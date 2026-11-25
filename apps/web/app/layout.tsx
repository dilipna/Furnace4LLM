import type { Metadata } from "next";
import "./globals.css";
import "./font-vars.css";

export const metadata: Metadata = {
  title: "Furnace — Your model. Your machine.",
  description:
    "Run open-weight models locally with isolated serving, evaluations, logs and crash recovery. Free local app. Windows installer preview.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://furnace-5h6.pages.dev"),
  openGraph: { title: "Furnace — Your model. Your machine.", description: "A home for your local model. Isolated serving, evaluations and crash recovery.", type: "website", images: ["/product/og.svg"] },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full">
      <body className="min-h-full flex flex-col bg-bg-0 text-fg-0">{children}</body>
    </html>
  );
}
