// Server-side fetch helper. Browser code calls relative /api/* paths, which
// next.config.ts rewrites to the FastAPI service.
import { RECORDED_ONLY } from "@/lib/site";

const API_URL = process.env.FURNACE_API_URL ?? "http://localhost:8010";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

// Recorded-only deployments answer the read-only /api/bench/* routes from the committed
// snapshot (the same JSON the API returns); anything else has no service behind it.
async function fromSnapshot<T>(path: string): Promise<T> {
  const responses = (await import("@/lib/bench-snapshot.json")).default.responses as Record<string, unknown>;
  if (path in responses) return responses[path] as T;
  if (path.startsWith("/api/bench/")) throw new ApiError(404, `${path} is not in the recorded results`);
  throw new ApiError(503, "This site shows recorded results only; the live API is not deployed here.");
}

export async function apiGet<T>(path: string): Promise<T> {
  if (RECORDED_ONLY) return fromSnapshot<T>(path);
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? `GET ${path} failed (${res.status})`);
  }
  return (await res.json()) as T;
}
