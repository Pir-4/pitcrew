"""The Conclusions of the tests as a person reads them in Slack (see `AGENTS.md` here)."""

# A Nightly run whose `test` job is green, but whose launch holds a single result.
BROKEN_NIGHT_RUN_TOO_FEW_RESULTS = """\
:rotating_light: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 0 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/473215|Pipeline 473215> · <https://testops.example/launch/271942|Launch 271942>
---
Nightly run is broken, no Rerun: 1 result out of ~1675 expected."""

# A Nightly run whose pipeline stopped before its results were read: no Failed test count.
BROKEN_NIGHT_RUN_PIPELINE = """\
:rotating_light: *[Pitcrew] Gateway · staging*
---
*Nightly run*
<https://gitlab.example/gateway/qa_automation/-/pipelines/476973|Pipeline 476973> · <https://testops.example/launch/275171|Launch 275171>
---
Nightly run is broken, no Rerun: pipeline canceled at stage test."""

# night_with_failures under a Team that allows 10% of Failed tests: 11% failed.
BROKEN_NIGHT_RUN_TOO_MANY_FAILURES = """\
:rotating_light: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 685 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/478951|Pipeline 478951> · <https://testops.example/launch/276357|Launch 276357>
---
Nightly run is broken, no Rerun: too many failures, likely an environment problem: 685 of 6292 results failed."""

BROKEN_RERUN = """\
:rotating_light: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 685 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/478951|Pipeline 478951> · <https://testops.example/launch/276357|Launch 276357>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
Rerun is broken: 2 results out of ~223 expected. The 685 Failed tests of the Nightly run are not confirmed."""

GREEN_RERUN = """\
:white_check_mark: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 0 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/475379|Pipeline 475379> · <https://testops.example/launch/273781|Launch 273781>"""

# The Team does not recognize Error groups: the Failed tests are only counted.
RERUN_WITHOUT_ERROR_GROUPS = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/launch/279328|2 Failed tests still failing> on the Rerun"""

RERUN_WITH_NO_ERROR_GROUPS = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
No Error groups: <https://testops.example/launch/279328|2 Failed tests>, cause not determined"""

# One of the two Failed tests is in a group, the other one is counted as the rest.
RERUN_WITH_AN_ERROR_GROUP_AND_THE_REST = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/project/3/test-cases?search=id in [124669]|DataResponse[RoutersOverview]> · 1 Failed test: <https://testops.example/launch/279328/tree/11849203|#124669>
<https://testops.example/launch/279328|1 more Failed test>, cause not determined"""

# Launch 280791 as the Rerun: two groups listed largest first, then the rest.
RERUN_WITH_TWO_ERROR_GROUPS = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 5 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/483287|Pipeline 483287> · <https://testops.example/launch/280791|Launch 280791>
---
<https://testops.example/project/3/test-cases?search=id in [89663, 100830, 106459]|PoolModel> · 3 Failed tests: <https://testops.example/launch/280791/tree/11890501|#89663>, <https://testops.example/launch/280791/tree/11890502|#100830>, <https://testops.example/launch/280791/tree/11890503|#106459>
<https://testops.example/project/3/test-cases?search=id in [124669]|DataResponse[RoutersOverview]> · 1 Failed test: <https://testops.example/launch/280791/tree/11890500|#124669>
<https://testops.example/launch/280791|1 more Failed test>, cause not determined"""

# A group of 6 tests lists no test cases, only its link; every Failed test is in it, so no
# line counts the rest.
RERUN_WITH_A_GROUP_OF_MORE_THAN_5_TESTS = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 6 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/project/3/test-cases?search=id in [98115, 98116, 98117]|LpPositionsV2Model> · 6 Failed tests"""

# No test of the group has a test case: the group links the Rerun launch, its tests are named.
RERUN_WITH_A_GROUP_WITHOUT_TEST_CASES = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/launch/279328|PoolModel> · 2 Failed tests: <https://testops.example/launch/279328/tree/11849203|API: pools list>, <https://testops.example/launch/279328/tree/11849204|API: pool by address>"""

# One test of the group has no test case: it is named, and the group's link searches the
# other one's test case only.
RERUN_WITH_A_TEST_WITHOUT_A_TEST_CASE = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/project/3/test-cases?search=id in [124669]|PoolModel> · 2 Failed tests: <https://testops.example/launch/279328/tree/11849203|#124669>, <https://testops.example/launch/279328/tree/11849204|API: pool by address>"""

# 11 groups: the first 10 listed, the 11th summed up, then the rest.
RERUN_WITH_11_ERROR_GROUPS = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 70 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/project/3/test-cases?search=id in [1]|PaginatedResponse[list[FarmsList]]> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [2]|DataResponse[Config]> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [3]|SwapCreatedNsqModel> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [4]|OperationsV3Model> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [5]|SwapConfirmedNsqModel> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [6]|PoolsInfoResponse> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [7]|PoolModel> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [8]|LpPositionsV2Model> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [9]|OperationsInfoResponse> · 6 Failed tests
<https://testops.example/project/3/test-cases?search=id in [10]|DataResponse[RoutersOverview]> · 6 Failed tests
… and 1 more group (1 test)
<https://testops.example/launch/279328|9 more Failed tests>, cause not determined"""

# `&`, `<` and `>` of a group's key and of a test's name are escaped: Slack reads them as markup.
RERUN_ESCAPED = """\
:x: *[Pitcrew] Gateway · staging*
---
*Nightly run* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/480974|Pipeline 480974> · <https://testops.example/launch/278416|Launch 278416>
*Rerun* · 2 Failed tests
<https://gitlab.example/gateway/qa_automation/-/pipelines/481658|Pipeline 481658> · <https://testops.example/launch/279328|Launch 279328>
---
<https://testops.example/launch/279328|Page&lt;Pool&gt; &amp; Co> · 1 Failed test: <https://testops.example/launch/279328/tree/11849203|API: a &lt;b&gt; &amp; c>
<https://testops.example/launch/279328|1 more Failed test>, cause not determined"""
