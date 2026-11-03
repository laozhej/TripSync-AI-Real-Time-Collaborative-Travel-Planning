# Canvas synchronization verification

PRD §§1.3, 6.1, 10.2 and 13. Recorded 2026-11-03. The 100 ms threshold applies to all measured move samples in this follow-up. The original 144.23 ms socket and 133.30 ms rendered observations remain in the Phase 4 record.

The canvas groups activities by displayed day and hour once per item-list change. Each grid cell reads its own slot, and currency/date formatters are reused. The room maintenance loop checks for actual catalog contests before querying the trip and past votes. It still resolves overdue elections first. The version comparison, authorization queries and durability rules are unchanged.

| Profile | Fresh baseline P95 / max | Updated P95 / max | Updated samples at or over 100 ms |
|---|---:|---:|---:|
| Dispatch to last socket apply, 1,000 moves | 13.99 / 32.97 ms | 12.39 / 27.69 ms | 0 |
| Dispatch to both Chrome DOM updates, 200 moves | 57.40 / 78.60 ms | 42.80 / 62.40 ms | 0 |
| Dispatch through matching DOM and two animation frames, 200 moves | 79.70 / 97.50 ms | 59.90 / 96.40 ms | 0 |
| Same-version race winner through both Chrome frames, 20 races | — | 35.50 / 36.00 ms | 0 |

The initial tail miss did not recur in the fresh baseline. The updated runs show more headroom at P95. The measured maxima apply to these local runs. Socket apply spread peaked at 2.37 ms. The socket run also confirmed 20 stale races, 20 conflict notifications and aggregate equality across reconnects. The Chrome races verified a single version advance, a stale response and equal client item state.

## Reproduce

Use the disposable PostgreSQL browser runner. Close other benchmark runs before measuring. From the repository root:

```powershell
$env:BROWSER_API_PORT='8017'
$env:BROWSER_WEB_PORT='5187'
$env:BROWSER_TEST_TIMEOUT='300'
$env:MEASUREMENT_OUTPUT='evidence/performance/sync-reproduction'
.\.venv\Scripts\python.exe -u backend/tests/browser_clean_setup.py backend/tests/browser_sync_measure.py
$env:BROWSER_SERVER='sync_profile_server:app'
$env:MEASURE_BOARD_ONLY='1'
.\.venv\Scripts\python.exe -u backend/tests/browser_clean_setup.py backend/tests/phase4_measure.py
```

Run in a fresh shell with Python 3.13.1, Chrome 156.0.8078.79 and the documented local Windows/PostgreSQL setup. The runner migrates through 0012 and imports the fictional Bengaluru and Goa datasets. The same-host tests use Bengaluru and the dataset SHA-256 recorded in each socket summary. The socket test alternates two rooms with ten sockets and five identities, 20 warmup moves and 1,000 interleaved HTTP reads. It uses one process's monotonic clock. The Chrome test uses two isolated contexts, 20 warmup moves and same-host performance time origins. Its last-frame measurement includes waiting for two animation frames after each context detects matching DOM. The test-only profiler records authorization, SQL and lock wait on the server.

[Baseline socket summary](../evidence/performance/sync-baseline/summary.json) · [Baseline Chrome summary](../evidence/performance/sync-baseline/browser-summary.json) · [Grid-only Chrome run](../evidence/performance/sync-after/browser-summary.json) · [Final socket summary](../evidence/performance/sync-final/summary.json) · [Final Chrome summary](../evidence/performance/sync-final/browser-summary.json)

The runs establish the §13 move synchronization criterion for the exercised local profile. Cross-host latency, other board mutation types under sustained load and 50-distinct-planner timing remain unmeasured here. AI measurements remain in the Phase 4 record.

## Regression verification

The disposable backend suite ran with `RUN_LIVE_MODEL=1` after preloading local Qwen2.5. It passed 117 tests with one warning and zero skips in 96.18 seconds. The final frontend run passed all eight Node tests and the Vite production build. [Backend output](../evidence/tests/sync-followup-backend.txt)
