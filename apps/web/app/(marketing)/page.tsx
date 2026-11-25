import { ProductHome } from "@/components/download/site";
import { readEverydayRecording } from "@/lib/everyday-recording";
import { readInstaller } from "@/lib/download-release";
export default function Home() { return <ProductHome installer={readInstaller()} recording={readEverydayRecording()} />; }
