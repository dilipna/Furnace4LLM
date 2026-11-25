import type { Metadata } from "next";
import { ProductDocument, titles } from "@/components/download/documents";
import { readInstaller } from "@/lib/download-release";
export const dynamicParams = false;
export function generateStaticParams() { return Object.keys(titles).filter(info => !["start", "pricing"].includes(info)).map(info => ({ info })); }
export async function generateMetadata({ params }: { params: Promise<{ info: string }> }): Promise<Metadata> { const { info } = await params; return { title: (titles[info] ?? "Guide") + " · Furnace" }; }
export default async function InfoPage({ params }: { params: Promise<{ info: string }> }) { const { info } = await params; return <ProductDocument kind={info} installer={info === "releases" ? readInstaller() : null} />; }
