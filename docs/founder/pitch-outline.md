# Investor pitch outline (for later; not for fundraising now)

Use this for an advisor, an accelerator application, or an investor who asks to see the
thinking. It is ten slides at most. The ask at this stage is introductions and design
partners, not money (see "the ask"). Every figure comes from `docs/founder/brief.md`; do not
add market sizes, traction or quotes that have not happened.

1. **Problem.** Teams that serve their own models change prompts and serving config often
   (how often is a hypothesis the interviews test).
   Some of them silently remove the server's prompt-cache reuse or raise time to first token.
   Answers don't change, so answer-quality checks pass, and the cost shows up in production
   unless someone benchmarks the server before merge.
   *Show:* the landing panel's diff and the 98% → 0% cache hit.

2. **Why now (argued, not measured).** More teams self-host open-weight models; serving
   engines (vLLM, SGLang) reuse prompt prefixes automatically, so prompt structure now affects
   latency and GPU cost directly. Hosted APIs price cached prefixes differently too. This is
   a hypothesis about the market, not a figure.

3. **Product.** A GitHub check for serving performance. It renders each revision's real
   prompts, measures main and the PR interleaved on the team's server, decides with a 90%
   interval, and drafts a tested fix for a supported regression. A human merges.
   *Show:* the three-minute demo.

4. **How it's different (honestly).** Eval platforms (promptfoo, Braintrust, LangSmith)
   score answers and also record latency; promptfoo can assert a per-call latency threshold.
   Code-benchmark CI (CodSpeed) times Python functions. Monitoring sees production. Furnace
   is one packaged workflow: both revisions' real prompts, interleaved on the team's own
   server, an interval decision, prefix-cache hit rate, the responsible line, and a fix
   checked by the same gate. It complements eval tools. There is no moat yet; the candidates
   are the validated measurement method and pilot data on which regressions happen.

5. **Evidence so far.** 0/36 false alarms on unchanged code; the known regression blocked
   6/6; repair verified in 3/3 repeated trials of one scenario; and the limits, stated: small
   regressions left undecided 15/18, one fixture, one GPU. One live run on a public GitHub
   repository (check run, draft fix, verification 10/10).

6. **Customer and first use.** A small team on self-hosted vLLM. First session: baseline, one
   real PR checked, a repair if one applies. Still to validate (slide 9).

7. **Business model (hypotheses).** A per-repository subscription for the hosted control
   plane, with the runner on the customer's machine; setup and support early on. Not priced
   with anyone yet.

8. **Costs.** Near zero today (laptop, free tiers). The customer's GPU runs the benchmarks:
   about 85 s per Guard run and about 200 s per repair attempt on the laptop.

9. **What we're learning next.** How often teams hit this; whether a caught regression is
   worth paying for; whether onboarding can drop from a hand-written suite file to minutes;
   whether results hold on production-size models and servers.

10. **The ask.** Introductions to teams that self-host models in production; feedback on
    whether the problem is real for them.

## Before any fundraising slide is credible

Pilots on real repositories with an outcome (caught something, or did not); several teams
describing the problem unprompted; and one price someone has agreed to pay. Until then,
present this as a validated technical prototype looking for design partners.
