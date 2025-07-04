# backend/app/services/llm_service.py
import base64
import asyncio
import traceback
from fastapi import HTTPException

import google.cloud.aiplatform as aiplatform
from vertexai.generative_models import GenerativeModel, Part, Image
from vertexai.generative_models import GenerationConfig, SafetySetting, HarmCategory, HarmBlockThreshold
import google.api_core.exceptions

# Import config variables
from app.core import config

_vertex_ai_initialized = False

def initialize_vertex_ai():
    global _vertex_ai_initialized
    if _vertex_ai_initialized: return True
    if not config.GCP_PROJECT_ID:
        print("CRITICAL: GCP_PROJECT_ID is not defined. LLM functionality will be unavailable.")
        _vertex_ai_initialized = False
        return False
    try:
        print(f"Attempting to initialize Vertex AI for project {config.GCP_PROJECT_ID} in {config.GCP_LOCATION}...")
        aiplatform.init(project=config.GCP_PROJECT_ID, location=config.GCP_LOCATION)
        print(f"Vertex AI successfully initialized for project {config.GCP_PROJECT_ID} in {config.GCP_LOCATION}.")
        _vertex_ai_initialized = True
        return True
    except Exception as e:
        print(f"CRITICAL: Error initializing Vertex AI: {e}\n{traceback.format_exc()}")
        _vertex_ai_initialized = False
        return False

