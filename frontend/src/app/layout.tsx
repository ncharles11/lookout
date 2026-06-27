import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Lookout — HUD Dashboard",
  description: "Self-hosted infrastructure monitoring",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-[#09090b] antialiased">{children}</body>
    </html>
  );
}
