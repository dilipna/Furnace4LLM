# RQ1: reconstruction accuracy

Deterministic reconstruction only (LLM synthesis is not built, so no +LLM ablation). F1 is the development fixture; held-out apps were labeled from source before their first scan (labels: `bench/ground_truth/`, written by the developer agent, not yet independently reviewed).

## Micro-averaged P / R / F1

| category | F1 (dev) | held-out set 1 | held-out set 2 | held-out set 3 | held-out set 4 | held-out set 5 |
| --- | --- | --- | --- | --- | --- | --- |
| routes | – | – | – | – | – | 1.00 / 1.00 / 1.00 (5/5p/5t) |
| llm_call_sites | – | – | – | – | – | – / 0.00 / 0.00 (0/0p/3t) |
| models | – | – | – | – | – | – / 0.00 / 0.00 (0/0p/2t) |
| serving_engines | – | – | – | – | – | – / 0.00 / 0.00 (0/0p/1t) |
| retrievers | – | – | – | – | – | n/a |
| tools | – | – | – | – | – | – / 0.00 / 0.00 (0/0p/11t) |
| prompts | – | – | – | – | – | – / 0.00 / 0.00 (0/0p/8t) |
| workflows | – | – | – | – | – | – / 0.00 / 0.00 (0/0p/1t) |
| contradictions | – | – | – | – | – | n/a |

Attribute accuracy (held-out-5): 7/7 (a scan that finds nothing scores 7/7 on the same truth)

## Per app

### openai-cs-agents-demo (held-out-5, scan 0.9s)

| category | P / R / F1 (tp/pred/truth) | missed | false positives |
| --- | --- | --- | --- |
| routes | 1.00 / 1.00 / 1.00 (5/5p/5t) | – | – |
| llm_call_sites | – / 0.00 / 0.00 (0/0p/3t) | python-backend/server.py::AirlineServer.respond; python-backend/airline/guardrails.py::relevance_guardrail; python-backend/airline/guardrails.py::jailbreak_guardrail | – |
| models | – / 0.00 / 0.00 (0/0p/2t) | gpt-5.2; gpt-4.1-mini | – |
| serving_engines | – / 0.00 / 0.00 (0/0p/1t) | openai | – |
| retrievers | n/a | – | – |
| tools | – / 0.00 / 0.00 (0/0p/11t) | faq_lookup_tool; get_trip_details; update_seat; flight_status_tool; baggage_tool; get_matching_flights; book_new_flight; assign_special_service_seat; issue_compensation; display_seat_map; cancel_flight | – |
| prompts | – / 0.00 / 0.00 (0/0p/8t) | python-backend/airline/agents.py::seat_services_instructions; python-backend/airline/agents.py::flight_information_instructions; python-backend/airline/agents.py::booking_cancellation_instructions; python-backend/airline/agents.py::refunds_compensation_instructions; python-backend/airline/agents.py::faq_agent; python-backend/airline/agents.py::triage_agent; python-backend/airline/guardrails.py::guardrail_agent; python-backend/airline/guardrails.py::jailbreak_guardrail_agent | – |
| workflows | – / 0.00 / 0.00 (0/0p/1t) | POST /chatkit | – |
| contradictions | n/a | – | – |

Attributes correct: 7/7

## Confidence calibration (all apps)

ECE = 0.400 over n = 1 decidable claims.

| confidence bin | n | mean confidence | accuracy |
| --- | ---: | ---: | ---: |
| [0.6, 0.8) | 1 | 0.60 | 1.00 |
