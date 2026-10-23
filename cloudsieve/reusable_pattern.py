"""Reusable #context-memory decision pattern for Strands Decider 2B.

This module is intentionally self-contained and can be reused in other orchestration
agents. It defines a typed decision template that asks a decider to answer two
questions for each chunk of context or tool output:

1) Importance score: how critical is the chunk for completing the current task?
2) Grounding check: does the chunk contain actionable state, constraint, or evidence?

The pattern is designed to be used before large tool outputs and episodic memories are
added to the LLM prompt, reducing token bloat while preserving ambiguous but possibly
important evidence behind lazy pointer stubs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Iterable, Optional


class DeciderChoice(str, Enum):
    """Importance score values from boilerplate to root-cause evidence."""

    BOILERPLATE_NOISE = "0_boilerplate_noise"
    BACKGROUND_METADATA = "1_background_metadata"
    SYMPTOM_CLUE = "2_symptom_clue"
    ROOT_CAUSE_EVIDENCE = "3_root_cause_evidence"


class GroundingChoice(str, Enum):
    """Actionability answer: whether a chunk contains actionable evidence."""

    YES = "yes"
    NO = "no"


class RoutingAction(str, Enum):
    """Final routing action for a chunk given decider output and confidence."""

    INJECT = "inject"
    PRUNE = "prune"
    LAZY_STUB = "lazy_stub"


@dataclass(frozen=True)
class ContextMemoryDecisionPattern:
    """Type-safe prompt definition for the reusable #context-memory pattern."""

    pattern_name: str = "#context-memory"
    question_score: str = (
        "How critical is this chunk for resolving the active AWS engineering task?"
    )
    score_options: tuple[str, ...] = (
        DeciderChoice.BOILERPLATE_NOISE.value,
        DeciderChoice.BACKGROUND_METADATA.value,
        DeciderChoice.SYMPTOM_CLUE.value,
        DeciderChoice.ROOT_CAUSE_EVIDENCE.value,
    )
    question_grounding: str = (
        "Does this chunk contain actionable failure state, constraint, or root-cause evidence?"
    )
    grounding_options: tuple[str, ...] = (
        GroundingChoice.YES.value,
        GroundingChoice.NO.value,
    )
    confidence_threshold: float = 0.80
    scoring_policy: str = (
        "Score 2-3 or yes with confidence >= 0.80 -> INJECT. "
        "Score 0 or no with confidence >= 0.80 -> PRUNE. "
        "Otherwise -> LAZY_STUB."
    )
    lazy_stub_template: str = (
        "[Stub #{id}: {summary} (conf={conf}) - call expand_memory_chunk('{id}') to fetch raw payload]"
    )


@dataclass
class DeciderDecision:
    """Concrete decision emitted for a chunk by the decider model or simulator."""

    chunk_id: str
    score: DeciderChoice
    grounding: GroundingChoice
    confidence: float
    summary: str
    action: RoutingAction = RoutingAction.LAZY_STUB
    raw_excerpt: Optional[str] = None
    rationale: str = ""


def build_context_memory_pattern() -> ContextMemoryDecisionPattern:
    """Return the reusable #context-memory decision pattern metadata."""

    return ContextMemoryDecisionPattern()


def cloudsieve_filter(
    func: Optional[Callable[..., Any]] = None,
    *,
    filter_name: str = "cloudsieve_filter",
) -> Callable[..., Any]:
    """Decorator to wrap an agent method and route large tool outputs through the pattern.

    Example:
        @cloudsieve_filter()
        def on_tool_output(raw_context):
            return raw_context
    """

    def decorator(target: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return target(*args, **kwargs)

        wrapper.__name__ = getattr(target, "__name__", filter_name)
        wrapper.__doc__ = getattr(target, "__doc__", "")
        wrapper.__annotations__ = getattr(target, "__annotations__", {})
        wrapper.__wrapped__ = target
        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


__all__ = [
    "DeciderChoice",
    "GroundingChoice",
    "RoutingAction",
    "ContextMemoryDecisionPattern",
    "DeciderDecision",
    "build_context_memory_pattern",
    "cloudsieve_filter",
]
