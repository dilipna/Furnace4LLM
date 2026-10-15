// Cloudflare Pages Function: HTTP byte ranges (RFC 9110 §14) for the two demo recordings.
//
// Pages serves static assets with 200 and the whole file even when a request carries Range
// (https://developers.cloudflare.com/pages/configuration/serving-pages/), and Safari/WebKit only
// plays media from servers that answer ranges with 206. This Function runs ONLY for the two
// recordings: public/_routes.json limits invocation to /demo/furnace-demo.webm and
// /demo/furnace-demo.mp4; every other request (all pages, the poster, the RSC files under
// /demo/) is a static asset that never reaches it. It reads the file from the static assets
// (env.ASSETS), so nothing is stored anywhere else.
//
// Behaviour:
//   GET/HEAD without Range (or with an invalid, multi-range or stale If-Range request): 200, the
//     whole file, Accept-Ranges: bytes. (A server may ignore Range; multiple ranges are never
//     sent by media players.)
//   one satisfiable range "a-b", "a-" or "-n": 206 with exactly those bytes, Content-Range
//     "bytes a-b/size", Content-Length b-a+1.
//   unsatisfiable (first byte >= size, or "-0"): 416 with Content-Range "bytes */size".
//   other methods: passed to the static asset server unchanged.

const VIDEOS = new Set(["furnace-demo.webm", "furnace-demo.mp4"]);

/**
 * Parse a Range header against a representation of `size` bytes.
 * Returns null (ignore Range: serve 200), "unsatisfiable" (416) or {start, end} (inclusive).
 */
export function parseRange(header, size) {
  if (!header) return null;
  const m = /^\s*bytes\s*=\s*(.*)$/i.exec(header);
  if (!m) return null; // another range unit: ignore
  const specs = m[1].split(",").map((s) => s.trim()).filter(Boolean);
  if (specs.length !== 1) return null; // none, or several ranges: ignore and send the whole file
  const r = /^(\d*)-(\d*)$/.exec(specs[0]);
  if (!r || (r[1] === "" && r[2] === "")) return null; // malformed: ignore
  if (r[1] === "") {
    const suffix = Number(r[2]); // "-n": the last n bytes
    if (suffix === 0 || size === 0) return "unsatisfiable";
    return { start: Math.max(size - suffix, 0), end: size - 1 };
  }
  const start = Number(r[1]);
  if (r[2] !== "" && Number(r[2]) < start) return null; // "b-a" with b > a is invalid: ignore
  if (start >= size) return "unsatisfiable";
  const end = r[2] === "" ? size - 1 : Math.min(Number(r[2]), size - 1);
  return { start, end };
}

/** If-Range: honour the Range only when the validator still matches (strong ETag or date). */
function ifRangeAllows(ifRange, etag, lastModified) {
  if (!ifRange) return true;
  const v = ifRange.trim();
  if (v.startsWith('"')) return Boolean(etag) && !etag.startsWith("W/") && v === etag;
  return Boolean(lastModified) && v === lastModified;
}

/** Copy bytes [start, end] of `body` into a fixed-length stream (sets Content-Length). */
function slice(body, start, end, waitUntil) {
  const length = end - start + 1;
  const { readable, writable } = new FixedLengthStream(length);
  const pump = async () => {
    const reader = body.getReader();
    const writer = writable.getWriter();
    let pos = 0;
    try {
      while (pos <= end) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunkStart = pos;
        pos += value.byteLength;
        if (pos <= start) continue;
        const from = Math.max(start - chunkStart, 0);
        const to = Math.min(end + 1 - chunkStart, value.byteLength);
        await writer.write(value.subarray(from, to));
      }
      await writer.close();
    } catch (err) {
      await writer.abort(err);
    } finally {
      reader.cancel().catch(() => {});
    }
  };
  waitUntil(pump());
  return readable;
}

export async function onRequest({ request, env, params, waitUntil }) {
  const method = request.method;
  if (!VIDEOS.has(params.file) || (method !== "GET" && method !== "HEAD")) {
    return env.ASSETS.fetch(request);
  }
  // the whole file from the static assets; Range is ours to apply
  const assetUrl = new URL(request.url);
  const asset = await env.ASSETS.fetch(new Request(assetUrl.toString(), { method: "GET" }));
  if (asset.status !== 200 || !asset.body) return asset;

  // The size must be exact: from Content-Length when the asset server sends one, otherwise by
  // reading the file (at most 13 MB here) and slicing it in memory.
  const declared = asset.headers.get("content-length");
  let bytes = null; // the whole file in memory, only when no Content-Length was sent
  let size;
  if (declared !== null && /^\d+$/.test(declared)) {
    size = Number(declared);
  } else {
    bytes = new Uint8Array(await asset.arrayBuffer());
    size = bytes.byteLength;
  }
  const discard = () => {
    if (!bytes) asset.body.cancel().catch(() => {});
  };

  const headers = new Headers();
  for (const h of ["content-type", "etag", "last-modified", "cache-control", "x-content-type-options"]) {
    const v = asset.headers.get(h);
    if (v) headers.set(h, v);
  }
  headers.set("accept-ranges", "bytes");
  headers.set("x-furnace-range", "function"); // marks responses from this Function (tests check it)

  const etag = asset.headers.get("etag");
  const range = ifRangeAllows(request.headers.get("if-range"), etag, asset.headers.get("last-modified"))
    ? parseRange(request.headers.get("range"), size)
    : null;

  if (range === "unsatisfiable") {
    discard();
    headers.set("content-range", `bytes */${size}`);
    headers.delete("content-type");
    return new Response(null, { status: 416, headers });
  }
  if (range === null) {
    headers.set("content-length", String(size));
    if (method === "HEAD") {
      discard();
      return new Response(null, { status: 200, headers });
    }
    return new Response(bytes ?? asset.body, { status: 200, headers });
  }

  const { start, end } = range;
  headers.set("content-range", `bytes ${start}-${end}/${size}`);
  headers.set("content-length", String(end - start + 1));
  if (method === "HEAD") {
    discard();
    return new Response(null, { status: 206, headers });
  }
  const body = bytes ? bytes.subarray(start, end + 1) : slice(asset.body, start, end, waitUntil);
  return new Response(body, { status: 206, headers });
}
