// frontend/src/app/layout.tsx
import type { Metadata } from "next";
// We are importing fonts via globals.css with @import for this example
// but using next/font is generally preferred for performance.
// const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
// const playfair = Playfair_Display({ subsets: ["latin"], weight: "700", variable: "--font-serif" });

import "./globals.css";

export const metadata: Metadata = {
  title: "Portfolio Builder", // Updated title
  description: "Generate Portfolio's with reference websites.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // <html lang="en" className={`${inter.variable} ${playfair.variable}`}>
    <html lang="en"> 
      <body>{children}</body>
    </html>
  );
}