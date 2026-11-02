from dataclasses import dataclass

from sqlalchemy.orm import Session, sessionmaker

from pitcrew.clients.gitlab import GitLabClient
from pitcrew.clients.links import WebLinks
from pitcrew.clients.slack import SlackClient
from pitcrew.clients.testops import TestOpsClient


@dataclass(frozen=True)
class StepDependencies:
    """What every Step works with, handed over by the endpoint: a new client goes here, so
    that neither the endpoint nor the Steps' constructors change."""

    session_factory: sessionmaker[Session]
    testops: TestOpsClient
    gitlab: GitLabClient
    slack: SlackClient
    links: WebLinks
