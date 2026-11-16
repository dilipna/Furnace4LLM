# Studio local-server connection preview

This local development branch adds a connection workflow before model selection.
It has not been published, and no real model/server combination has been validated.
The connector observes HTTP responses; it does not install, load, sandbox or manage
the external server. Native research-model loading remains unimplemented. A server
can implement the protocol while running any architecture, or no model at all.
Protocol compatibility alone cannot establish model compatibility or quality.

## Try the application

From this branch's repository root, with Python 3.12 and uv installed:

```sh
uv sync --frozen
uv run furnace studio
```

Keep the terminal running and use its private session link. Open the guided example
or inspect a project, then select **Connect a local model server** in the header.
You can inspect the workflow without a model; connection and execution need a server.
Neither Docker nor a GPU is required by the connector itself. The external server
has its own dependencies and hardware requirements. Docker is still required for
the separate deterministic infrastructure fixture.

When a model is selected, supply an already-running server you operate that accepts:

- `GET /v1/models`: JSON `data` array containing the exact configured `id`.
- `POST /v1/chat/completions`: one text user message, `stream: false`, `temperature: 0`,
  and `max_tokens`. Response: the same exact `model` ID and exactly one choice with
  nonempty string `message.content` and `finish_reason` of `stop` or `length`.

Only `http://127.0.0.1:PORT/v1`, with port 1024–65535, is accepted. Studio's own port
is refused. This initial contract excludes remote hosts, hostname resolution, IPv6,
authentication, credentials, redirects, tools, multimodal messages and streaming.
An otherwise OpenAI-compatible server can still be incompatible with this subset.
Do not remove authentication from a shared server to use the preview; choose a
dedicated local test instance. No API keys belong in these forms or exports.

1. Save the URL, exact model ID and declared code/checkpoint or server revision.
   Saving does not contact the endpoint.
2. Confirm you operate the endpoint, then **Check and connect**. This reads its model
   list; it does not run inference or attest to which weights are loaded.
3. Send a sanitized text request. Inspect actual returned text, completion termination
   and client-observed round trip. This timing is not streaming TTFT.
4. Save representative cases in Workspace → Evaluations, reconnect after the edit,
   then run endpoint cases. Guided fixture expectations must be replaced with cases
   appropriate to your server. Descriptions without exact expectations stay unscored.
5. Export the kit and inspect `workspace-plan.json` → `model_endpoint`. Fixture
   evidence and provenance remain separate fields. Disconnect when finished.

## Review attempts without losing the failure

**Attempt history** retains the last ten endpoint evaluations per project, newest
first in Studio. Expand an attempt with a click or keyboard to inspect its status,
request IDs, per-case records, durations and output hashes. Opening history makes no
model request. A successful retry retains the earlier failure; retries still execute
all cases again. An attempt can be completed while containing failed or unscored cases.

History and the current result are saved together after each case and at completion.
Restart marks a partial run interrupted and retains its recorded cases. Changing
connection settings clears the current result but keeps historical attempts. Contract,
case and preference edits change the configuration identity; older attempts show
**Earlier or unbound configuration**. Restoring an earlier configuration may make its
history label match again, but does not reconnect or promote it to the current result.

Retention is by attempt start order, with the same ten-attempt limit for successes,
failures and interruptions. Starting attempt eleven expires the oldest; export the kit
beforehand to preserve a separate copy. `model_endpoint.history` contains retained
records and `history_limit` states the limit. No raw prompts/outputs or previous case
text are retained in history. Historical names/expectations are not reconstructed from
the current cases. Earlier previews' last saved run is included; already overwritten
attempts cannot be recovered, and missing original case counts stay unknown. Removing
a project removes its local history; downloaded copies remain under your control.

## Failure, identity and privacy contract

