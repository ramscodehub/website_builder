"use client";

import { useState, FormEvent } from "react";
import Image from 'next/image';
import styles from "./DarkHomePage.module.css"; 

// --- Icons ---
const AiIconPlaceholder = () => ( <div style={{ width: '28px', height: '28px', background: 'linear-gradient(135deg, #BB86FC, #6200EE)', borderRadius: '6px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><img src="/favicon.ico" alt="AI Icon" style={{ width: '20px', height: '20px', objectFit: 'contain', borderRadius: '3px' }}/></div> );

// NEW: SVG Icon Components for Footer
const GithubIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" role="img" aria-hidden="true">
    <path d="M12 2C6.477 2 2 6.477 2 12c0 4.418 2.865 8.165 6.839 9.489.5.092.682-.218.682-.482 0-.237-.009-1.024-.014-1.862-2.782.603-3.369-1.21-3.369-1.21-.454-1.156-1.11-1.464-1.11-1.464-.908-.62.069-.608.069-.608 1.004.071 1.532 1.03 1.532 1.03.891 1.529 2.34 1.087 2.91.831.091-.646.349-1.087.635-1.338-2.22-.253-4.555-1.113-4.555-4.949 0-1.092.39-1.985 1.03-2.685-.104-.253-.448-1.272.098-2.648 0 0 .84-.269 2.75 1.025A9.547 9.547 0 0 1 12 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.748-1.025 2.748-1.025.548 1.376.204 2.395.1 2.648.64.7 1.028 1.593 1.028 2.685 0 3.848-2.337 4.695-4.566 4.942.359.31.678.92.678 1.852 0 1.336-.012 2.415-.012 2.741 0 .267.18.577.688.482A10.001 10.001 0 0 0 22 12c0-5.523-4.477-10-10-10Z" />
  </svg>
);
const LinkedInIcon = () => (
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" role="img" aria-hidden="true">
    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11 19h-3v-11h3v11zm-1.5-12.268c-.966 0-1.75-.79-1.75-1.764s.784-1.764 1.75-1.764 1.75.79 1.75 1.764-.783 1.764-1.75 1.764zm13.5 12.268h-3v-5.604c0-3.368-4-3.113-4 0v5.604h-3v-11h3v1.765c1.396-2.586 7-2.777 7 2.476v6.759z" />
  </svg>
);


// --- Interfaces & Gallery Data (as before) ---
interface GalleryItem { id: string; viewLink: string; previewImageUrl: string; title: string; description?: string; }
interface CloneApiResponse { message: string; file_path: string; view_link?: string; }
const allGalleryItems: GalleryItem[] = [
    { id: "p1", viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250705_113015.html", previewImageUrl: "/gallery_previews/p1.png", title: "Portfolio", description: "Style: Modern & Minimal" },
    { id: "p2", viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250628_194319.html", previewImageUrl: "/gallery_previews/p2.png", title: "Portfolio", description: "Style: Creative & Playful" },
    { id: "p3", viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250705_165357.html", previewImageUrl: "/gallery_previews/p3.png", title: "Portfolio", description: "Style: Tech Blog Inspired" },
    { id: "p4", viewLink: "https://d12dmeynqgk1fi.cloudfront.net/portfolios/prudhvi_ram_mannuru_portfolio_20250701_205318.html", previewImageUrl: "/gallery_previews/p4.png", title: "Portfolio", description: "Style: Professional SaaS" },
];

export default function HomePage() {
  const [referenceUrl, setReferenceUrl] = useState<string>("");
  const [resumeText, setResumeText] = useState<string>("");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showUnoLink, setShowUnoLink] = useState<boolean>(false);
  
  const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    // ... (This function remains unchanged) ...
    event.preventDefault();
    if (!referenceUrl) { setError("Please enter a reference portfolio URL."); return; }
    if (!resumeText) { setError("Please paste your resume information."); return; }
    setIsLoading(true); setError(null); 
    setStatusMessage("Building your portfolio... This may take 4-5 minutes.");
    setShowUnoLink(true);
    const payload = { reference_url: referenceUrl, resume_text: resumeText };
    try {
        const response = await fetch(`${BACKEND_URL}/build-portfolio`, {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload),
        });
        if (!response.ok) {
            let errorDetail = `Error: ${response.status} ${response.statusText}`;
            try { const errorData = await response.json(); errorDetail = errorData.detail || errorDetail; }
            catch (e) { /* Ignore */ }
            throw new Error(errorDetail);
        }
        const data: CloneApiResponse = await response.json();
        setShowUnoLink(false);
        setStatusMessage(data.message || "Portfolio built successfully!");
        if (data.view_link) {
            window.open(data.view_link, '_blank', 'noopener,noreferrer');
        } else {
            setError("Portfolio built successfully, but no viewable link was returned.");
        }
    } catch (err: any) {
        setError(err.message || "Failed to build portfolio.");
        setStatusMessage("Portfolio building process failed.");
        setShowUnoLink(false);
        console.error("API Error:", err);
    } finally {
        setIsLoading(false);
    }
  };
  
  return (
    <div className={styles.mainContainer}>
      <header className={styles.header}>
        <div className={styles.logoContainer}> <AiIconPlaceholder /> </div>
      </header>

      {/* Hero Section and Form remain unchanged */}
      <section className={styles.heroSection}>
        <h1 className={styles.heroHeadline}>Build your portfolio in seconds</h1>
        <p className={styles.heroSubHeadline}>Provide a reference portfolio for style, and your resume for content.</p>
        <form onSubmit={handleSubmit} className={styles.inputForm}>
            <div className={styles.inputCard}>
                <label htmlFor="referenceUrl" className={styles.inputLabel}>Reference Portfolio URL</label>
                <input id="referenceUrl" type="url" value={referenceUrl} onChange={(e) => setReferenceUrl(e.target.value)} placeholder="https://www.example-portfolio.com" className={styles.urlInput} required disabled={isLoading} />
            </div>
            <div className={styles.inputCard}>
                <label htmlFor="resumeText" className={styles.inputLabel}>Your Resume / Profile Info</label>
                <textarea id="resumeText" value={resumeText} onChange={(e) => setResumeText(e.target.value)} placeholder="Paste your full resume or professional bio here..." className={styles.resumeTextarea} required disabled={isLoading} />
            </div>
            <div className={styles.submitButtonContainer}>
                <button type="submit" className={styles.submitButton} disabled={isLoading} aria-label="Build Portfolio">
                    <span>Build My Portfolio</span>
                </button>
            </div>
        </form>
      </section>

      {/* Status messages remain unchanged */}
      {(isLoading || statusMessage || error) && ( <div className={styles.statusMessageContainer}> {isLoading && statusMessage && <p className={styles.statusMessage}>{statusMessage}</p>} {isLoading && showUnoLink && ( <p className={styles.unoLinkMessage}> While you wait, feel free to play a game of <a href="https://unoapp-qpfg65xn6a-ue.a.run.app/" target="_blank" rel="noopener noreferrer" className={styles.unoLink}>UNO that I built!</a> </p> )} {!isLoading && statusMessage && !error && <p className={styles.statusMessage}>{statusMessage}</p>} {error && <p className={styles.errorMessage}>{error}</p>} </div> )}
      
      {/* Gallery Section remains unchanged */}
      <section className={styles.gallerySection}>
        <h2 className={styles.galleryMainTitle}>Portfolios Generated with this Service</h2>
        <p className={styles.gallerySubTitle}>Click any card to visit the live site</p>
        <div className={styles.galleryGrid}>
          {allGalleryItems.map((site) => (
            <a key={site.id} href={site.viewLink} target="_blank" rel="noopener noreferrer" className={styles.galleryCardLinkWrapper}>
              <div className={styles.galleryCard}>
                <div className={styles.galleryCardPreviewContainer}>
                  <Image src={site.previewImageUrl} alt={`Screenshot preview for ${site.title}`} fill className={styles.galleryCardPreviewImage} />
                </div>
                <div className={styles.galleryCardContent}>
                  <h3 className={styles.galleryCardTitle}>{site.title}</h3>
                  <p className={styles.galleryCardDescription}>{site.description}</p>
                </div>
              </div>
            </a>
          ))}
        </div>
      </section>

      {/* --- NEW FOOTER SECTION --- */}
      <footer className={styles.footer}>
        <p className={styles.footerText}>
          Built by Prudhvi Ram Mannuru
        </p>
        <div className={styles.footerLinks}>
          <a href="https://github.com/ramscodehub" target="_blank" rel="noopener noreferrer" className={styles.footerIconLink} aria-label="GitHub Profile">
            <GithubIcon />
          </a>
          <a href="https://linkedin.com/in/prudhviram" target="_blank" rel="noopener noreferrer" className={styles.footerIconLink} aria-label="LinkedIn Profile">
            <LinkedInIcon />
          </a>
        </div>
      </footer>
    </div>
  );
}