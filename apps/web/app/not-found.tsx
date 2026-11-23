import Link from "next/link";
import { DocPage } from "@/components/download/site";
export default function NotFound() { return <DocPage title="This page took a wrong turn." eyebrow="404"><p>The page may have moved. Your local workspace is separate from this website.</p><p><Link href="/">Back to Furnace →</Link></p><p><Link href="/docs">Find a guide</Link> · <Link href="/earlier-work">Explore earlier work</Link></p></DocPage>; }
