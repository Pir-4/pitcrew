import pytest

from pitcrew.clients.testops import TestResult
from pitcrew.constants import TestStatus
from pitcrew.db.models.error_group import ErrorKind, NewErrorGroup, NewErrorGroupTest
from pitcrew.steps.error_groups import recognize_error_groups


def failed_test(result_id: int) -> TestResult:
    return TestResult(
        result_id=result_id,
        test_case_id=None,
        name=f"Test {result_id}",
        status=TestStatus.BROKEN,
    )


@pytest.mark.parametrize(
    ("error", "groups"),
    [
        pytest.param(
            # Launch 279328, result 11849203.
            "pydantic_core._pydantic_core.ValidationError: 1 validation error for "
            "DataResponse[RoutersOverview]\n"
            "data.supportedAssets\n"
            "  Extra inputs are not permitted [type=extra_forbidden, ...]",
            [(ErrorKind.MODEL, "DataResponse[RoutersOverview]")],
            id="one validation error, the model with its generics",
        ),
        pytest.param(
            # Launch 280791, result 11890501.
            "pydantic_core._pydantic_core.ValidationError: 5 validation errors for "
            "PoolModel\n"
            "lp_fee\n"
            "  Extra inputs are not permitted [type=extra_forbidden, ...]",
            [(ErrorKind.MODEL, "PoolModel")],
            id="several validation errors",
        ),
        pytest.param(
            # Launch 280791, result 11890501, put after blank lines.
            "\n  \n"
            "pydantic_core._pydantic_core.ValidationError: 5 validation errors for "
            "PoolModel\n",
            [(ErrorKind.MODEL, "PoolModel")],
            id="validation error after blank lines",
        ),
        pytest.param(
            # Launch 278212, result 11794980.
            'AssertionError: Wrong status code, response content {"errors":["Model not '
            'found."]}\n'
            "Diff:\n"
            "Value of root changed from 403 to 404.",
            [],
            id="look-alike: Model not found",
        ),
        pytest.param(
            # Launch 274925, result 11697644.
            "AssertionError: Assertion failed: 'value='1.12044317' "
            "currency=AssetModel(symbol='USDT', kind='jetton', decimals=6) "
            "decimals='8'' not equal to 'value='1.12044315' "
            "currency=AssetModel(symbol='USDT', kind='jetton', decimals=6) "
            "decimals='8''",
            [],
            id="look-alike: an AssetModel in a value assertion",
        ),
        pytest.param(
            # Launch 280791, result 11890501, put under a line of the test's own: the rule reads
            # the first line only.
            "AssertionError: Response does not match its schema\n"
            "pydantic_core._pydantic_core.ValidationError: 5 validation errors for "
            "PoolModel",
            [],
            id="validation error below the first line",
        ),
        pytest.param(
            # Launch 279328, result 11849204.
            "AssertionError: Wrong status code, response content "
            '{"error":"The API key header is required.","code":"api_key_required"}',
            [],
            id="plain assertion",
        ),
        pytest.param(None, [], id="no error"),
    ],
)
def test_failed_test_is_grouped_by_the_model_that_rejected_its_data(
    error: str | None, groups: list[tuple[ErrorKind, str]]
) -> None:
    recognized = recognize_error_groups([(failed_test(11849203), error)])

    assert [(group.kind, group.key) for group in recognized] == groups


def test_error_group_holds_its_tests_in_the_order_read() -> None:
    # Launch 280791; its third test is `broken` there, marked `failed` here: the rule does not
    # look at the status.
    error = (
        "pydantic_core._pydantic_core.ValidationError: 5 validation errors for "
        "PoolModel"
    )
    tests = [
        TestResult(11890502, 100830, "API: Pools list filtered by asset", TestStatus.BROKEN),
        TestResult(11890499, 122461, "API: Swap simulation rejects a request without the API key", TestStatus.FAILED),
        TestResult(11890501, 89663, "API: Pool by address returns fees and reserves", TestStatus.FAILED),
    ]  # fmt: skip
    errors = [error, "AssertionError: Wrong status code", error]

    recognized = recognize_error_groups(zip(tests, errors, strict=True))

    assert recognized == [
        NewErrorGroup(
            kind=ErrorKind.MODEL,
            key="PoolModel",
            tests=(
                NewErrorGroupTest(
                    test_result_id=11890502,
                    test_case_id=100830,
                    name="API: Pools list filtered by asset",
                ),
                NewErrorGroupTest(
                    test_result_id=11890501,
                    test_case_id=89663,
                    name="API: Pool by address returns fees and reserves",
                ),
            ),
        )
    ]


@pytest.mark.parametrize(
    ("models", "order"),
    [
        pytest.param(
            [
                "DataResponse[RoutersOverview]",
                "PoolModel",
                "PoolModel",
                "PoolModel",
            ],
            ["PoolModel", "DataResponse[RoutersOverview]"],
            id="largest first",
        ),
        pytest.param(
            [
                "DataResponse[RoutersOverview]",
                "DataResponse[PoolInfo]",
            ],
            [
                "DataResponse[PoolInfo]",
                "DataResponse[RoutersOverview]",
            ],
            id="a tie by key",
        ),
    ],
)
def test_error_groups_come_largest_first_ties_by_key(
    models: list[str], order: list[str]
) -> None:
    failed_tests = [
        (
            failed_test(result_id),
            "pydantic_core._pydantic_core.ValidationError: "
            f"1 validation error for {model}",
        )
        for result_id, model in enumerate(models)
    ]

    recognized = recognize_error_groups(failed_tests)

    assert [group.key for group in recognized] == order
