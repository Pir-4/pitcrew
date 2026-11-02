# Rerun as a GitLab pipeline on our own test plan, completion via a CI callback

Pitcrew starts a Rerun by writing the Failed tests into the Team's Rerun test plan in TestOps and
creating a `qa_automation` pipeline through the GitLab API with `TEST_PLAN_ID` set to that plan,
instead of starting a TestOps job run. Only a pipeline we create ourselves carries our settings
(`ENVIRONMENT`, `RUN_WITH_FLAGS`, `PITCREW_STEP`, the launch tag linking the Rerun to its
Nightly run), and the GitLab response gives the Rerun pipeline id at once.

What `qa_automation` declares as `spec:inputs` (`PROJECT_NAME`, `ENVIRONMENT`, `TEST_PLAN_ID`,
`NOTIFY_SLACK`, `RUN_WITH_FLAGS`, ...) goes in the pipeline's `inputs`, not as variables: its CI
reads them only as `$[[ inputs.NAME ]]`, so a variable of the same name is silently ignored and
the input default wins (`TEST_PLAN_ID=0000` runs every test). Only what is not an input
(`PITCREW_STEP`, `ALLURE_LAUNCH_TAGS`) goes as a pipeline variable.

Pitcrew learns that a pipeline finished from a CI step in `qa_automation` that calls its REST
endpoint with the Step (`night_run`, `night_rerun`), not by polling GitLab. The same step serves
the Nightly run and the Rerun, and the service holds no long-running watchers; the cost is that a
Rerun whose CI step never fires stays unfinished until the trigger is resent.
