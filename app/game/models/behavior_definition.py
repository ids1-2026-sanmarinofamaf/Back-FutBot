from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorDefinition:
    """
    Serializable definition of a behavior.

    Stores the behavior identifier and source code that can be sent to
    worker processes and compiled locally into a RuntimeBehavior.
    """
    id: int
    code: str