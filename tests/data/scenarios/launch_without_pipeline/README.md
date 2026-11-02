# Launch without pipeline

A launch uploaded from an IDE: TestOps holds no job run for it, so no GitLab pipeline reported
into it. A trigger naming it is rejected before any Run chain starts.

## Nightly run

Launch 277050, its job runs (none) recorded on 2026-10-15. The pipeline id is the one the trigger
claims, 478951 (the Nightly run of `night_with_failures`); nothing of it is recorded here.
