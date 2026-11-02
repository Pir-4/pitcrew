class AgentException(Exception):
    """Base of the errors of an Agent task that happen outside the Agent itself."""


class AgentNotConfiguredException(AgentException):
    """The service env lacks what the Agent needs, e.g. the LiteLLM key; the message names
    the variable to set."""


class GitException(AgentException):
    """Git failed to prepare a Working copy; the message holds git's own reason."""
