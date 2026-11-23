import { ProductHome } from "@/components/download/site";
import { readInstaller } from "@/lib/download-release";
export default function Home() { return <ProductHome installer={readInstaller()} />; }
