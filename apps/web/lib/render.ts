// Server-only rendering mode (lib/site.ts stays importable from client components).
import { connection } from "next/server";
import { RECORDED_ONLY } from "@/lib/site";

/** Live deployments render per request (fresh results from the API); recorded ones are static. */
export async function dynamicUnlessRecorded(): Promise<void> {
  if (!RECORDED_ONLY) await connection();
}
