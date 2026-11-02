# Error groups recognized by deterministic rules, without an LLM

Pitcrew puts a Failed test of the Rerun into an Error group only when a fixed rule on its
error text recognizes the cause with certainty (for the **model** Error kind: the first line of
the error is `pydantic_core._pydantic_core.ValidationError: N validation error(s) for <Name>`,
keyed by `<Name>` as written). The Conclusion reports only Error groups and merely counts the
Failed tests no rule recognizes. We chose this over asking an LLM to classify the failures
because these cases are simple enough to recognize statically and an LLM call per night costs
money and brings doubt into what should be certain. The LLM comes in later, to fix what an
Error group points at, and to analyse the failures no rule can tell.

## Consequences

- A new Error kind is added as a new rule, never as a looser match: a rule that is not certain
  is not a rule (e.g. the word "Model" alone also appears in value assertions and in
  `Model not found.` answers).
- A failure the rules do not know stays unreported beyond the count, even when it is obvious to
  a human; that is the price of reporting nothing uncertain.
