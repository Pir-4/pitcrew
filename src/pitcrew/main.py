from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from pitcrew.api import run_chains, triggers
from pitcrew.api.exception_handlers import EXCEPTION_HANDLERS
from pitcrew.api.middleware import RequestLogMiddleware
from pitcrew.clients.gitlab import GitLabClient
from pitcrew.clients.links import WebLinks
from pitcrew.clients.slack import SlackClient
from pitcrew.clients.testops import TestOpsClient
from pitcrew.config.settings import LogSettings, get_settings
from pitcrew.config.team import TeamConfigs
from pitcrew.db.migrate import migrate
from pitcrew.log import configure_logging, get_logger

# At import, before the startup: its errors and uvicorn's own lines are logged the same way.
_log_settings = LogSettings()
configure_logging(_log_settings.log_format, _log_settings.log_level)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Loads the Team configs, migrates the DB, opens the TestOps, GitLab and Slack
    clients and builds the web links; an invalid config, or a Slack webhook it names that is
    not set, stops the startup."""
    settings = get_settings()
    team_configs = TeamConfigs(settings.config_dir)
    app.state.team_configs = team_configs
    slack = SlackClient(
        settings,
        {
            config.slack.webhook_variable
            for config in team_configs
            if config.features.conclusion and config.slack is not None
        },
    )
    engine = create_engine(str(settings.database_url))
    migrate(engine)
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)
    app.state.testops = TestOpsClient(settings.allure)
    app.state.gitlab = GitLabClient(settings.gitlab)
    app.state.slack = slack
    app.state.links = WebLinks(settings)
    logger.info("Pitcrew started")
    yield
    app.state.slack.close()
    app.state.gitlab.close()
    app.state.testops.close()
    engine.dispose()


app = FastAPI(title="Pitcrew", lifespan=lifespan)
app.add_middleware(RequestLogMiddleware)
for exception, handler in EXCEPTION_HANDLERS.items():
    app.add_exception_handler(exception, handler)
app.include_router(triggers.router)
app.include_router(run_chains.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe for the deploy: answers as long as the process serves requests."""
    return {"status": "ok"}
