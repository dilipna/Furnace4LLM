# Pilot discovery checklist

Do not lead with a feature demo. Ask for one concrete recent change and how it was judged.
No interviews have been conducted as part of preparing this checklist.

- How do you currently detect latency regressions? Who notices them and when?
- Which changes most often cause them: prompts, retrieval, model, serving settings, traffic?
- What do you benchmark before merging, with which inputs and concurrency?
- How much manual work does that require? Ask for observed steps/time rather than an estimate of savings.
- What result would make Furnace useful enough to keep using?
- Which endpoint/server/version do you control? Can it be isolated from production load?
- Is the application Python, with sliceable prompt construction and reproducible tests?
- May the App read this repository and write checks? Who can consent to a draft PR?
- Which representative sanitized questions and known-good revision can be used?
- What would make an INCONCLUSIVE result actionable? What uncertainty is unacceptable?
- Who will review changes to model-visible metadata and semantic behavior?
- What data may stay in logs, for how long, and who handles deletion/revocation?
- What would cause you to stop this pilot immediately?

Record answers, objections and refusal reasons verbatim where consent permits. Do not
turn this checklist into fabricated feedback, testimonials or an adoption claim.
