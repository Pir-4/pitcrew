# Green night

A run without Failed tests: its `test` job finished and its launch holds 64 results, all passed.
Nothing is rerun and nothing is posted.

## Nightly run

Played by a manual run of a small plan on master: pipeline 475379, launch 273781, recorded on
2026-10-15 (job runs, Failed tests) and 2026-10-16 (result count, jobs). It ran the test plan
11765 (`TEST_PLAN_ID` in the log of its `test` job 3058543): `test_plan.json` is
`GET /api/rs/testplan/11765`, playing the nightly test plan 1387 the Team config names. It holds
1 test case; the 64 results are its parametrised runs, enough under the base config's
`broken_below_ratio`.

The plan was recorded on 2026-10-31 and modified after this night (`lastModifiedDate`), so it
may differ from what ran; its count is still consistent with the launch.
