# Night with failures

A Nightly run of Gateway on staging whose `test` job finished and whose launch holds 685
Failed tests (44 failed + 641 broken) of 6292 results, over two pages; its 95 skipped results
are not Failed tests. The 685 results are 223 test cases. Pitcrew writes them into the Rerun
test plan and creates the Rerun; the night ends there, before the Rerun's trigger.

## Nightly run

Pipeline 478951, launch 276357, nightly test plan 1387 (1675 test cases). Recorded on
2026-10-15 (job runs, Failed tests) and 2026-10-16 (result count, test plan, jobs).

## Rerun

Only what creating it answers:

- `pipeline.json`: the created pipeline, 481658. Recorded as `GET .../pipelines/481658`, a Rerun
  Pitcrew created for another night (`small_night_failing_on_rerun`): the same body as the
  create answer, and creating one again would start real tests. Pitcrew reads only its `id`.
- `test_plan.json`: the Rerun test plan 12396 as TestOps answered the write of
  `test_plan_request.json`, the body Pitcrew sends for the 223 test cases (recorded on
  2026-10-16; `testCasesCount` 223 at once, no sync needed).
