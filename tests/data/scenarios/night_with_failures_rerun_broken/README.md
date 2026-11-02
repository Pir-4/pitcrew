# Night with failures, Rerun broken

The Nightly run of `night_with_failures` (copied from there): 685 Failed tests, 223 test cases
in the Rerun test plan. Its Rerun's `test` job finished, but the Rerun launch holds 2 results
of the ~223 expected: the Rerun is broken, and the 685 Failed tests are not confirmed.

## Nightly run

Pipeline 478951, launch 276357, nightly test plan 1387: see `night_with_failures`.

## Rerun

Played by the recorded Rerun of another night, `small_night_failing_on_rerun`: pipeline 481658,
launch 279328 (2 results, both Failed), recorded on 2026-10-19. No Rerun of launch 276357 was
recorded: it would rerun 223 test cases on a real Environment. The created pipeline and the
written Rerun test plan are those of `night_with_failures`.
