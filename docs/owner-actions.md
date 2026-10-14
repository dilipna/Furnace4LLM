# Owner actions (Dilip): what only you can do, and what each unlocks

Updated 2026-10-14. Done: demo repository `dilipna/furnace-demo-f1` created and populated
(main `bb4d918`, r1-request-id `0a637d7`); GitHub App `furnace-dev-dilipna` created and
installed on that repository only; pushes approved; live GitHub run done 2026-10-14 (attempt 2 PASS, verification 10/10; `bench/results/2026-10-14-live-github/`); fresh-commit webhook run PASS (`bench/results/2026-10-14-live-webhook/`).

| # | action | exact steps | unlocks |
|---|---|---|---|
| 1 | Vercel only, for now (about 10 min) | vercel.com → **Sign up with GitHub** (Hobby, free; no card) → Add New → Project → import `dilipna/Furnace4LLM` (give Vercel access to that one repository) → Root Directory `apps/web` → Environment Variables: `NEXT_PUBLIC_RECORDED_ONLY` = `true` (and #2 if decided) → Deploy. Then send Claude the `*.vercel.app` URL. Supabase and Render: **not needed** until hosted scans/webhooks are wanted | the public recorded site; Claude runs `scripts/smoke_hosted.py --web` and the desktop/mobile pass on it |
| 2 | Pilot contact | decide where "Ask about a pilot" goes: a `mailto:` address or LinkedIn (default: your LinkedIn profile, already working) | set `NEXT_PUBLIC_CONTACT_URL` on Vercel, then Redeploy |
| 3 | AWS (optional) | only if you have an account with credits: tell Claude, and it prepares an EC2 GPU runner guide (`g4dn.xlarge`, started only for demos) | live runs without the laptop |
| 4 | Narrated recording (optional) | record yourself over `/demo` following `docs/demo-3min.md` (3 minutes); the silent recording is already on the site | a talk-track video for investors |
| 5 | Resume | paste the two final bullets from `docs/founder/resume-bullets.md`; add the site URL to the project line once it is live | — |
| 6 | Customer conversations | 10 people who serve their own models, using `docs/founder/validation-plan.md`; Claude does not contact anyone | the evidence a fundraising conversation needs |
