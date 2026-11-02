"""The one way a Step posts to the Team's Slack channel about a Run chain."""

from collections.abc import Callable
from dataclasses import dataclass

from pitcrew.clients.slack import SlackClient, SlackMessage
from pitcrew.config.team import FeaturesConfig, TeamConfig
from pitcrew.db.models.post import PostKind
from pitcrew.db.models.run_chain import RunChain
from pitcrew.log import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class _KindRules:
    """What the `Publisher` needs of a kind of post: the Team feature that gates it and a
    constant log phrase per event."""

    feature_on: Callable[[FeaturesConfig], bool]
    skipped: str
    already_made: str
    made: str


# The log phrases of a Conclusion read as they did before posts had kinds.
_KINDS = {
    PostKind.CONCLUSION: _KindRules(
        feature_on=lambda features: features.conclusion,
        skipped="Conclusion not posted: the Team has no Slack Conclusion",
        already_made="Conclusion already posted",
        made="Conclusion posted",
    ),
}


class Publisher:
    """Posts a message about a Run chain to its Team's channel, at most once per kind and
    key, and records the post on the chain.

    The post is recorded on the chain right after Slack accepted it, and saved by the Step
    afterwards. A Step failing in between posts it again when resumed. That is on purpose:
    a Slack webhook takes no idempotency key, so a post is either at least once or at most
    once, and a lost Conclusion is worse than a doubled one.
    """

    def __init__(self, slack: SlackClient, team_config: TeamConfig) -> None:
        """
        Args:
            slack: Where the message is posted.
            team_config: The Team's channel and features.
        """
        self._slack = slack
        self._team_config = team_config

    def publish(
        self, chain: RunChain, kind: PostKind, message: SlackMessage, key: str = ""
    ) -> bool:
        """Posts the message unless the Team has no such posts or the chain has it already.
        Neither saves the chain nor moves it on: the Step makes its own transition and saves.

        Args:
            chain: The Run chain the message is about; the post is recorded on it.
            kind: What the post is; the Team feature of the kind gates it.
            message: What is posted.
            key: Which post of the kind; empty for the Conclusion.

        Returns:
            Whether the chain has the post: `False` when the Team's feature of the kind is off
            or the Team has no Slack channel.

        Raises:
            ClientException: Slack answered an error; nothing is recorded.
        """
        slack_config = self._team_config.slack
        rules = _KINDS[kind]
        if not rules.feature_on(self._team_config.features) or slack_config is None:
            logger.info(rules.skipped)
            return False
        if chain.has_post(kind, key):
            logger.info(rules.already_made)
            return True
        self._slack.post(slack_config.webhook_variable, message)
        chain.record_post(kind, key)
        logger.info(rules.made)
        return True
