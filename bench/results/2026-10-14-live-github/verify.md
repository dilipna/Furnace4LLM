# Live GitHub verification

Repository `dilipna/furnace-demo-f1`; run record `C:\dev\furnace\bench\results\2026-10-14-live-github\live_run.json`; verified 2026-10-14T05:20:52+00:00. Result: **PASS**.

| check | result | problems | what GitHub / the receiver showed |
|---|---|---|---|
| permissions | ok | – | {"permissions": {"checks": "write", "contents": "write", "metadata": "read", "pull_requests": "write"}, "events": ["pull_request"], "repository_selection": "selected", "repositories": ["dilipna/furnace-demo-f1"]} |
| token_scope | ok | – | {"scan_token_create_branch": 403, "scan_token_create_check_run": 403, "guard_token_create_branch": 403} |
| attribution | ok | – | {"pr_head": "0a637d779689cc6d30a6adcd4409bf83c1c27824", "check_run_head": "0a637d779689cc6d30a6adcd4409bf83c1c27824", "conclusion": "failure", "furnace_check_runs_on_head": 1} |
| check_updates | ok | – | {"started_at": "2026-10-14T05:11:41Z", "completed_at": "2026-10-14T05:13:16Z", "title": "2 regressions found: prompt_prefix_stable, chat_perf_gate", "annotations": ["app/prompts.py:1 failure", "app/prompts.py:63 failure", "app/prompts.py:1 failure", "app/prompts.py:63 failure"]} |
| draft_prs | ok | – | {"pr_1": {"draft": true, "head": "furnace/forge-bb4d918", "base": "main", "by": "furnace-dev-dilipna[bot]", "url": "https://github.com/dilipna/furnace-demo-f1/pull/1"}, "pr_3": {"draft": true, "head": "furnace/repair-pr2-0a637d7", "base": "r1-request-id", "by": "furnace-dev-dilipna[bot]", "url": "https://github.com/dilipna/furnace-demo-f1/pull/3"}} |
| branches_intact | ok | – | {"main": {"before": "bb4d9186d57a05b6bb4ab0b46ab8f9c77a3d10a8", "now": "bb4d9186d57a05b6bb4ab0b46ab8f9c77a3d10a8"}, "r1-request-id": {"before": "0a637d779689cc6d30a6adcd4409bf83c1c27824", "now": "0a637d779689cc6d30a6adcd4409bf83c1c27824"}} |
| no_duplicates | ok | – | {"open_furnace_prs_by_base": {"r1-request-id": [3], "main": [1]}} |
| webhook_real_deliveries | ok | – | {"deliveries": 3, "status_codes": [200], "outcomes": ["ignored", "queued"]} |
| webhook_redelivery_noop | ok | – | {"before": [1, 1], "after": [1, 1], "redelivery_status": [200]} |
| webhook_forgery_refused | ok | – | {"unsigned": 401, "wrong secret": 401, "tampered body": 401, "valid": 202, "valid replay": 202} |
