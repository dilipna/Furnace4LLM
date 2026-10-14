# First-customer validation plan (2026-10-14 to about 2026-11-15)

Goal: find out whether the problem is real and frequent for a specific kind of team, before
building more. Everything here is done by Dilip; nothing is sent automatically.

## Hypotheses, each with what would disprove it

| # | hypothesis | disproved if |
|---|---|---|
| H1 | Teams that self-host models change prompts or serving config at least every few weeks | most interviewees change them rarely, or only through a separate prompt platform |
| H2 | They have had a latency or GPU-cost regression from such a change in the last six months | fewer than 3 of 10 can name one |
| H3 | Today they find it after deploy, or by a manual benchmark that is often skipped | they already gate PRs on serving latency, or don't care about TTFT |
| H4 | They would install a GitHub App and run a runner on their GPU machine for a pilot | security or ops policy blocks both for most |
| H5 | A caught regression is worth paying for | nobody names a budget owner or a price above zero |

## Who to talk to (10 to 15 conversations)

Engineers or tech leads at small companies or teams that run an LLM feature on models they
serve themselves (vLLM, SGLang, TGI, or Ollama in production), in Python. Where to find
them, with no paid tools: people who file issues or discussions in the vLLM and SGLang
repositories about latency or prefix caching; authors of public posts about self-hosting;
the University at Buffalo and alumni networks; local AI meetups. Ask for 20 minutes to learn how they ship, not to pitch.

## Interview guide (no pitching for the first 15 minutes)

1. Walk me through the last change you made to a prompt or to serving settings. How did
   you check it before it shipped?
2. When did latency or GPU cost last surprise you? What caused it, and how did you find out?
3. What runs on a pull request today? What do you wish ran?
4. Who would care if this happened again: you, your manager, a customer?
5. (Only now) Show the three-minute demo. Then ask: what would it need to do for you to try
   it on one repository? What would stop you?
6. If it caught one of these before production, what would that be worth, and whose budget
   would pay for it?

Record answers in a simple table (one row per conversation, one column per hypothesis).

## Pilot criteria

Offer the pilot (`/pilot`) only to teams that pass the fit check. Success for a pilot:
the gate runs on at least five of their real PRs, and they tell us whether any result changed
a decision. A pilot that finds nothing is still a result, and it is written up the same way.

## Decision at the end (about 2026-11-15)

- **Continue as is** if at least 3 of 10 confirm H2 and H3, and at least 2 start a pilot.
- **Narrow or change** if the pain is real but sits somewhere else (for example, hosted-API
  prompt-cache cost rather than self-hosted latency, or quality rather than performance).
- **Stop the startup track** (keep the project as portfolio work) if fewer than 2 of 10
  have the problem.

## What not to claim while this runs

No customer names, logos, quotes or numbers without written permission. No "pilots
running" until one has started. No market size unless a source is cited and the claim is
labeled as someone else's estimate.