Each request has a 1–10 second deadline, including a slowly trickling body. The
response limit is 64 KiB and completion text is limited to 8000 characters. Ad-hoc
inputs are limited to 4000 characters; generated tokens to 1–256. A batch has at most
30 cases and a 30-second request budget. It stops at the first request error,
disconnect or exhausted budget. Unexecuted cases remain `not_run` in the UI.

`completed` means all requests were recorded, not that their answers passed.
Case statuses are `exact_pass`, `exact_fail`, `unscored`, `incomplete` or `error`.
Token-limit termination is incomplete even if the returned text exactly matches.
Exact equality is not semantic quality. No performance acceptance, repair verification
or architecture certification follows from these observations.

Errors mark the connection failed. Reconnect and retry explicitly; there is no hidden
retry. Retrying re-executes the cases. Each recorded case has a new local request ID.
Project ID, contract, preferences, case inputs/expectations, connection settings and
protocol version bind the observation to a SHA-256 identity. Configuration changes
invalidate readiness and prior evidence. Saved results retain their time; reloading
does not execute again. A declared revision is user input, not independent attestation
of the server's code or weights. Changing weights without updating the declaration
cannot be detected by this connector.

Application restart disconnects without making endpoint calls and marks partial runs
interrupted. Disconnect stops further requests after the in-flight bounded call and
discards that call's result. It cannot cancel generation already running externally,
stop the server or prove isolation/reset of the server's sessions.

The existing private-session token, host/origin checks and request-size limits protect
the control API. The HTTP client uses a literal IP and ignores environment proxies.
It sends no authentication, cookies or control-plane secrets. The external server is
trusted by the operator; Furnace does not audit its code, logging or network access.
Raw ad-hoc prompts/outputs are held in tab memory, not durable activity/evaluation logs.
Saved cases and expectations are stored locally and exported. Evaluation records retain
output hashes, request IDs, timings and safe error categories, not upstream error bodies.
Local workspace files and downloaded kits are not encrypted by Furnace.

## Verification and remaining gates

`apps/api/tests/test_studio_model.py` uses actual loopback HTTP test servers, not
inference. It checks wire requests, execution counts, consent refusal, safe failures,
redirect refusal, proxy bypass, deadlines, cancellation, explicit retry, truncation,
configuration identity, restart and ZIP export. Run it with:

```sh
uv run pytest apps/api/tests/test_studio_model.py -q
node --test apps/api/tests/studio-state.test.mjs
```

The installed preview now passes isolated Linux Chromium checks for connection,
requests, case evaluation, downloaded ZIP identity, late responses, overlapping
refreshes, project drafts, keyboard form navigation, reload/Back and mobile overflow.
Desktop/mobile screenshots were inspected. An older response cannot restore a deleted
project or replace a newer refresh failure/success state. Recovery clears stale errors.
The persisted-pageshow failure/recovery handler was exercised with a synthetic event;
actual BFCache use was not established. Desktop Chrome, fresh Windows/macOS installation
and other browser engines remain unverified for this connector. Automated checks do
not establish human comprehension. See the verification record for exact source/artifact.

Owner-assisted trial (leave observations blank until performed):

| Task | Actual observation | Outcome |
| --- | --- | --- |
| Explain fixture versus endpoint response versus verified model identity | | |
| Find connection prerequisites without starting a model | | |
| Save settings and explain why this does not establish readiness | | |
| With an identified server, connect, send a request and inspect its limitations | | |
| Run cases; distinguish exact failure, truncation and unscored expectations | | |
| Disconnect, restart Studio, export and explain which evidence is historical | | |

The smallest real-model validation still needed is a pinned, authorized local server,
its compatible model ID/revision, licensing and hardware prerequisites, and an
author-reviewed reference case. Confirm readiness and nonempty reference inference,
then test bad input, timeout, restart, reconnection and export against that same server.
Do not substitute the HTTP test server or historical GPU measurements for this gate.
No compute has been purchased and no model needs to be selected to review the app.

See the [verification record](local-model-endpoint-verification.md) for the exact
source, local checks, preview hash and unverified gates.
