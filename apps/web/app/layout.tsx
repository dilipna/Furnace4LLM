import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const display = localFont({src:"./fonts/SchibstedGrotesk[wght].ttf",variable:"--font-schibsted",weight:"500 700",display:"swap",preload:false});
const sans = localFont({src:"./fonts/IBMPlexSans[wdth,wght].ttf",variable:"--font-plex-sans",weight:"400 600",display:"swap",preload:false});
const mono = localFont({src:[{path:"./fonts/IBMPlexMono-Regular.ttf",weight:"400"},{path:"./fonts/IBMPlexMono-Medium.ttf",weight:"500"}],variable:"--font-plex-mono",display:"swap",preload:false});

export const metadata: Metadata = {
  title: "Furnace — Infrastructure for your model.",
  description:
    "Connect a research model, get a free infrastructure starter kit and operate supported models locally. Furnace-operated hosting is proposed at $20/month.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "https://furnace-5h6.pages.dev"),
  openGraph: { title: "Furnace — Infrastructure for your model.", description: "A free infrastructure starter kit and local serving, evaluations, monitoring, logs and recovery for model researchers.", type: "website", images: ["/product/og.svg"] },
  robots: { index: true, follow: true },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-bg-0 text-fg-0">{children}</body>
    </html>
  );
}
