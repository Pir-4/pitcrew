# Triage Labels

The skills speak in terms of five canonical triage roles. This file maps those roles to the actual label strings used in this repo's issue tracker.

| Label in mattpocock/skills | Label in our tracker | Meaning                                  |
| -------------------------- | -------------------- | ---------------------------------------- |
| `needs-triage`             | `needs-triage`       | Maintainer needs to evaluate this issue  |
| `needs-info`               | `needs-info`         | Waiting on reporter for more information |
| `ready-for-agent`          | `ready-for-agent`    | Fully specified, ready for an AFK agent  |
| `ready-for-human`          | `ready-for-human`    | Requires human implementation            |
| `wontfix`                  | `wontfix`            | Will not be actioned                     |

When a skill mentions a role (e.g. "apply the AFK-ready triage label"), use the corresponding label string from this table.

Edit the right-hand column to match whatever vocabulary you actually use.

## Project labels

| Label         | Meaning |
| ------------- | ------- |
| `improvement` | Out of scope for the task that surfaced it; a possible later improvement. Not planned work. |

- When work on a task surfaces something worth doing but outside its scope (a refactor, a tooling gap,
  a missing check, a doc fix), do not do it in the current change. Draft a GitLab issue labelled
  `improvement`, with `Source: GW-<n>` / the issue or MR it came from and a where / problem / proposal
  body, and create it after the human says **publish**.
- Search open `improvement` issues first (`glab issue list --label improvement --output json -P 100`);
  if one covers it, comment there instead of creating a duplicate.
- `improvement` issues are not triaged automatically. The human promotes one into work by giving it a
  triage label (usually `needs-triage` or `ready-for-agent`).
