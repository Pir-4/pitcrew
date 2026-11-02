import subprocess
from pathlib import Path

from tests.support.constants import GITLAB_URL

# `gitlab.project_path` in the repo's config/base.yaml, and the URL Pitcrew clones it from.
CLONE_URL = f"{GITLAB_URL}/gateway/qa_automation.git"
# What `qa_automation` keeps for Claude Code: knowledge the Agent loads, and settings written
# for a human that never reach the Agent's disk.
SKILL = "test-conventions"
REPO_SETTINGS = (".claude/settings.json", ".claude/settings.local.json", ".mcp.json")
# Who commits to the bare repo: a CI container has no identity git could guess.
AUTHOR = ("-c", "user.name=Test", "-c", "user.email=test@example.com")


class Origin:
    """`qa_automation` on GitLab: a local bare repo that `CLONE_URL` resolves to."""

    def __init__(self, root: Path) -> None:
        self.bare = root / "origin.git"
        self._source = root / "source"
        git("init", "--bare", "--initial-branch=master", str(self.bare))
        git("clone", str(self.bare), str(self._source))

    def commit(self, branch: str, name: str, text: str = "content\n") -> None:
        if branch not in git("branch", "--list", branch, cwd=self._source):
            git("switch", "--create", branch, cwd=self._source)
        else:
            git("switch", branch, cwd=self._source)
        (self._source / name).parent.mkdir(parents=True, exist_ok=True)
        (self._source / name).write_text(text)
        # Forced: a developer's global ignore rules may hide `.claude/settings.local.json`.
        git("add", "--force", name, cwd=self._source)
        git(*AUTHOR, "commit", "--message", f"Add {name}", cwd=self._source)
        git("push", "origin", branch, cwd=self._source)


def git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def clone_in(work_dir: Path) -> Path:
    """The persistent clone Pitcrew keeps in its working directory."""
    [git_dir] = work_dir.rglob("qa_automation/.git")
    return git_dir.parent


def worktrees(work_dir: Path) -> list[str]:
    """The paths of the clone's worktrees, the clone itself among them."""
    listing = git("worktree", "list", "--porcelain", cwd=clone_in(work_dir))
    return [
        line.removeprefix("worktree ")
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]
