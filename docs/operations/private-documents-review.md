# Private-document preview review

Draft only. This is separate from the unchanged November 24 Studio walkthrough.
Nothing here records human participation or approves publication.

## Open the two previews

The existing Studio walkthrough stays at http://127.0.0.1:4010.
The new document website is at http://127.0.0.1:4011 while the local server runs.
From the built `product/private-site` checkout, restart the latter with:

```powershell
python scripts/preview_site.py --port 4011
```

The server needs `apps/web/out` from the static build. Locally staged installer and
recording files are ignored, not supplied by a fresh checkout or published online.
Stage an actual completed recording with
`python scripts/stage_everyday_recording.py C:\path\to\real-document-recording`
before rebuilding the static site. The input directory must include its real
`record.json`, video and screenshots; never substitute a scripted adapter for footage.

## Website comprehension (no Docker required)

Ask the participant to work without reading implementation details. Record their
words, confusion and assistance; do not infer understanding from clicks alone.

1. What does Furnace help you do? Who might use it?
2. Watch the example. Is it recorded, live, or a scripted test? What supports that answer?
3. What does the privacy receipt check? Can the rest of the computer access the internet?
4. Does privacy mean the answer is correct? Find the complete model results.
5. Can this machine run the app? Find the OS, Docker and model requirements.
6. Find the download and your next step. Do not install during this task unless agreed.

| Observation | Actual feedback | Assistance provided |
| --- | --- | --- |
| Purpose | | |
| Recorded versus live | | |
| Privacy boundary and answer quality | | |
| Compatibility | | |
| Next action | | |

## Installed document app (separate developer task)

Prerequisites: Windows x64, unsigned candidate approval, Docker Desktop with Linux
containers and about 8 GB available to Docker, disk space for the app/model, internet
for preparation. NVIDIA validation additionally needs a supported driver and GPU;
CPU is available. Installation/SmartScreen observations belong to the separate
[clean-account checklist](clean-account-install.md).

Use a synthetic document, not a personal medical, legal, financial or client file.
Approve model preparation/start explicitly, import a document, request a summary,
compare facts against the original, inspect the receipt and its limits, then clear.
Try a question whose answer is absent. Record incorrect answers as failures.
Open Advanced, return, then quit using the app window; closing a browser is not Quit.

| Observation | Actual result | Error / assistance |
| --- | --- | --- |
| Prepare/start | | |
| Extraction and answer correctness | | |
| Missing-information behavior | | |
| Receipt understood | | |
| Clear / Advanced / Quit | | |

## Release gates

- Latest selected installer must pass fresh installed-runtime acceptance; recordings and installed confirmations must retain their own source identities.
  Earlier `2c250d6` records remain historical.
- Review the [model comparison](../product/model-comparison.md) and separate historical
  re-scoring. The owner selected Qwen3 for compatible NVIDIA GPUs and Qwen1.5 for CPU/faster
  use. Remaining wrong answers and the Qwen3 CPU timeout remain; eight fixed attacks do
  not establish general injection resistance. No professional-advice suitability is claimed.
- Human observations, clean-account install/keep/delete, licensing/legal review and
  explicit owner merge/publication decisions remain outstanding.
- Local site evidence is in `docs/product/verification/private-site`: first Lighthouse
  result 84/100/100, later 97/100/100. These are separate uncontrolled observations;
  neither proves that one code change caused the difference.

No feedback has been collected by this sheet. Browser automation is not human evidence.
