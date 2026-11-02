"""The process environment of Claude Code: built from `Settings` alone, so that nothing of a
developer's `~/.claude` (settings, plugins, memory, login) and none of the service's own
secrets reaches the Agent (ADR 0005)."""

import os

from pitcrew.agent.exceptions import AgentNotConfiguredException
from pitcrew.config.settings import Settings

# Variables of the service's own environment Claude Code still gets: what finding programs,
# the locale and the corporate proxy and its CA need. The SDK passes Claude Code the whole
# environment of the service, its secrets among them, so every other variable is blanked.
INHERITED_VARIABLES = frozenset(
    {
        "PATH",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "TMPDIR",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "NODE_EXTRA_CA_CERTS",
        "HTTPS_PROXY",
        "HTTP_PROXY",
        "NO_PROXY",
        "https_proxy",
        "http_proxy",
        "no_proxy",
    }
)


class AgentEnvironment:
    """Claude Code reaches LiteLLM with the service's key and keeps its state (sessions) in
    `claude/` under the working directory, with its `HOME` in `home/` beside it."""

    def __init__(self, settings: Settings) -> None:
        """Builds the env from the settings alone.

        Args:
            settings: The LiteLLM URL and key, and the work dir that holds Claude Code's state
                and `HOME`.

        Raises:
            AgentNotConfiguredException: `LITELLM_KEY` is not set.
        """
        if settings.litellm.key is None or not settings.litellm.key.get_secret_value():
            raise AgentNotConfiguredException(
                "LITELLM_KEY is not set: the Agent reaches its model through LiteLLM "
                "with this key (make create-service-env)"
            )
        work_dir = settings.work_dir.resolve()
        self._claude_config_dir = work_dir / "claude"
        self._home = work_dir / "home"
        self.base_url = str(settings.litellm.url).rstrip("/")
        self._env = {
            "ANTHROPIC_BASE_URL": self.base_url,
            "ANTHROPIC_AUTH_TOKEN": settings.litellm.key.get_secret_value(),
            "CLAUDE_CONFIG_DIR": str(self._claude_config_dir),
            "HOME": str(self._home),
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        }

    def for_model(self, model: str) -> dict[str, str]:
        """The whole environment Claude Code gets for an Agent task: the service's variables
        blanked but for `INHERITED_VARIABLES`, then the Agent's. Every variable of the service
        is named, so the SDK, merging it over the service's own, adds nothing. Its directories
        are created when missing, e.g. on a wiped volume.

        Args:
            model: The model of the task, as LiteLLM names it.
        """
        self._claude_config_dir.mkdir(parents=True, exist_ok=True)
        self._home.mkdir(parents=True, exist_ok=True)
        service = {
            name: value if name in INHERITED_VARIABLES else ""
            for name, value in os.environ.items()
        }
        return service | self._env | {"ANTHROPIC_MODEL": model}
