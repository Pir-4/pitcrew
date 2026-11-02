"""What the endpoints take from the app state that the startup (`main.lifespan`) prepared."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from pitcrew.clients.gitlab import GitLabClient
from pitcrew.clients.links import WebLinks
from pitcrew.clients.slack import SlackClient
from pitcrew.clients.testops import TestOpsClient
from pitcrew.config.team import TeamConfigs
from pitcrew.db.repositories.container import Repositories
from pitcrew.steps.dependencies import StepDependencies


def get_team_configs(request: Request) -> TeamConfigs:
    return request.app.state.team_configs


def get_testops(request: Request) -> TestOpsClient:
    return request.app.state.testops


def get_gitlab(request: Request) -> GitLabClient:
    return request.app.state.gitlab


def get_slack(request: Request) -> SlackClient:
    return request.app.state.slack


def get_links(request: Request) -> WebLinks:
    return request.app.state.links


def get_session_factory(request: Request) -> sessionmaker[Session]:
    return request.app.state.session_factory


def get_repositories(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
) -> Iterator[Repositories]:
    with Repositories(session_factory) as db:
        yield db


def get_step_dependencies(
    session_factory: Annotated[sessionmaker[Session], Depends(get_session_factory)],
    testops: Annotated[TestOpsClient, Depends(get_testops)],
    gitlab: Annotated[GitLabClient, Depends(get_gitlab)],
    slack: Annotated[SlackClient, Depends(get_slack)],
    links: Annotated[WebLinks, Depends(get_links)],
) -> StepDependencies:
    """Built from the getters above, so that a test overriding a client reaches the Steps."""
    return StepDependencies(session_factory, testops, gitlab, slack, links)
