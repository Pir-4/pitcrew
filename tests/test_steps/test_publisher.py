from collections.abc import Iterator

import pytest

from pitcrew.clients.slack import SlackClient, SlackMessage
from pitcrew.config.settings import get_settings
from pitcrew.config.team import FeaturesConfig, TeamConfig
from pitcrew.constants import Environment
from pitcrew.db.models.post import PostKind
from pitcrew.db.models.run import Run, RunKind
from pitcrew.db.models.run_chain import RunChain
from pitcrew.steps.publisher import Publisher
from tests.support.config import load_team_config
from tests.support.constants import SLACK_WEBHOOK_VARIABLE
from tests.support.fakes import FakeSlack

GATEWAY = load_team_config("gateway")
MESSAGE = SlackMessage(
    text="[Pitcrew] Gateway · staging",
    blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": "*Nightly run*"}}],
)


@pytest.fixture
def slack_client(slack: FakeSlack) -> Iterator[SlackClient]:
    """The service's Slack client in front of the faked Slack."""
    client = SlackClient(
        get_settings(), [SLACK_WEBHOOK_VARIABLE], transport=slack.transport
    )
    yield client
    client.close()


def night_run() -> RunChain:
    """A Run chain of Gateway on staging, with no post yet."""
    return RunChain(
        team="Gateway",
        environment=Environment.STAGING,
        runs=[Run(kind=RunKind.NIGHTLY, pipeline_id=473215, launch_id=271942)],
    )


def test_a_message_is_posted_and_recorded(
    slack_client: SlackClient, slack: FakeSlack
) -> None:
    chain = night_run()

    published = Publisher(slack_client, GATEWAY).publish(
        chain, PostKind.CONCLUSION, MESSAGE
    )

    assert published is True
    assert slack.posted == [
        {
            "text": "[Pitcrew] Gateway · staging",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": "*Nightly run*"}}
            ],
        }
    ]
    assert chain.has_post(PostKind.CONCLUSION)


def test_a_message_the_chain_has_is_not_posted_again(
    slack_client: SlackClient, slack: FakeSlack
) -> None:
    chain = night_run()
    chain.record_post(PostKind.CONCLUSION)

    published = Publisher(slack_client, GATEWAY).publish(
        chain, PostKind.CONCLUSION, MESSAGE
    )

    assert published is True
    assert slack.posted == []
    assert len(chain.posts) == 1


@pytest.mark.parametrize(
    "team_config",
    [
        pytest.param(
            GATEWAY.model_copy(
                update={"features": FeaturesConfig(rerun=True, conclusion=False)}
            ),
            id="the Team has no Conclusion feature",
        ),
        pytest.param(
            # Not a valid Team config: startup refuses it (tests/test_config/test_startup.py).
            GATEWAY.model_copy(update={"slack": None}),
            id="the Team has no Slack channel",
        ),
    ],
)
def test_a_message_is_not_posted_for_a_team_without_the_post(
    slack_client: SlackClient, slack: FakeSlack, team_config: TeamConfig
) -> None:
    chain = night_run()

    published = Publisher(slack_client, team_config).publish(
        chain, PostKind.CONCLUSION, MESSAGE
    )

    assert published is False
    assert slack.posted == []
    assert chain.posts == []
