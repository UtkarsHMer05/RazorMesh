import type { Metadata } from "next";
import { ClientNav } from "@/components/client-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "RazorMesh Trust",
  description:
    "Runtime trust infrastructure for agentic commerce — local prototype (Test Mode, no real money).",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <div className="mock-banner" role="note" data-testid="mock-provider-banner">
          TEST ENVIRONMENT — NO REAL MONEY — UNOFFICIAL PROTOTYPE (MOCK OR RAZORPAY
          TEST MODE)
        </div>
        <header className="header">
          <div className="container header-inner">
            <div className="brand">
              <span className="brand-name">RazorMesh Trust</span>
              <span className="brand-sub">
                Built for Razorpay Buildathon · unofficial prototype
              </span>
            </div>
            <nav aria-label="Primary">
              <ClientNav />
            </nav>
          </div>
        </header>
        <main className="main container">{children}</main>
      </body>
    </html>
  );
}
