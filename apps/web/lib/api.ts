// Server-side fetch helper. Browser code calls relative /api/* paths, which
// next.config.ts rewrites to the FastAPI service.
const API_URL = process.env.FURNACE_API_URL ?? "http://localhost:8010";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new ApiError(res.status, body?.detail ?? `GET ${path} failed (${res.status})`);
  }
  return (await res.json()) as T;
}
