import { InstalledTour } from "@/components/download/tour";
import { readRecording } from "@/lib/recording";
export default function DemoPage() { return <InstalledTour recording={readRecording()} />; }
