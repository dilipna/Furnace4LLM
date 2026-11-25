import { InstalledTour } from "@/components/download/tour";
import { readRecording } from "@/lib/recording";
export default function ResearchTour() { return <InstalledTour recording={readRecording()} />; }
