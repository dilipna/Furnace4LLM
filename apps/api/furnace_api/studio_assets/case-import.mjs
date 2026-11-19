// Pure, bounded parsing. Imported status labels never become execution evidence.
export const MAX_CASE_FILE_BYTES = 65536;
const limits = {name:100, input:4000, expected_behavior:4000, expected_output:8000};
const allowed = new Set([...Object.keys(limits), "status", "recorded_status", "scoring"]);
const methods = new Set(["exact", "normalized", "contains", "regex", "numeric", "choice", "json_fields"]);
export function parseCaseSuite(bytes) {
  if (bytes.byteLength > MAX_CASE_FILE_BYTES) throw new Error("The case file exceeds 64 KiB.");
  let source;
  try { source = new TextDecoder("utf-8", {fatal:true}).decode(bytes); }
  catch { throw new Error("The case file must contain valid UTF-8 text."); }
  const cases = [];
  let discardedStatuses = 0;
  for (const [index, line] of source.split(/\r\n|\r|\n/).entries()) {
    if (!line.trim()) continue;
    const fail = message => { throw new Error("Line " + (index + 1) + ": " + message); };
    if (cases.length >= 30) fail("a suite can contain at most 30 cases.");
    let item;
    try { item = JSON.parse(line); } catch { fail("invalid JSON object."); }
    if (!item || typeof item !== "object" || Array.isArray(item)) fail("expected one case object.");
    if (Object.keys(item).some(key => !allowed.has(key))) fail("unsupported field; use the documented case format.");
    const result = {};
    for (const [key, limit] of Object.entries(limits)) {
      const value = item[key];
      if (key === "expected_output" && value == null) { result[key] = null; continue; }
      if (typeof value !== "string") fail(key + " must be a string.");
      const characters = [...value];
      if (characters.length > limit || (key !== "expected_output" && !characters.length)) fail(key + " has an invalid length (maximum " + limit + ").");
      if (characters.some(char => { const point = char.codePointAt(0); return point >= 0xd800 && point <= 0xdfff; })) fail(key + " contains an invalid Unicode character.");
      result[key] = value; // Exact whitespace and empty exact expectations are significant.
    }
    if (item.scoring != null) {
      // Shape check only; Studio validates the complete rule before saving.
      if (typeof item.scoring !== "object" || Array.isArray(item.scoring) || !methods.has(item.scoring.method)) fail("scoring must be an object with a supported method.");
      result.scoring = item.scoring;
    }
    if (Object.hasOwn(item, "status") || Object.hasOwn(item, "recorded_status")) discardedStatuses++;
    cases.push(result);
  }
  if (!cases.length) throw new Error("No cases found. Use one JSON object per line.");
  const request = {cases, expected_configuration_sha256:"0".repeat(64)};
  if (new TextEncoder().encode(JSON.stringify(request)).byteLength > 65536) throw new Error("The normalized suite exceeds the 64 KiB save limit. Import fewer or shorter cases.");
  return {cases, discardedStatuses};
}
