# backend/app/api/endpoints.py
import os
from datetime import datetime
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
import traceback

# Import services, models, and config
from app.services import scraper_service, llm_service, s3_service
from app.models.pydantic_models import (
    UrlRequest, PortfolioBuildConfig, ScrapedContextResponse, ClonedHtmlFileResponse,
    GalleryResponse, GalleryItem
)
from app.core import config

router = APIRouter()

@router.post("/get-scraped-context", response_model=ScrapedContextResponse, summary="Scrape and Clean Website Context")
async def get_scraped_context_endpoint(req: UrlRequest):
    try:
        print(f"Scraping URL for tester context: {req.url}")
        context_data = await scraper_service.scrape_website_context(req.url)
        return ScrapedContextResponse(
            desktop_screenshot_base64=context_data.desktop_screenshot_base64,
            mobile_screenshot_base64=context_data.mobile_screenshot_base64,
            simplified_html=context_data.simplified_html,
            original_url=req.url
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Unexpected error in /get-scraped-context: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred. Error: {str(e)}")

@router.post("/clone-website-and-save", response_model=ClonedHtmlFileResponse, summary="Clone Website and Save HTML to File")
async def clone_website_and_save_endpoint(req_body: UrlRequest, request: Request):
    try:
        print(f"Step 1: Scraping URL for cloning: {req_body.url}")
        context_data = await scraper_service.scrape_website_context(req_body.url)
        if not context_data.simplified_html or "failed" in context_data.simplified_html.lower() or "empty" in context_data.simplified_html.lower():
            raise HTTPException(status_code=422, detail=f"HTML scraping/cleaning failed. HTML: {context_data.simplified_html[:200]}")
        
        ENABLE_LLM_CLONING = True
        llm_generated_html = ""

        if ENABLE_LLM_CLONING:
            print("Step 2: Generating HTML with LLM...")
            llm_generated_html = await llm_service.generate_html_with_llm(
                cleaned_html=context_data.simplified_html,
                desktop_screenshot_base64=context_data.desktop_screenshot_base64,
                mobile_screenshot_base64=context_data.mobile_screenshot_base64
            )
            print("Step 3: Received HTML from LLM processing.")
            if not llm_generated_html.strip():
                 print("Warning: LLM returned an effectively empty HTML string.")
        else:
            print("Step 2 & 3: LLM Cloning is disabled. Generating placeholder HTML.")
            llm_generated_html = f"<html><body><h1>Placeholder for {req_body.url}</h1><p>LLM cloning is currently disabled.</p></body></html>"
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        sanitized_url_part = req_body.url.split('//')[-1].split('/')[0].replace('.', '_').replace(':', '_')
        filename = f"clone_{sanitized_url_part}_{timestamp}.html"
        file_path = os.path.join(config.GENERATED_HTML_DIR_PATH, filename)
        
        try:
            with open(file_path, "w", encoding="utf-8") as f: f.write(llm_generated_html)
            print(f"Successfully saved cloned HTML to: {file_path}")
        except IOError as e:
            print(f"Error saving HTML file: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to save generated HTML file. Error: {str(e)}")
        
        base_url_parts = request.url.components
        base_url = f"{base_url_parts.scheme}://{base_url_parts.netloc}"
        view_link_path = f"{config.STATIC_CLONES_PATH_PREFIX}/{filename}"
        view_link = f"{base_url}{view_link_path}"
        
        return ClonedHtmlFileResponse(
            message="Website cloned and HTML saved." if ENABLE_LLM_CLONING else "Placeholder HTML generated.",
            file_path=file_path,
            view_link=view_link
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        print(f"Unexpected error in /clone-website-and-save: {type(e).__name__} - {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred. Error: {str(e)}")

@router.get("/gallery-items", response_model=GalleryResponse, summary="Get Items for Website Clone Gallery")
async def get_gallery_items(request: Request):
    items = []
    base_url_parts = request.url.components
    base_url = f"{base_url_parts.scheme}://{base_url_parts.netloc}"
    gallery_data_map = {
        "Landing Pages": [
            {"id": "ola", "filename": "clone_www_olacabs_com_20250605_183343.html", "title": "Ola Cabs", "description": "Ride Hailing Service"},
            {"id": "wix", "filename": "clone_www_wix_com_20250605_190834.html", "title": "Wix.com", "description": "Website Builder"},
            {"id": "wordpress", "filename": "clone_wordpress_com_20250605_222253.html", "title": "WordPress.com", "description": "Blogging Platform"}],
        "Portfolio Websites": [
            {"id": "simplegreet", "filename": "clone_simple-greetings-1748253405653_vercel_app_20250605_193006.html", "title": "Simple Greetings", "description": "Portfolio Example"}],
        "Ecommerce Sites": [
            {"id": "uber", "filename": "clone_www_uber_com_20250605_175014.html", "title": "Uber.com", "description": "Ride & Delivery"}]}
    for category, cat_items in gallery_data_map.items():
        for item_data in cat_items:
            local_file_path = os.path.join(config.GENERATED_HTML_DIR_PATH, item_data["filename"])
            if not os.path.exists(local_file_path):
                 print(f"Gallery item file missing, creating placeholder for: {item_data['filename']}")
                 try:
                     with open(local_file_path, "w", encoding="utf-8") as f_placeholder:
                         f_placeholder.write(f"<html><body><h1>Placeholder for {item_data['title']}</h1><p>File: {item_data['filename']}</p></body></html>")
                 except IOError:
                     print(f"Could not create placeholder for {item_data['filename']}")
            items.append(GalleryItem(id=item_data["id"], filename=item_data["filename"], view_link=f"{base_url}{config.STATIC_CLONES_PATH_PREFIX}/{item_data['filename']}", category=category, title=item_data["title"], description=item_data.get("description")))
    return GalleryResponse(items=items)

@router.get("/tester", response_class=FileResponse, summary="Get the Test Dashboard Page for Scraping Context")
async def get_test_dashboard():
    # Assumes tester.html is in the 'backend' directory, one level up from 'app'
    tester_path = os.path.join(config.BASE_DIR, "..", "tester.html")
    if not os.path.exists(tester_path):
        # Fallback if it's next to main.py inside app
        tester_path_alt = os.path.join(config.BASE_DIR, "tester.html")
        if os.path.exists(tester_path_alt):
            return FileResponse(tester_path_alt)
        raise HTTPException(status_code=404, detail=f"tester.html not found at {tester_path} or alternate.")
    return FileResponse(tester_path)

@router.post("/build-portfolio", response_model=ClonedHtmlFileResponse, summary="Build a Portfolio from a Reference URL and Resume")
async def build_portfolio_endpoint(build_config: PortfolioBuildConfig, request: Request):
    """
    Orchestrates the portfolio building process:
    1. Scrapes the reference URL for style.
    2. Parses the user's resume text into structured JSON.
    3. Generates a new HTML portfolio with the user's data in the reference style.
    4. Saves the generated HTML and returns a link to it.
    """
    try:
        # Step 1: Scrape the reference URL for its style and layout
        print(f"Step 1: Scraping reference URL: {build_config.reference_url}")
        scraped_context = await scraper_service.scrape_website_context(build_config.reference_url)
        if not scraped_context.simplified_html or "failed" in scraped_context.simplified_html.lower():
            raise HTTPException(status_code=422, detail="Scraping the reference URL failed. Cannot proceed.")
        if "Application error: a client-side exception has occurred" in scraped_context.simplified_html:
            print(f"ERROR: Detected a client-side crash on the reference site: {build_config.reference_url}")
            # Stop the process immediately and return a helpful error to the user.
            raise HTTPException(
                status_code=422, # Unprocessable Content
                detail="The provided reference website encountered a client-side error during processing. This can happen with some modern web frameworks. Please try a different reference URL.")
        # NEW Check 2: Empty root div (SPA didn't load)
        # We check if the simplified_html is very short and basically just the empty root div.
        if scraped_context.simplified_html and len(scraped_context.simplified_html) < 100 and '<div id="root"></div>' in scraped_context.simplified_html:
            print(f"ERROR: Scraped an empty shell for SPA site: {build_config.reference_url}")
            raise HTTPException(
                status_code=422,
                detail="The reference site seems to be a dynamic application that did not load content in time. Please try a different URL."
            )
        # Step 2: Parse the user's resume text into structured JSON
        print("Step 2: Parsing resume text with LLM...")
        resume_json = await llm_service.parse_resume_to_json(build_config.resume_text)
        if not resume_json.get("name") and not resume_json.get("experience"): # Basic check for successful parse
            raise HTTPException(status_code=422, detail="Failed to parse resume text into a usable format.")

        # Step 3: Generate the new portfolio HTML using the style and content
        print("Step 3: Generating new portfolio HTML with LLM...")
        generated_portfolio_html = await llm_service.generate_portfolio_from_context(
            scraped_context=scraped_context.model_dump(), # Pass the context as a dictionary
            resume_json=resume_json
        )
        print("Step 4: Received generated portfolio HTML.")

        if not generated_portfolio_html.strip():
            raise HTTPException(status_code=500, detail="LLM generated a blank portfolio. Please try a different reference URL or adjust resume text.")

        # Step 5: Save the generated file and create a view link
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use the person's name for a more descriptive filename if available
        person_name = resume_json.get("name", "portfolio").strip().replace(" ", "_").lower()
        filename = f"portfolios/{person_name}_portfolio_{timestamp}.html"
        file_path = f"s3://{config.S3_BUCKET_NAME}/{filename}"

        # Step 6: Upload to S3 using the new service function
        public_url = s3_service.upload_html_to_s3(
            html_content=generated_portfolio_html,
            filename=filename
        )
        
        return ClonedHtmlFileResponse(
            message="Portfolio built and deployed successfully.",
            file_path=file_path, # S3 URI
            view_link=public_url # Public HTTP URL
        )

    except HTTPException as http_exc:
        # Re-raise HTTPExceptions that are already well-formed
        raise http_exc
    except Exception as e:
        print(f"Unexpected error in /build-portfolio endpoint: {type(e).__name__} - {e}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred during portfolio generation. Error: {str(e)}")