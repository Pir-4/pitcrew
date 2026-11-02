import base64
from pathlib import Path

import pytest

from pitcrew.agent.working_copy import WorkingCopies
from pitcrew.config.settings import get_settings
from tests.support.constants import GITLAB_TOKEN
from tests.support.git import (
    CLONE_URL,
    REPO_SETTINGS,
    SKILL,
    Origin,
    clone_in,
    git,
    worktrees,
)
from tests.support.logs import Logs

PROJECT_PATH = "gateway/qa_automation"
# What every Agent task's Working copy is named after: its action.
NAME = "smoke"
AGENT_TASK_ID = "test-agent-task"


@pytest.fixture
def working_copies(agent_env: dict[str, str], origin: Origin) -> WorkingCopies:
    """The Working copies of `qa_automation`, cloned from `origin`."""
    return WorkingCopies(get_settings(), PROJECT_PATH)


def files_of(path: Path) -> list[str]:
    return sorted(child.name for child in path.iterdir())


def test_working_copy_is_a_worktree_of_the_ref_beside_the_clone(
    working_copies: WorkingCopies, work_dir: Path
) -> None:
    with working_copies.create("master", NAME, AGENT_TASK_ID) as working_copy:
        files = files_of(working_copy)

    assert files == [".claude", ".git", "README.md"]
    assert working_copy.is_relative_to(work_dir)
    assert working_copy != clone_in(work_dir)


def test_working_copy_of_another_branch_holds_its_files(
    working_copies: WorkingCopies, origin: Origin
) -> None:
    origin.commit("feature", "feature.md")

    with working_copies.create("feature", NAME, AGENT_TASK_ID) as working_copy:
        files = files_of(working_copy)

    assert "feature.md" in files


def test_working_copy_leaves_out_the_repos_claude_code_settings(
    working_copies: WorkingCopies, work_dir: Path
) -> None:
    with working_copies.create("master", NAME, AGENT_TASK_ID) as working_copy:
        present = [name for name in REPO_SETTINGS if (working_copy / name).exists()]
        skill = (working_copy / ".claude/skills" / SKILL / "SKILL.md").is_file()
        status = git("status", "--porcelain", cwd=working_copy)

    assert (present, skill, status) == ([], True, "")
    # The clone stays whole: a worktree without the sparse setting has the files.
    whole = work_dir / "whole"
    git("worktree", "add", "--detach", str(whole), "HEAD", cwd=clone_in(work_dir))
    assert all((whole / name).is_file() for name in REPO_SETTINGS)


def test_working_copy_is_removed_after_the_agent_task(
    working_copies: WorkingCopies, work_dir: Path
) -> None:
    with working_copies.create("master", NAME, AGENT_TASK_ID) as working_copy:
        pass

    assert not working_copy.exists()
    assert worktrees(work_dir) == [str(clone_in(work_dir))]


def test_working_copy_is_removed_when_the_agent_fails(
    working_copies: WorkingCopies, work_dir: Path
) -> None:
    with (
        pytest.raises(RuntimeError),
        working_copies.create("master", NAME, AGENT_TASK_ID) as working_copy,
    ):
        raise RuntimeError("The Agent's process died")

    assert not working_copy.exists()
    assert worktrees(work_dir) == [str(clone_in(work_dir))]


def test_second_working_copy_fetches_into_the_existing_clone(
    working_copies: WorkingCopies, origin: Origin, work_dir: Path, logs: Logs
) -> None:
    with working_copies.create("master", NAME, AGENT_TASK_ID):
        clone = clone_in(work_dir)
    origin.commit("master", "new_test.py")

    with working_copies.create("master", NAME, AGENT_TASK_ID) as working_copy:
        files = files_of(working_copy)

    assert "new_test.py" in files
    assert clone_in(work_dir) == clone
    assert logs.messages().count("Clone created") == 1
    assert logs.messages().count("Clone fetched") == 1


def test_working_copies_of_a_name_share_the_path(
    working_copies: WorkingCopies,
) -> None:
    # Claude Code keeps the sessions of a Working copy by its path: one place, found again.
    with working_copies.create("master", NAME, AGENT_TASK_ID) as first:
        pass

    with working_copies.create("master", NAME, AGENT_TASK_ID) as second:
        pass

    assert first == second


def test_working_copy_left_by_a_killed_process_is_replaced(
    working_copies: WorkingCopies, work_dir: Path, logs: Logs
) -> None:
    with working_copies.create("master", NAME, AGENT_TASK_ID) as left:
        pass
    git("worktree", "add", "--detach", str(left), "HEAD", cwd=clone_in(work_dir))
    (left / "half_done.py").write_text("left by the killed task\n")

    with working_copies.create("master", NAME, AGENT_TASK_ID) as working_copy:
        files = files_of(working_copy)

    assert files == [".claude", ".git", "README.md"]
    assert worktrees(work_dir) == [str(clone_in(work_dir))]
    assert "Stale Working copy removed" in logs.messages()


def test_gitlab_token_reaches_neither_the_log_nor_the_clone(
    working_copies: WorkingCopies, work_dir: Path, logs: Logs
) -> None:
    with working_copies.create("master", NAME, AGENT_TASK_ID):
        pass
    with working_copies.create("master", NAME, AGENT_TASK_ID):
        pass

    basic_auth = base64.b64encode(f"oauth2:{GITLAB_TOKEN}".encode()).decode()
    git_config = (clone_in(work_dir) / ".git" / "config").read_text()
    for secret in (GITLAB_TOKEN, basic_auth):
        assert secret not in logs.text
        assert secret not in git_config
    assert CLONE_URL in git_config
