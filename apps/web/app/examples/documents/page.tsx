import { DocumentTour } from "@/components/download/document-tour";
import { readEverydayRecording } from "@/lib/everyday-recording";
export default function DocumentExamplePage() { return <DocumentTour recording={readEverydayRecording()} />; }
