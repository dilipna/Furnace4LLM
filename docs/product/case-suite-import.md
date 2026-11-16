# Import evaluation cases into Studio

In a saved project, open **Evaluations → Import an evaluation suite**. This workflow
works without Docker or a model. It prepares cases; it does not execute them.

1. Choose a sanitized UTF-8 JSONL file: one case object per line, up to 30 cases and
   64 KiB. Blank lines, UTF-8 BOM and CRLF line endings are supported. A starter kit's
   `evaluation-cases.example.jsonl` can be imported directly.
2. Inspect the local preview. It lists names and whether each case has an exact
   expectation or stays descriptive/unscored. Nothing has been saved or uploaded.
3. Choose **Replace saved cases with preview** to replace the complete saved suite
   for this project. Replacement is explicit; it does not append or execute cases.
   Use **Discard import preview** to leave saved cases unchanged.
4. Existing result labels from imported files are discarded. Saved cases start
   `not_run`. Changing their inputs/expectations invalidates prior evaluation identity;
   retained endpoint attempts remain in history with their configuration labels.
5. Run the selected fixture or endpoint explicitly when its prerequisites are ready.
   Importing a label never establishes execution, answer quality or model support.

Example file (the expected string is an assertion, not a measured model baseline):

```jsonl
{"name":"Exact fixture example","input":"hello","expected_behavior":"Deterministic fixture prefixes uppercase text","expected_output":"framework:HELLO"}
{"name":"Researcher-reviewed behavior","input":"sanitized example input","expected_behavior":"Describe what an author should assess"}
```

Required string fields are `name` (1–100 Unicode code points), `input` and
`expected_behavior` (1–4000 each). Optional `expected_output` is a string of up to
8000 code points or null. Missing/null output expectations are unscored; an empty
string is an exact expectation. Whitespace is preserved. The fields `status` and
`recorded_status` are accepted only to support exported files and are discarded.
Other fields, invalid JSON/UTF-8, invalid field types and unpaired Unicode surrogates
are rejected. Errors identify the line and field without echoing malformed content.

The normalized save request, including its configuration precondition, must also fit
the existing 64 KiB control-API body limit. A file near the size limit can therefore
require fewer/shorter cases. No limit or evaluation acceptance rule was loosened.

## Changes while previewing

Previews belong to the project in which the file was selected. Switching projects,
late file reads and selecting another file cannot apply the earlier preview to a
different project. An unsaved preview stays in this tab and triggers the existing
close/reload warning. It is not durable across browser closure. Discarding it is a
local operation available even when saved state cannot be reconfirmed.

The preview captures the project identity for contract, compute preferences and
case inputs. Replacement sends that SHA-256 to the existing case API. The service
checks it after acquiring the project lock; a concurrent relevant edit causes HTTP
409 and leaves the saved cases untouched. Refresh saved state, then choose the file
again. Running fixture workers must be stopped before editing. These checks serialize
with endpoint work; they do not cancel generation already running in an external server.

Previewing reads the chosen file in the browser and never executes/imports its code.
Explicit replacement sends the normalized case fields to this machine's private Studio
API. Saved inputs/expectations are stored locally and included in kit exports; they
are not encrypted by Furnace. Use sanitized inputs and do not import secrets.

See the [verification record](case-suite-import-verification.md) for exact source,
installed-browser checks and remaining limitations.
