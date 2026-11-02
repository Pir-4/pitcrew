# Small night failing on Rerun

A Nightly run with two Failed tests (test cases 122461, 124669) of 106 results; both fail again
on the Rerun (results 11849203, 11849204): one rejected by the model
`DataResponse[RoutersOverview]`, one on a plain `AssertionError`. Two of two failing
again is no sign of a down Environment: the Rerun is not broken. The test rejected by the model
is `broken`, not `failed`: Allure marks `failed` only an `AssertionError`, so no recorded model
error is on a `failed` test, and the Error group rule does not look at the status.

## Nightly run

Played by a manual run of a branch: pipeline 480974, launch 278416, recorded on 2026-10-19. It
ran the test plan 11066 (`TEST_PLAN_ID` in the log of its `test` job 3100032): `test_plan.json`
is `GET /api/rs/testplan/11066`, playing the nightly test plan 1387 the Team config names. It
holds 3 test cases; the 106 results are their parametrised runs, enough under the base config's
`broken_below_ratio`.

The plan was recorded on 2026-10-31 and modified after this night (`lastModifiedDate`), so it
may differ from what ran; its count is still consistent with the launch.

## Rerun

The Rerun Pitcrew created for launch 278416: pipeline 481658, launch 279328, recorded on
2026-10-19. `pipeline.json` is `GET .../pipelines/481658`, the same body as the create answer.
`test_results.json` holds the two results, each cut down to `id`, `launchId`, `testCaseId`,
`name`, `status` and `message`. `test_plan.json`, the answer to writing the Rerun test plan, is
copied from `night_with_failures` (Pitcrew reads nothing of it).
