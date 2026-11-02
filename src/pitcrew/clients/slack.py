"""Slack through incoming webhooks: one per Team channel, posting is all they do."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx2 as httpx

from pitcrew.clients.base import BaseClient
from pitcrew.config.settings import Settings


@dataclass(frozen=True)
class SlackMessage:
    """A Block Kit message, ready to post.

    Attributes:
        text: Stands for the message in notifications.
        blocks: The Block Kit blocks of the message.
    """

    text: str
    blocks: Sequence[Mapping[str, Any]]


class SlackClient(BaseClient):
    """Posts to the webhooks the Team configs name by their variable. A webhook URL is the
    secret itself, so the variable stands for it in every error."""

    def __init__(
        self,
        settings: Settings,
        webhook_variables: Iterable[str],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        """Reads every webhook up front, so that a missing one stops the startup.

        Args:
            settings: Where the webhooks are read from, by their variables.
            webhook_variables: The variables the Team configs name, e.g.
                `SLACK_WEBHOOK_GATEWAY`.
            transport: A faked transport serving recorded responses, for the tests.

        Raises:
            ValueError: A variable is not set.
        """
        webhooks = {}
        for variable in webhook_variables:
            webhook = settings.secret(variable)
            if webhook is None:
                raise ValueError(
                    f"{variable} is not set: a Team config posts its Conclusion there"
                )
            webhooks[variable] = webhook.get_secret_value()
        self._webhooks = webhooks
        # Every webhook is a full URL of its own.
        super().__init__(base_url="", headers={}, transport=transport)

    def post(self, webhook_variable: str, message: SlackMessage) -> None:
        """Posts a Block Kit message. Slack answers in plain text, so the answer is not read.

        Args:
            webhook_variable: The variable of the channel's webhook, as the Team config names
                it.
            message: What is posted.

        Raises:
            ClientException: Slack answered an error, with its reason, e.g. `invalid_blocks`.
        """
        self._send(
            "POST",
            self._webhooks[webhook_variable],
            json={"text": message.text, "blocks": list(message.blocks)},
        )

    def _error_url(self, request: httpx.Request) -> str:
        url = str(request.url)
        for variable, webhook in self._webhooks.items():
            if url == webhook:
                return f"${variable}"
        return "<a Slack webhook>"
