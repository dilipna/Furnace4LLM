# Owner actions (Dilip): what only you can do, and what each unlocks

Updated 2026-10-14. Done: demo repository `dilipna/furnace-demo-f1` created and populated
(main `bb4d918`, r1-request-id `0a637d7`); GitHub App `furnace-dev-dilipna` created and
installed on that repository only; pushes approved; live GitHub run done 2026-10-14 (attempt 2 PASS, verification 10/10; `bench/results/2026-10-14-live-github/`).

| # | action | exact steps | unlocks |
|---|---|---|---|
| 1 | Hosting accounts (about 30 min) | create free accounts on supabase.com, render.com, vercel.com (sign in with GitHub); then tell Claude "accounts ready" and follow `docs/deploy.md` steps 1-3 together | a public URL for the site and the recorded demo; `scripts/smoke_hosted.py` then verifies it |
| 2 | Pilot contact | decide where "Ask about a pilot" goes (an e-mail address or LinkedIn); default today: LinkedIn | set as `NEXT_PUBLIC_CONTACT_URL` on Vercel |
| 3 | AWS (optional) | only if you have an account with credits: tell Claude, and it prepares an EC2 GPU runner guide (`g4dn.xlarge`, started only for demos) | live runs without the laptop |
| 4 | Narrated recording (optional) | record yourself over `/demo` following `docs/demo-3min.md` (3 minutes); the silent recording is already on the site | a talk-track video for investors |
| 5 | Resume | paste one variant from `docs/founder/resume-bullets.md` per application (the GitHub line is now verified) | — |
| 6 | Customer conversations | 10 people who serve their own models, using `docs/founder/validation-plan.md`; Claude does not contact anyone | the evidence a fundraising conversation needs |
