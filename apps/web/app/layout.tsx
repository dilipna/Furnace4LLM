import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const display = localFont({src:"./fonts/SchibstedGrotesk[wght].ttf",variable:"--font-schibsted",weight:"500 700",display:"swap"});
const sans = localFont({src:"./fonts/IBMPlexSans[wdth,wght].ttf",variable:"--font-plex-sans",weight:"400 600",display:"swap"});
const mono = localFont({src:[{path:"./fonts/IBMPlexMono-Regular.ttf",weight:"400"},{path:"./fonts/IBMPlexMono-Medium.ttf",weight:"500"}],variable:"--font-plex-mono",display:"swap"});

export const metadata: Metadata = {
  title: "Furnace — Private AI for your documents.",
  description:
    "Summarise sensitive documents, ask questions and write locally. Inspect each answer’s privacy checks. Free Windows application preview.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://furnace-5h6.pages.dev"),
  openGraph: { title: "Furnace — Private AI for your documents.", description: "Private document help on your computer, with inspectable privacy checks.", type: "website", images: ["/product/og.svg"] },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-bg-0 text-fg-0">{children}</body>
    </html>
  );
}
