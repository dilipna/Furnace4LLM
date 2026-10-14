# Fresh-commit webhook run (2026-10-14T18:45:01+00:00)

Repository `dilipna/furnace-demo-f1`, branch made from `r1-request-id`, code eeb419a. Result: **PASS**.

| step | ok | seconds | detail |
|---|---|---|---|
| commit | True | 4.0 | `{'branch': 'webhook-recheck-20261014-1845', 'parent': '0a637d779689cc6d30a6adcd4409bf83c1c27824', 'head_sha': '49224d282d101806e2f43873a7f22ca15a839e8a'}` |
| pr | True | 3.2 | `{'number': 4, 'url': 'https://github.com/dilipna/furnace-demo-f1/pull/4', 'draft': False}` |
| delivery | True | 4.2 | `{'guid': '61c93440-c7ff-11f1-8f9e-466f538a0d5c', 'github_status_code': 200, 'delivered_at': '2026-10-14T18:45:11.023Z', 'source': 'push', 'outcome': 'queued', 'job_id': 'd09d0db6-8ae5-491a-af9e-1d97a56deafb'}` |
| redeliver_active | True | 5.8 | `{'when': 'while the job was active', 'job_status_at_redelivery': 'running', 'redelivery_status_code': 200, 'rows_before': {'delivery_rows': 1, 'jobs_for_head': 1, 'guard_jobs': 2}, 'rows_after': {'delivery_rows': 1, 'jobs_for_head': 1, 'guard_jobs': 2}}` |
| job | True | 95.2 | `{'job_id': 'd09d0db6-8ae5-491a-af9e-1d97a56deafb', 'status': 'succeeded', 'states_seen': ['running', 'succeeded'], 'attempts': 1, 'locked_by': 'BrahmaVishnuShiva-runner', 'created_at': '2026-10-14T18:45:11.304463+00:00', 'finished_at': '2026-10-14T18:46:54.193515+00:00', 'seconds': 102.889052, 'error': None, 'result': {'title': '2 regressions found: prompt_prefix_stable, chat_perf_gate', 'repair': {'reason': 'FURNACE_GUARD_AUTO_REPAIR is off', 'enqueued': False}, 'check_id': 116037356084, 'conclusion': 'failure', 'signatures': ['prefix_instability']}}` |
| check | True | 1.4 | `{'check_run_id': 116037356084, 'url': 'https://github.com/dilipna/furnace-demo-f1/runs/116037356084', 'head_sha': '49224d282d101806e2f43873a7f22ca15a839e8a', 'app': 'furnace-dev-dilipna', 'conclusion': 'failure', 'title': '2 regressions found: prompt_prefix_stable, chat_perf_gate', 'started_at': '2026-10-14T18:45:15Z', 'completed_at': '2026-10-14T18:46:53Z', 'annotations': 4}` |
| redeliver_done | True | 6.0 | `{'when': 'after the job completed', 'job_status_at_redelivery': 'succeeded', 'redelivery_status_code': 200, 'rows_before': {'delivery_rows': 1, 'jobs_for_head': 1, 'guard_jobs': 2}, 'rows_after': {'delivery_rows': 1, 'jobs_for_head': 1, 'guard_jobs': 2}}` |
| check_after_redelivery | True | 1.3 | `{'check_run_id': 116037356084, 'url': 'https://github.com/dilipna/furnace-demo-f1/runs/116037356084', 'head_sha': '49224d282d101806e2f43873a7f22ca15a839e8a', 'app': 'furnace-dev-dilipna', 'conclusion': 'failure', 'title': '2 regressions found: prompt_prefix_stable, chat_perf_gate', 'started_at': '2026-10-14T18:45:15Z', 'completed_at': '2026-10-14T18:46:53Z', 'annotations': 4}` |
