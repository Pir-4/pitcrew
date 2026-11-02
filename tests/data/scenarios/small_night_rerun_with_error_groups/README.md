# Small night, Rerun with Error groups

The Nightly run of `small_night_failing_on_rerun` (copied from there), whose Rerun has 5 Failed
tests forming two Error groups of the model kind: `PoolModel` (3 tests) and
`DataResponse[RoutersOverview]` (1), and one plain `AssertionError` left out of them.

## Nightly run

Pipeline 480974, launch 278416: see `small_night_failing_on_rerun`.

## Rerun

Played by another Rerun Pitcrew created (of the Rerun test plan 12396): pipeline 483287,
launch 280791, 5 results, all Failed, recorded on 2026-10-21. `pipeline.json` is
`GET .../pipelines/483287`, recorded on 2026-10-31. `test_results.json` holds the 5 results, each
cut down to `id`, `launchId`, `testCaseId`, `name`, `status` and `message`. `test_plan.json` is
copied from `night_with_failures` (Pitcrew reads nothing of it).
