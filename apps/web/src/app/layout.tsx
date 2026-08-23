import type { Metadata } from "next";
import { ClientNav } from "@/components/client-nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "RazorMesh Trust",
  description:
    "Runtime trust infrastructure for agentic commerce — Phase 1 local prototype (simulated payments only).",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <div className="mock-banner" role="note" data-testid="mock-provider-banner">
          MOCK PAYMENT PROVIDER — NO REAL MONEY — PHASE 1 LOCAL PROTOTYPE
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
