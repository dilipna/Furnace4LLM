import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";

const display = localFont({src:"./fonts/SchibstedGrotesk[wght].ttf",variable:"--font-schibsted",weight:"500 700",display:"swap",preload:false});
const sans = localFont({src:"./fonts/IBMPlexSans[wdth,wght].ttf",variable:"--font-plex-sans",weight:"400 600",display:"swap",preload:false});
const mono = localFont({src:[{path:"./fonts/IBMPlexMono-Regular.ttf",weight:"400"},{path:"./fonts/IBMPlexMono-Medium.ttf",weight:"500"}],variable:"--font-plex-mono",display:"swap",preload:false});

export const metadata: Metadata = {
  title: "Furnace — A workspace for your model",
  description:
    "Prepare a local workspace for your research model. Get started with a free kit, explore a guided example, and inspect recorded research and its limitations.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${display.variable} ${sans.variable} ${mono.variable} h-full`}>
      <body className="min-h-full flex flex-col bg-bg-0 text-fg-0">{children}</body>
    </html>
  );
}