async def generate_html_with_llm(cleaned_html: str, desktop_screenshot_base64: str, mobile_screenshot_base64: str) -> str:
    if not initialize_vertex_ai():
        raise HTTPException(status_code=500, detail="Vertex AI not initialized or initialization failed.")
    
    system_prompt = """
You are an expert web developer specializing in creating HTML and CSS replicas of websites.
Your goal is to generate a single, self-contained HTML file with an embedded CSS <style> block in the <head> that visually replicates the provided website design as closely as possible.
You will be given:
1. A desktop screenshot of the target website (as base64 encoded PNG).
2. A mobile screenshot of the target website (as base64 encoded PNG).
3. A cleaned HTML structure of the target website's body content. This HTML has had most classes, styles, and data attributes removed. Focus on the semantic tags and the visual information from the screenshots to determine styling and layout.
Instructions:
- Analyze the screenshots for layout, typography (font families, sizes, weights, colors), colors, spacing, borders, shadows, and other visual elements for both desktop and mobile views.
- Use the provided cleaned HTML as a structural guide. Recreate the elements present in this HTML.
- Generate appropriate CSS within a single `<style>` block in the `<head>` of the HTML document to match the visual appearance in the screenshots.
- Use media queries (e.g., @media (max-width: 768px) { ... }) for responsiveness to ensure the design adapts between the desktop and mobile screenshot appearances.
- Pay attention to the semantic meaning of HTML tags (e.g., <nav>, <button>, <h1>) when deciding on styles.
- If you see empty <div> tags in the provided HTML where an icon might have been (based on the screenshot), you can either omit the div or, if an icon is clearly visible and simple (like an arrow or a common symbol), you can try to replicate it using a simple inline SVG or a Unicode character. For complex icons or logos not provided as images, use a placeholder description like <!-- placeholder for search icon --> or omit.
- Ensure the generated HTML is well-formed, including <!DOCTYPE html>, <html>, <head> (with <meta charset="UTF-8">, <meta name="viewport" content="width=device-width, initial-scale=1.0">, and <title>Website Clone</title>), and <body> tags.
- Prioritize visual similarity to the screenshots.
- Do not use any external CSS libraries or JavaScript. The output should be a single HTML file.
- For fonts, try to use common web-safe fonts (e.g., Arial, Helvetica, sans-serif; Times New Roman, serif; Courier New, monospace) that approximate the look in the screenshots. If a very specific font name is obvious (like "Uber Move Display"), you can specify it in the CSS `font-family` property.
- For images visible in the screenshot but not represented by <img> tags in the cleaned HTML (e.g., background images), you should try to include them using CSS background-image properties. Use descriptive placeholder URLs like "placeholder-background-image.jpg" or similar if the actual image source isn't available.
- The final output should be ONLY the complete HTML code, starting with <!DOCTYPE html>. Do not include any conversational text or explanations before or after the HTML code block.
    """
    max_retries = 2; base_delay = 5
    current_max_output_tokens = 65000 # Using the model's known limit

    for attempt in range(max_retries + 1):
        try:
            model = GenerativeModel(config.MODEL_NAME)
            prompt_parts = [
                Part.from_text(system_prompt), Part.from_text("\n\nHere is the design context:\n\nCleaned HTML Structure:\n```html\n"),
                Part.from_text(cleaned_html), Part.from_text("\n```\n\nDesktop Screenshot (Base64 PNG):\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(desktop_screenshot_base64))),
                Part.from_text("\n\nMobile Screenshot (Base64 PNG):\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(mobile_screenshot_base64))),
                Part.from_text("\n\nPlease generate the complete HTML code as a single block, starting with <!DOCTYPE html>.")
            ]
            generation_config_obj = GenerationConfig(temperature=0.2, top_p=0.95, top_k=40, max_output_tokens=current_max_output_tokens, response_mime_type="text/plain")
            safety_settings_list = [
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
            ]
            
            print(f"Sending request to Gemini model (Attempt {attempt + 1}): {config.MODEL_NAME} with max_output_tokens={current_max_output_tokens}...")
            response = await model.generate_content_async(contents=prompt_parts, generation_config=generation_config_obj, safety_settings=safety_settings_list)
            print("Received response from Gemini.")
            
            if response and response.candidates:
                candidate = response.candidates[0]
                print(f"Candidate Finish Reason: {candidate.finish_reason}")
                if hasattr(candidate, 'safety_ratings'): print(f"Candidate Safety Ratings: {candidate.safety_ratings}")
                if hasattr(response, 'usage_metadata'): print(f"Usage Metadata: {response.usage_metadata}")
                
                if candidate.finish_reason == 2: print("Warning: Output truncated due to MAX_TOKENS limit.")
                
                if candidate.content and candidate.content.parts:
                    raw_generated_text = "".join(p.text for p in candidate.content.parts if hasattr(p, 'text') and p.text)
                    print(f"RAW LLM OUTPUT (first 500 chars):\n---\n{raw_generated_text[:500]}...\n---")
                    
                    generated_html = raw_generated_text
                    if generated_html.strip().startswith("```html"): generated_html = generated_html.strip()[7:]
                    if generated_html.strip().endswith("```"): generated_html = generated_html.strip()[:-3]
                    
                    if not generated_html.strip() and candidate.finish_reason == 1: 
                         print("Warning: Generated HTML is empty after stripping markdown, though model stopped naturally.")
                    return generated_html.strip() 
            raise HTTPException(status_code=500, detail="LLM response did not contain valid candidates or content.")
        
        except google.api_core.exceptions.ResourceExhausted as e_res_exhausted:
            print(f"ResourceExhausted error (Attempt {attempt + 1}): {e_res_exhausted}")
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                print("Max retries reached for ResourceExhausted error.")
                raise HTTPException(status_code=429, detail=f"Resource exhausted after multiple retries: {str(e_res_exhausted)}")
        except Exception as e:
            print(f"Error calling LLM: {type(e).__name__} - {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate HTML with LLM. Error: {str(e)}")
    
    raise HTTPException(status_code=500, detail="LLM generation failed after all attempts.")


# --- NEW FUNCTION for parsing resume text ---
async def parse_resume_to_json(resume_text: str) -> dict:
    """
    Uses an LLM to parse raw resume text into a structured JSON object.
    """
    if not initialize_vertex_ai():
        raise HTTPException(status_code=500, detail="Vertex AI not initialized for resume parsing.")

    # A cheaper, faster model might be suitable for this parsing task.
    # We can use a config variable or hardcode it for now.
    parser_model_name = config.MODEL_NAME # Or config.PARSER_MODEL_NAME if you define it

    system_prompt = """
You are an expert resume parser. Your task is to analyze the provided resume text and extract key information into a structured JSON object.
The JSON object must have the following schema:
{
  "name": "string",
  "headline": "string (e.g., 'Software Engineer' or 'Product Manager')",
  "contact_info": {
    "email": "string",
    "phone": "string",
    "linkedin": "string (full URL)",
    "github": "string (full URL)",
    "portfolio": "string (full URL)"
  },
  "summary": "string (A brief professional summary or about me section)",
  "skills": [
    "string"
  ],
  "experience": [
    {
      "role": "string",
      "company": "string",
      "location": "string",
      "dates": "string (e.g., 'Jan 2020 - Present')",
      "description_points": [
        "string"
      ]
    }
  ],
  "projects": [
    {
      "name": "string",
      "description": "string",
      "technologies": [
        "string"
      ],
      "link": "string (full URL)"
    }
  ],
  "education": [
      {
          "institution": "string",
          "degree": "string",
          "dates": "string"
      }
  ]
}
If a field is not present in the resume text, omit the key or set its value to null. For arrays like 'experience', if there are no items, provide an empty array [].
The entire output must be ONLY the JSON object, with no surrounding text, comments, or markdown fences like ```json.
"""
    try:
        model = GenerativeModel(parser_model_name)
        
        # We need to explicitly ask for JSON output
        generation_config = GenerationConfig(
            temperature=0.0, # Low temperature for deterministic parsing
            response_mime_type="application/json",
        )
        
        print(f"Sending resume text to {parser_model_name} for parsing...")
        response = await model.generate_content_async(
            [system_prompt, resume_text],
            generation_config=generation_config
        )

        print("Received parsed resume from LLM.")
        
        # The response should be a single text part containing the JSON string
        parsed_json_text = response.text
        
        # Use a robust way to parse the JSON from the response text
        import json
        return json.loads(parsed_json_text)

    except Exception as e:
        print(f"Error parsing resume with LLM: {type(e).__name__} - {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to parse resume data with LLM. Error: {str(e)}")


# --- NEW FUNCTION for generating portfolio HTML ---

async def generate_portfolio_from_context(
    scraped_context: dict, 
    resume_json: dict
) -> str:
    """
    Uses style context and structured user data (JSON) to generate a portfolio page.
    """
    if not initialize_vertex_ai():
        raise HTTPException(status_code=500, detail="Vertex AI not initialized for portfolio generation.")

    builder_model_name = config.MODEL_NAME # Or config.BUILDER_MODEL_NAME

    # This prompt is the new "builder" prompt
    system_prompt = """
You are an expert web developer tasked with building a beautiful, single-page personal portfolio.
You will be given three pieces of information:
1.  **Style Guide:** Screenshots (desktop and mobile) of a reference website to define the visual aesthetic (layout, colors, typography, spacing, component styles).
2.  **Structural Guide:** A cleaned HTML structure from the reference website. Use this to understand the layout and section order (e.g., hero, about, projects, experience).
3.  **User Content:** A JSON object containing the user's personal information (name, skills, experience, projects, etc.).

Your task is to generate a single, self-contained HTML file. This file must:
-   Visually match the style of the provided screenshots.
-   Use the layout and sectioning of the provided HTML structure as a guide.
-   Be populated exclusively with the user's data from the provided JSON object. DO NOT use any text content from the reference site's HTML.
-   If a user image is needed, use a gender-neutral illustrated avatar (not realistic or photo-based). Prefer stylized, cartoon-style avatars from sources like example : DiceBear or Avataaars, which preserve anonymity and inclusivity.
-   Intelligently map the JSON data to the appropriate sections. For example:
    -   `name` and `headline` from the JSON go into the hero/header section.
    -   The `experience` array from the JSON should be used to create a list of jobs in the "Experience" or "Work" section of the layout.
    -   The `projects` array should be used to create project cards in the "Projects" section.
    -   The `skills` array should be displayed in a "Skills" section.
-   All CSS must be in a single `<style>` block in the `<head>`.
-   The final output must be ONLY the complete HTML code, starting with <!DOCTYPE html>.
"""
    # This function reuses the same logic as generate_html_with_llm, but with a different prompt
    # and includes the resume_json in the prompt parts.
    
    import json
    max_retries = 2; base_delay = 5
    current_max_output_tokens = 65000

    for attempt in range(max_retries + 1):
        try:
            model = GenerativeModel(builder_model_name)
            
            prompt_parts = [
                Part.from_text(system_prompt),
                Part.from_text("\n\n--- STYLE AND STRUCTURAL GUIDE ---\n"),
                Part.from_text("Desktop Screenshot:\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(scraped_context['desktop_screenshot_base64']))),
                Part.from_text("\nMobile Screenshot:\n"),
                Part.from_image(Image.from_bytes(base64.b64decode(scraped_context['mobile_screenshot_base64']))),
                Part.from_text("\nCleaned HTML Structure:\n```html\n"),
                Part.from_text(scraped_context['simplified_html'] or "<!-- No HTML structure provided -->"),
                Part.from_text("\n```\n\n--- USER CONTENT (JSON) ---\n```json\n"),
                # Pretty-print the JSON so it's easier for the LLM to read
                Part.from_text(json.dumps(resume_json, indent=2)),
                Part.from_text("\n```\n\nPlease generate the complete portfolio HTML file based on these inputs.")
            ]

            generation_config_obj = GenerationConfig(temperature=0.2, top_p=0.95, top_k=40, max_output_tokens=current_max_output_tokens, response_mime_type="text/plain")
            safety_settings_list = [
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE),
                SafetySetting(category=HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE)
            ]
            
            print(f"Sending context to {builder_model_name} for portfolio generation (Attempt {attempt + 1})...")
            response = await model.generate_content_async(contents=prompt_parts, generation_config=generation_config_obj, safety_settings=safety_settings_list)
            print("Received portfolio response from Gemini.")
            
            if response and response.candidates and response.candidates[0].content.parts:
                candidate = response.candidates[0]
                print(f"Portfolio Gen Finish Reason: {candidate.finish_reason}")
                
                raw_generated_text = "".join(p.text for p in candidate.content.parts if hasattr(p, 'text'))
                
                generated_html = raw_generated_text
                if generated_html.strip().startswith("```html"): generated_html = generated_html.strip()[7:]
                if generated_html.strip().endswith("```"): generated_html = generated_html.strip()[:-3]
                
                return generated_html.strip()
            
            raise HTTPException(status_code=500, detail="LLM response for portfolio generation was invalid.")

        except google.api_core.exceptions.ResourceExhausted as e:
            # ... (Retry logic as in generate_html_with_llm) ...
            print(f"ResourceExhausted on portfolio gen (Attempt {attempt + 1}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(base_delay * (2 ** attempt))
            else:
                raise HTTPException(status_code=429, detail=f"Resource exhausted for portfolio generation: {str(e)}")
        except Exception as e:
            print(f"Error generating portfolio with LLM: {type(e).__name__} - {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"Failed to generate portfolio with LLM. Error: {str(e)}")

    raise HTTPException(status_code=500, detail="Portfolio generation failed after all attempts.")