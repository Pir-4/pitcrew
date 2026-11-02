"""Working copies of the test repo: Pitcrew keeps one persistent clone in its working
directory and gives each Agent task a worktree of it at the ref the task needs (ADR 0005)."""

import base64
import os
import shutil
import subprocess
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from pitcrew.agent.exceptions import GitException
from pitcrew.config.settings import Settings
from pitcrew.log import Stopwatch, get_logger, log_scope, mask_secrets

logger = get_logger(__name__)

# The remote of the clone; a branch of the test repo is `origin/<branch>` in it.
REMOTE = "origin"

# The test repo's Claude Code settings, written for a human with credentials the service lacks:
# left out of every Working copy, so Claude Code never loads them (ADR 0005). A new settings
# file Claude Code reads from the project goes here.
EXCLUDED_FILES = (
    "/.claude/settings.json",
    "/.claude/settings.local.json",
    "/.mcp.json",
)


class WorkingCopies:
    """The clone of one test repo under `<work dir>/repos/<project path>` and its Working
    copies under `<work dir>/working_copies/<name>`. Git runs as an external
    process; the GitLab token reaches it through the process environment only, never through
    the remote URL or the git config on disk.

    A Working copy is a sparse worktree without `EXCLUDED_FILES`: they are absent on disk but
    not deleted for git, so `git status` is clean and a commit cannot remove them. The sparse
    setting is the worktree's own (`extensions.worktreeConfig`), so the clone stays whole."""

    def __init__(self, settings: Settings, project_path: str) -> None:
        """Prepares the paths and git's credentials; touches nothing on disk yet.

        Args:
            settings: The GitLab URL and token, and the work dir that holds the clone and the
                Working copies.
            project_path: The test repo on GitLab, e.g. `gateway/qa_automation`.
        """
        gitlab_url = str(settings.gitlab.url).rstrip("/")
        self._url = f"{gitlab_url}/{project_path}.git"
        # Absolute: git runs in the clone, and Claude Code keys sessions by the path.
        work_dir = settings.work_dir.resolve()
        self._clone = work_dir / "repos" / project_path
        self._working_copies = work_dir / "working_copies"
        # GitLab takes a token as the password of HTTP basic auth, whatever the user name.
        credentials = f"oauth2:{settings.gitlab.token.get_secret_value()}"
        basic_auth = base64.b64encode(credentials.encode()).decode()
        mask_secrets([basic_auth])
        self._auth = {
            f"http.{gitlab_url}/.extraHeader": f"Authorization: Basic {basic_auth}"
        }

    @contextmanager
    def create(self, ref: str, name: str, agent_task_id: str) -> Generator[Path]:
        """A Working copy at `ref` (a branch of the test repo, a tag or a commit), with the
        clone fetched first; removed when the Agent task ends, also on failure.

        `name` says what the Working copy is for and stays the same for the work an Agent
        task continues: Claude Code keeps the sessions of a Working copy by its path, so a
        session is resumed in, and its transcript kept under, the same path. Two Agent tasks
        running at once never share a name; a Working copy of the name left by a killed
        process is replaced.

        Args:
            ref: A branch of the test repo, a tag or a commit.
            name: What the Working copy is for; its directory under `working_copies/`.
            agent_task_id: The Agent task the Working copy is for, in the log lines.

        Yields:
            The path of the Working copy.

        Raises:
            GitException: The clone could not be fetched, or `ref` does not exist.
        """
        with log_scope(agent_task_id=agent_task_id, working_copy=name):
            path = self._working_copies / name
            if path.exists():
                shutil.rmtree(path)
                logger.warning("Stale Working copy removed")
            self._update_clone()
            commit = self._resolve(ref)
            self._add_sparse(path, commit)
            logger.info("Working copy created", ref=ref, commit=commit)
            try:
                yield path
            finally:
                self._remove(path)

    def _add_sparse(self, path: Path, commit: str) -> None:
        """Adds the worktree empty, sets what it leaves out, then checks out `commit`: the
        excluded files never reach the disk."""
        self._git("worktree", "add", "--no-checkout", "--detach", str(path), commit)
        exclusions = [f"!{name}" for name in EXCLUDED_FILES]
        self._git("sparse-checkout", "set", "--no-cone", "/*", *exclusions, cwd=path)
        self._git("checkout", "--detach", commit, cwd=path)

    def _remove(self, path: Path) -> None:
        """Logs a failure instead of raising it: it must not hide the Agent task's own."""
        try:
            self._git("worktree", "remove", "--force", str(path))
        except GitException:
            logger.exception("Working copy not removed", path=str(path))
        else:
            logger.info("Working copy removed")

    def _update_clone(self) -> None:
        stopwatch = Stopwatch()
        if (self._clone / ".git").is_dir():
            self._git("fetch", "--prune", "--tags", REMOTE, authenticated=True)
            # Forgets the Working copies a killed process left without removing them.
            self._git("worktree", "prune")
            self._enable_worktree_config()
            logger.info("Clone fetched", duration_ms=stopwatch.ms)
            return
        self._clone.parent.mkdir(parents=True, exist_ok=True)
        self._git(
            "clone",
            "--no-checkout",
            "--origin",
            REMOTE,
            self._url,
            str(self._clone),
            cwd=self._clone.parent,
            authenticated=True,
        )
        self._enable_worktree_config()
        logger.info("Clone created", url=self._url, duration_ms=stopwatch.ms)

    def _enable_worktree_config(self) -> None:
        """The sparse setting of a Working copy goes into that worktree's own config, not the
        clone's. Also set on a fetch: a clone made before Working copies were sparse lacks it."""
        self._git("config", "extensions.worktreeConfig", "true")

    def _resolve(self, ref: str) -> str:
        """The commit of a branch as the remote has it, else of a tag or a commit."""
        for candidate in (f"refs/remotes/{REMOTE}/{ref}", ref):
            commit = self._git(
                "rev-parse",
                "--verify",
                "--quiet",
                f"{candidate}^{{commit}}",
                check=False,
            )
            if commit:
                return commit
        raise GitException(f"No branch, tag or commit {ref!r} in {self._url}")

    def _git(
        self,
        *args: str,
        cwd: Path | None = None,
        authenticated: bool = False,
        check: bool = True,
    ) -> str:
        """Runs git and returns its stdout stripped; its output is logged line by line."""
        env = os.environ | {"GIT_TERMINAL_PROMPT": "0"}
        if authenticated:
            env |= _config_env(env, self._auth)
        logger.debug("Git started", git_args=list(args))
        process = subprocess.run(
            ["git", *args],
            cwd=cwd or self._clone,
            env=env,
            capture_output=True,
            text=True,
        )
        for line in (process.stdout + process.stderr).splitlines():
            logger.debug("Git output", line=line)
        if check and process.returncode != 0:
            raise GitException(
                f"git {args[0]} failed with exit code {process.returncode}: "
                f"{process.stderr.strip()}"
            )
        return process.stdout.strip() if process.returncode == 0 else ""


def _config_env(env: dict[str, str], config: dict[str, str]) -> dict[str, str]:
    """Git config of one process, added after what the environment already sets there."""
    start = int(env.get("GIT_CONFIG_COUNT", "0"))
    added = {"GIT_CONFIG_COUNT": str(start + len(config))}
    for index, (key, value) in enumerate(config.items(), start):
        added[f"GIT_CONFIG_KEY_{index}"] = key
        added[f"GIT_CONFIG_VALUE_{index}"] = value
    return added
