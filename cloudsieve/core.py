"""CloudSieve core logic.

This module implements the Decider 2B connector and the context-memory router used to
reduce noisy AWS incident context before reaching Bedrock. The design intentionally
supports both a real backend and a robust offline simulator so the project remains
usable in local development or hackathon demos without any dependency on a remotely
hosted Strands Decider 2B service.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from hashlib import sha1
from typing import Any, Iterable, Iterator, List, Mapping, Optional, Sequence, Union

try:
    import boto3  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in local mock mode
    boto3 = None

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover - optional dependency in local mock mode
    requests = None

from .reusable_pattern import (
    ContextMemoryDecisionPattern,
    DeciderChoice,
    DeciderDecision,
    GroundingChoice,
    RoutingAction,
    build_context_memory_pattern,
)


JsonLike = Union[str, Mapping[str, Any], Sequence[Any]]


@dataclass
class FilteredChunk:
    """A chunk after the decider has classified it."""

    chunk_id: str
    raw: str
    score: DeciderChoice
    grounding: GroundingChoice
    confidence: float
    action: RoutingAction
    summary: str
    routed: bool = False
    stub: Optional[str] = None


@dataclass
class CloudSieveResult:
    """Result object returned by the filtering process."""

    kept: list[FilteredChunk] = field(default_factory=list)
    pruned: list[FilteredChunk] = field(default_factory=list)
    lazy_stubs: list[FilteredChunk] = field(default_factory=list)
    total_raw_tokens: int = 0
    total_kept_tokens: int = 0
    total_pruned_tokens: int = 0
    total_lazy_tokens: int = 0
    total_saved_tokens: int = 0
    decisions: list[DeciderDecision] = field(default_factory=list)


@dataclass
class CloudSieveDecision:
    """Public alias for the decision object used by the hook and decider."""

    chunk_id: str
    score: DeciderChoice
    grounding: GroundingChoice
    confidence: float
    summary: str
    action: RoutingAction = RoutingAction.LAZY_STUB
    raw_excerpt: Optional[str] = None
    rationale: str = ""


class Decider2BConnector:
    """Connector for Strands Decider 2B with a realistic offline fallback."""

    def __init__(
        self,
        endpoint: Optional[str] = None,
        model_id: str = "strands-decider-2b",
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        use_mock: bool = True,
    ) -> None:
        self.endpoint = endpoint or os.getenv("STRANDS_DECIDER_ENDPOINT")
        self.model_id = model_id or os.getenv("STRANDS_DECIDER_MODEL_ID", "strands-decider-2b")
        self.api_key = api_key or os.getenv("STRANDS_DECIDER_API_KEY")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.use_mock = use_mock or self.endpoint is None
        self.pattern = build_context_memory_pattern()

    def _mock_decision(self, chunk: str, context: Optional[str] = None) -> DeciderDecision:
        """Offline simulator producing calibrated, realistic decisions.

        The heuristic is built to mimic production safety behavior: it weighs AWS
        incident signatures such as AccessDenied, ExplicitDeny, timeouts, throttling,
        and evidence-bearing failure states much more heavily than generic metadata.
        """

        lower = chunk.lower()
        score = DeciderChoice.BOILERPLATE_NOISE
        ground = GroundingChoice.NO
        confidence = 0.78
        rationale_bits: list[str] = []

        if re.search(r"(explicitdeny|accessdenied|kms.*deny|not authorized to perform sts:assumerole|provisionedthroughputexceededexception|task timed out|gateway timeout|deny path matched|root cause|route change|nat gateway.*cost|cost spike|data transfer.*spike)", lower):
            score = DeciderChoice.ROOT_CAUSE_EVIDENCE
            ground = GroundingChoice.YES
            confidence = 0.99
            rationale_bits.append("high-signal root-cause evidence found")
        elif re.search(r"(error|failed|exception|throttl|timeout|429|access denied|warning|not authorized|blocked|outage|spike|increase|failed|degraded)", lower):
            score = DeciderChoice.SYMPTOM_CLUE
            ground = GroundingChoice.YES
            confidence = 0.93
            rationale_bits.append("service symptom or failure state detected")
        elif re.search(r"(summary|metadata|health check|status ok|healthy|no relevant issue|maintenance window|compliance|planned change|deployment metadata|tags|region|account|arn|bucket versioning|certificate|monitoring enabled|no current|no gaps|password|identifier|retention)", lower):
            score = DeciderChoice.BACKGROUND_METADATA
            ground = GroundingChoice.NO
            confidence = 0.90
            rationale_bits.append("background metadata without actionability")
        else:
            score = DeciderChoice.BOILERPLATE_NOISE
            ground = GroundingChoice.NO
            confidence = 0.82
            rationale_bits.append("likely boilerplate or repetitive operational noise")

        if re.search(r"(kms|dynamodb|nat gateway|s3|lambda|iam|cloudtrail|cloudwatch|x-ray|sts|assumerole|security group|route table|cost explorer)", lower):
            confidence = min(0.99, confidence + 0.04)
        if re.search(r"(start|stop|resolving|investigating|next steps|summary)", lower):
            confidence = max(0.45, confidence - 0.05)

        summary = re.sub(r"\s+", " ", chunk[:160]).strip()
        decision = DeciderDecision(
            chunk_id=f"mock_{sha1(chunk.encode('utf-8')).hexdigest()[:10]}",
            score=score,
            grounding=ground,
            confidence=round(confidence, 3),
            summary=summary,
            action=RoutingAction.LAZY_STUB,
            raw_excerpt=chunk[:256],
            rationale="; ".join(rationale_bits),
        )
        return decision

    def _call_real_endpoint(self, chunk: str, context: Optional[str] = None) -> DeciderDecision:
        """Placeholder for a real Strands Decider 2B request."""

        if requests is None:
            raise RuntimeError("requests package is required for real endpoint calls")

        if not self.endpoint:
            raise ValueError("No Decider endpoint configured")

        payload = {
            "input": {"chunk": chunk, "context": context or "AWS incident investigation"},
            "model_id": self.model_id,
            "options": {
                "temperature": 0.0,
                "max_tokens": 128,
                "score_options": list(self.pattern.score_options),
                "grounding_options": list(self.pattern.grounding_options),
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = requests.post(self.endpoint, headers=headers, json=payload, timeout=10)
        response.raise_for_status()
        body = response.json()
        return DeciderDecision(
            chunk_id=body.get("chunk_id", "remote_chunk"),
            score=DeciderChoice(body.get("score", DeciderChoice.BACKGROUND_METADATA.value)),
            grounding=GroundingChoice(body.get("grounding", GroundingChoice.NO.value)),
            confidence=float(body.get("confidence", 0.7)),
            summary=str(body.get("summary", chunk[:120])),
            action=RoutingAction(body.get("action", RoutingAction.LAZY_STUB.value)),
            raw_excerpt=chunk[:256],
            rationale=str(body.get("rationale", "remote_decider_result")),
        )

    def decide_chunk(self, chunk: str, context: Optional[str] = None) -> DeciderDecision:
        """Classify a chunk and return a typed decision object."""

        if self.use_mock:
            return self._mock_decision(chunk, context)
        return self._call_real_endpoint(chunk, context)


class CloudSieveMemoryHook:
    """Hook that filters AWS context before it reaches the Bedrock model."""

    def __init__(
        self,
        decider: Optional[Decider2BConnector] = None,
        max_chunk_tokens: int = 250,
        confidence_threshold: float = 0.80,
        include_pattern: bool = True,
    ) -> None:
        self.decider = decider or Decider2BConnector(use_mock=True)
        self.max_chunk_tokens = max_chunk_tokens
        self.confidence_threshold = confidence_threshold
        self.pattern = self.decider.pattern
        self.include_pattern = include_pattern

    @staticmethod
    def _as_string(value: JsonLike) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, Mapping):
            return json.dumps(value, separators=(",", ":"), sort_keys=True)
        if isinstance(value, (list, tuple)):
            return json.dumps(value, separators=(",", ":"), sort_keys=True)
        return str(value)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(1, len(re.findall(r"\S+", text)) // 0.75)

    @staticmethod
    def _chunk_text(text: str, max_tokens: int = 250) -> list[str]:
        """Split raw incident memory into sentence-level micro-chunks.

        Large multi-turn AWS logs and policy documents are naturally multi-sentence. A
        sentence-based chunker keeps the chunk size aligned with Decider 2B's desired
        latency window while preventing root-cause signals from being diluted by the
        surrounding boilerplate.
        """

        parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]
        if not parts:
            return [text]

        chunks: list[str] = []
        for part in parts:
            words = re.findall(r"\S+", part)
            if len(words) <= max(25, max_tokens // 2):
                chunks.append(part)
                continue
            for i in range(0, len(words), max(20, max_tokens // 2)):
                chunks.append(" ".join(words[i:i + max(20, max_tokens // 2)]))
        return chunks

    @staticmethod
    def _make_stub(chunk_id: str, summary: str, confidence: float) -> str:
        return (
            f"[Stub #{chunk_id}: {summary[:80]} (conf={confidence:.2f}) - "
            f"call expand_memory_chunk('{chunk_id}') to fetch raw payload]"
        )

    def _mock_decision(self, chunk: str, context: Optional[str] = None) -> DeciderDecision:
        """Offline simulator producing calibrated, realistic decisions.

        The heuristic is built to mimic production safety behavior: it weighs AWS
        incident signatures such as AccessDenied, ExplicitDeny, timeouts, throttling,
        and evidence-bearing failure states much more heavily than generic metadata.
        """

        lower = chunk.lower()
        score = DeciderChoice.BOILERPLATE_NOISE
        ground = GroundingChoice.NO
        confidence = 0.78
        rationale_bits: list[str] = []

        if re.search(r"(explicitdeny|accessdenied|kms.*deny|not authorized to perform sts:assumerole|provisionedthroughputexceededexception|task timed out|gateway timeout|deny path matched|root cause|route change|nat gateway.*cost|cost spike|data transfer.*spike)", lower):
            score = DeciderChoice.ROOT_CAUSE_EVIDENCE
            ground = GroundingChoice.YES
            confidence = 0.99
            rationale_bits.append("high-signal root-cause evidence found")
        elif re.search(r"(error|failed|exception|throttl|timeout|429|access denied|warning|not authorized|blocked|outage|spike|increase|failed|degraded)", lower):
            score = DeciderChoice.SYMPTOM_CLUE
            ground = GroundingChoice.YES
            confidence = 0.93
            rationale_bits.append("service symptom or failure state detected")
        elif re.search(r"(summary|metadata|health check|status ok|healthy|no relevant issue|maintenance window|compliance|planned change|deployment metadata|tags|region|account|arn|bucket versioning|certificate|monitoring enabled|no current|no gaps|password|identifier|retention)", lower):
            score = DeciderChoice.BACKGROUND_METADATA
            ground = GroundingChoice.NO
            confidence = 0.90
            rationale_bits.append("background metadata without actionability")
        else:
            score = DeciderChoice.BOILERPLATE_NOISE
            ground = GroundingChoice.NO
            confidence = 0.82
            rationale_bits.append("likely boilerplate or repetitive operational noise")

        if re.search(r"(kms|dynamodb|nat gateway|s3|lambda|iam|cloudtrail|cloudwatch|x-ray|sts|assumerole|security group|route table|cost explorer)", lower):
            confidence = min(0.99, confidence + 0.04)
        if re.search(r"(start|stop|resolving|investigating|next steps|summary)", lower):
            confidence = max(0.45, confidence - 0.05)

        summary = re.sub(r"\s+", " ", chunk[:160]).strip()
        decision = DeciderDecision(
            chunk_id=f"mock_{sha1(chunk.encode('utf-8')).hexdigest()[:10]}",
            score=score,
            grounding=ground,
            confidence=round(confidence, 3),
            summary=summary,
            action=RoutingAction.LAZY_STUB,
            raw_excerpt=chunk[:256],
            rationale="; ".join(rationale_bits),
        )
        return decision

    def _route_decision(self, decision: DeciderDecision) -> FilteredChunk:
        action = RoutingAction.LAZY_STUB
        if decision.confidence >= self.confidence_threshold:
            if decision.grounding == GroundingChoice.YES or decision.score in (
                DeciderChoice.SYMPTOM_CLUE,
                DeciderChoice.ROOT_CAUSE_EVIDENCE,
            ):
                action = RoutingAction.INJECT
            elif decision.grounding == GroundingChoice.NO or decision.score in (
                DeciderChoice.BOILERPLATE_NOISE,
                DeciderChoice.BACKGROUND_METADATA,
            ):
                action = RoutingAction.PRUNE
        else:
            action = RoutingAction.LAZY_STUB

        return FilteredChunk(
            chunk_id=decision.chunk_id,
            raw=decision.raw_excerpt or decision.summary,
            score=decision.score,
            grounding=decision.grounding,
            confidence=decision.confidence,
            action=action,
            summary=decision.summary,
            stub=self._make_stub(decision.chunk_id, decision.summary, decision.confidence)
            if action == RoutingAction.LAZY_STUB
            else None,
        )

    def _process_single(self, index: int, payload: JsonLike) -> FilteredChunk:
        raw = self._as_string(payload)
        decision = self.decider.decide_chunk(raw, context=f"aws_context_memory_{index}")
        decision.chunk_id = f"chunk_{index}_{decision.chunk_id}"
        routed = self._route_decision(decision)
        return routed

    def filter_chunks(self, payloads: Iterable[JsonLike]) -> CloudSieveResult:
        """Filter a sequence of JSON-like chunks or raw strings."""

        kept: list[FilteredChunk] = []
        pruned: list[FilteredChunk] = []
        lazy_stubs: list[FilteredChunk] = []
        decisions: list[DeciderDecision] = []

        total_raw_tokens = 0
        total_kept_tokens = 0
        total_pruned_tokens = 0
        total_lazy_tokens = 0

        for index, raw in enumerate(payloads):
            item = self._as_string(raw)
            total_raw_tokens += self._estimate_tokens(item)
            decision = self.decider.decide_chunk(item, context=f"aws_context_memory_{index}")
            decision.chunk_id = f"chunk_{index}_{decision.chunk_id}"
            decisions.append(decision)
            routed = self._route_decision(decision)
            routed.raw = item
            if routed.action == RoutingAction.INJECT:
                kept.append(routed)
                total_kept_tokens += self._estimate_tokens(item)
            elif routed.action == RoutingAction.PRUNE:
                pruned.append(routed)
                total_pruned_tokens += self._estimate_tokens(item)
            else:
                lazy_stubs.append(routed)
                total_lazy_tokens += self._estimate_tokens(item)

        result = CloudSieveResult(
            kept=kept,
            pruned=pruned,
            lazy_stubs=lazy_stubs,
            total_raw_tokens=total_raw_tokens,
            total_kept_tokens=total_kept_tokens,
            total_pruned_tokens=total_pruned_tokens,
            total_lazy_tokens=total_lazy_tokens,
            decisions=decisions,
        )
        result.total_saved_tokens = max(0, total_raw_tokens - total_kept_tokens - total_lazy_tokens)
        return result

    def filter_context(self, context: Union[str, Iterable[JsonLike]]) -> CloudSieveResult:
        """Filter either a raw string or an iterable of chunks."""

        if isinstance(context, str):
            chunks = self._chunk_text(context, max_tokens=self.max_chunk_tokens)
            return self.filter_chunks(chunks)
        return self.filter_chunks(context)

    def __call__(self, context: Union[str, Iterable[JsonLike]]) -> CloudSieveResult:
        return self.filter_context(context)


def cloudsieve_filter(
    fn: Optional[Any] = None,
    *,
    hook: Optional[CloudSieveMemoryHook] = None,
) -> Any:
    """Decorator convenience for CloudSieve routing.

    Example:
        @cloudsieve_filter()
        def ingest_memory(context):
            return context
    """

    def decorator(target: Any) -> Any:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = target(*args, **kwargs)
            if hook is None:
                hook_instance = CloudSieveMemoryHook()
            else:
                hook_instance = hook
            if isinstance(result, str):
                return hook_instance.filter_context(result)
            if isinstance(result, (list, tuple)):
                return hook_instance.filter_chunks(result)
            return result

        wrapper.__name__ = getattr(target, "__name__", "cloudsieve_filter")
        wrapper.__doc__ = getattr(target, "__doc__", "")
        wrapper.__wrapped__ = target
        return wrapper

    if fn is not None:
        return decorator(fn)
    return decorator


__all__ = [
    "Decider2BConnector",
    "CloudSieveMemoryHook",
    "CloudSieveResult",
    "FilteredChunk",
    "cloudsieve_filter",
    "CloudSieveDecision",
]
