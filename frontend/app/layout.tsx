import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Horizon — XAU Bot",
  description: "Intelligent XAUUSDT trading bot",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
