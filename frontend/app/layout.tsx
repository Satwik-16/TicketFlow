import type { Metadata } from "next";
import { Syne, DM_Sans } from "next/font/google";
import "./globals.css";

const syne = Syne({
  variable: "--font-syne",
  subsets: ["latin"],
  display: "swap",
});

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Apexon AI Agent",
  description: "Enterprise-grade IT Helpdesk AI.",
  keywords: ["IT helpdesk", "AI agent", "ticket management", "LangGraph"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${syne.variable} ${dmSans.variable} h-full antialiased dark`}>
      <body className="min-h-full font-body text-slate-300">
        {children}
      </body>
    </html>
  );
}
