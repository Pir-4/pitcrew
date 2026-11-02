class RunChainException(Exception):
    """Base of the errors of a Run chain transition: a Step asked the chain for a move that
    would break one of its invariants."""


class RerunAlreadyStartedException(RunChainException):
    """The Run chain has its Rerun already: a second one is refused."""
