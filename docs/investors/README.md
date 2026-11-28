# Furnace investor room — private review draft

Furnace gives model researchers a free infrastructure kit and local Studio to run,
evaluate, observe and recover a model. Furnace operating that infrastructure on
customer or Furnace compute is a proposed paid service. The document assistant is
an example application, not a change of market or product.

Prepared November 27, 2026. No outreach, waitlist, service, spending or publication
is activated here. This branch is docs-only against main; some evidence describes
unmerged candidates. Copies retain original bytes and [provenance](provenance.json).
The December 4 local release and private demonstration take precedence.

## Contents

- [One-page memo](memo.md), [deck outline and notes](deck.md).
- [Evidence room](evidence-room.md), [known limitations](known-limitations.md).
- [Market](market.md), [why now](why-now.md), [competition](competition.md).
- [Economics](unit-economics.md), [expansion](expansion.md), [FAQ](faq.md).
- [Video scripts](video-scripts.md), [design-partner kit](design-partners.md).
- [Demand/privacy proposal](demand-measurement.md), [adapter proof status](adapter-proof.md).
- [All owner placeholders](owner-inputs.md).

## Verify

From a checkout with Python installed; no additional dependency:

```sh
python docs/investors/check_evidence.py
python docs/investors/test_check_evidence.py
python docs/investors/check_evidence.py --online
```

Offline checks validate copied bytes, JSON pointers, arithmetic, deck/memo numerical
claims and local links. Online mode checks external URLs and source excerpts.
A network error or bot challenge fails; offline success does not establish live-link
verification. [Actual verification](verification.md).

The validator is an editing guard, not fact checking or proof of demand. Human review
owns claim interpretation. Passing arithmetic does not validate assumptions. Do not
replace an installed result with a better source-checkout trial.
