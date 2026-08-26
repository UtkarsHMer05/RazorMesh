import type { Metadata } from 'next';
import { Outfit, Inter } from 'next/font/google';
import { SiteNav } from '@/components/site-nav';
import './globals.css';

const outfit = Outfit({
  subsets: ['latin'],
  weight: ['400', '500', '700', '900'],
  display: 'swap',
  variable: '--font-outfit',
});

const inter = Inter({
  subsets: ['latin'],
  weight: ['400', '500'],
  display: 'swap',
  variable: '--font-inter',
});

export const metadata: Metadata = {
  title: 'RazorMesh Trust — Intent-to-Execution Integrity',
  description:
    'RazorMesh verifies intent, semantics, and execution before an AI agent can move money. Local prototype (Test Mode, no real money).',
  metadataBase: new URL('http://localhost:3000'),
  openGraph: {
    title: 'RazorMesh Trust',
    description:
      'Runtime trust infrastructure for agentic commerce. The AI proposes; RazorGuard authorizes; the trusted executor executes.',
    type: 'website',
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${outfit.variable} ${inter.variable}`} suppressHydrationWarning>
      <body className={outfit.className}>
        <div
          className="mock-banner"
          role="note"
          data-testid="mock-provider-banner"
        >
          TEST ENVIRONMENT — NO REAL MONEY — UNOFFICIAL PROTOTYPE (MOCK OR
          RAZORPAY TEST MODE)
        </div>
        <SiteNav />
        <main className="main">{children}</main>
      </body>
    </html>
  );
}
