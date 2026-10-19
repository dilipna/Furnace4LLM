# Browser prompt-prefix checker

Open <https://furnace-5h6.pages.dev/prefix-check>. No account or GPU is needed.
Choose **Try a regression** to see request metadata shorten the shared prefix, then
**Try the repair** to see the effect of moving it after stable instructions.
These are synthetic examples, computed by the same function used for pasted input.

For your own application, render two snapshots with the same distinct final user questions
in the same order. Paste base and head as JSONL, then choose **Compare prefixes**.
Each line is a request object with a nonempty `messages` array, for example:

```jsonl
{"messages":[{"role":"system","content":"Use the operations runbook. Check service health before restarting."},{"role":"user","content":"Why is the service slow?"}]}
{"messages":[{"role":"system","content":"Use the operations runbook. Check service health before restarting."},{"role":"user","content":"How should I investigate errors?"}]}
```

Only string role/content fields are supported, with a final nonempty user message.
Multimodal content, duplicate questions, mismatched question sequences, malformed JSON,
more than 200 requests, fewer than two requests, and snapshots exceeding 2 MiB UTF-8
are rejected. Additional request metadata fields are ignored.

The checker serializes each message as `role + newline + content + newline`, then finds
the minimum shared leading Unicode character count across requests. The head passes
when it retains at least `floor(base_shared_chars * 0.9)`. A baseline that does not
meaningfully extend beyond its initial role label is inconclusive. Character counts
are not token counts. Editing either textarea clears stale results.

The browser implementation is tested against all twelve recorded outputs of the actual
Python Forge prefix test in `experiments/prefix-cache/guard-replay.json`, including Unicode,
input errors, and the cache-disabled condition. Run from `apps/web` with Node 24:

```bash
node --test lib/prefix-check.test.mjs
```

Prompt text stays in React state/browser memory. There is no upload, model call, application
logging, or browser storage in this tool. **Clear prompts** removes it from the page state;
Furnace cannot control browser extensions, clipboard tools, or browser recovery features.

This is a structural check. A PASS does not establish cache hits, lower latency, or equivalent
answers; caching disabled on the server is invisible to it. Real serving measurements need
the [experiment runner](../experiments/prefix-cache/README.md). Repository scanning, GPU
benchmarking, and hosted Guard execution remain unavailable on the public static site.
