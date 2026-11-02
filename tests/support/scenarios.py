import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tests.support.constants import SCENARIOS


@dataclass(frozen=True)
class Run:
    """One run of a night, the Nightly run or its Rerun: its ids, and the folder of what
    GitLab and TestOps answered about it."""

    directory: Path
    # What the scenario file leaves out, the run has not got as far as.
    ids: dict[str, int]

    @property
    def pipeline_id(self) -> int:
        return self.id_of("pipeline_id")

    @property
    def launch_id(self) -> int:
        return self.id_of("launch_id")

    @property
    def test_plan_id(self) -> int:
        return self.id_of("test_plan_id")

    def id_of(self, role: str) -> int:
        if role not in self.ids:
            raise LookupError(f"{self.directory} records no {role}")
        return self.ids[role]

    def recorded(self, name: str) -> Any | None:
        """The recorded answer of this name, parsed; `None` when the scenario has none."""
        path = self.directory / name
        if not path.is_file():
            return None
        return json.loads(path.read_text())


@dataclass(frozen=True)
class Night:
    """A scenario of `data/scenarios/`: one night of the Run chain, its Nightly run and,
    when recorded, its Rerun."""

    name: str
    nightly: Run
    recorded_rerun: Run | None = None

    @classmethod
    def load(cls, name: str) -> "Night":
        directory = SCENARIOS / name
        ids = json.loads((directory / "scenario.json").read_text())
        rerun = ids.get("rerun")
        return cls(
            name=name,
            nightly=Run(directory / "nightly", ids["nightly"]),
            recorded_rerun=rerun and Run(directory / "rerun", rerun),
        )

    @property
    def rerun(self) -> Run:
        if self.recorded_rerun is None:
            raise LookupError(f"Scenario {self.name} has no Rerun")
        return self.recorded_rerun

    @property
    def runs(self) -> list[Run]:
        return [run for run in (self.nightly, self.recorded_rerun) if run is not None]

    def recorded_of(self, role: str, id_: int, name: str) -> Any | None:
        """The recorded answer of this name about the run whose id of this role
        (`pipeline_id`, `launch_id`, `test_plan_id`) is `id_`; `None` when the night holds
        none."""
        run = next((run for run in self.runs if run.ids.get(role) == id_), None)
        return run.recorded(name) if run else None

    def recorded_test_result(self, result_id: int) -> Any | None:
        """A Failed test's result as a run's `test_results.json` holds it; `None` when no run
        of the night holds it."""
        for run in self.runs:
            if body := (run.recorded("test_results.json") or {}).get(str(result_id)):
                return body
        return None


# What the `load_scenario` fixture gives: a night loaded by its name.
LoadScenario = Callable[[str], Night]
