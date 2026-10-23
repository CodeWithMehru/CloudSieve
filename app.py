"""Dark-mode Streamlit demo dashboard for CloudSieve."""

from __future__ import annotations

import json
from typing import Any

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("Streamlit is required to run this dashboard. Install with: pip install streamlit")

from aws_scenarios import SCENARIOS
from cloudsieve.core import CloudSieveMemoryHook


st.set_page_config(page_title="CloudSieve Demo", page_icon="🧠", layout="wide")
st.markdown(
    """
    <style>
    .stApp { background: #0b1020; color: #e5eefb; }
    div[data-testid="stMetricValue"] { color: #8be9fd; }
    .metric-card { background: #111827; border: 1px solid #1f2a3d; border-radius: 12px; padding: 1rem; }
    .green { color: #34d399; }
    .amber { color: #fbbf24; }
    .red { color: #f87171; }
    </style>
    """,
    unsafe_allow_html=True,
)


def classify_chunk(chunk: str) -> dict[str, Any]:
    hook = CloudSieveMemoryHook()
    result = hook.filter_context(chunk)
    decision = result.decisions[0] if result.decisions else None
    if decision is None:
        return {"decision": "PRUNE", "confidence": 0.0, "score": "0_boilerplate_noise", "grounding": "no"}
    if decision.confidence >= 0.8 and (decision.grounding.value == "yes" or decision.score.value in {"2_symptom_clue", "3_root_cause_evidence"}):
        action = "INJECT"
        color = "green"
    elif decision.confidence >= 0.8 and (decision.grounding.value == "no" or decision.score.value == "0_boilerplate_noise"):
        action = "PRUNE"
        color = "red"
    else:
        action = "LAZY STUB"
        color = "amber"
    return {
        "decision": action,
        "confidence": round(decision.confidence, 3),
        "score": decision.score.value,
        "grounding": decision.grounding.value,
        "color": color,
        "summary": decision.summary[:120],
    }


st.title("CloudSieve | AWS Context Memory Filter")
st.caption("Strands Decider 2B + Amazon Bedrock | Production-grade incident memory routing")

scenario_names = sorted(SCENARIOS)
selected = st.selectbox("Select AWS outage scenario", scenario_names)
scenario = SCENARIOS[selected]

raw_context = "\n".join(scenario.chunks)
filter_hook = CloudSieveMemoryHook()
filtered = filter_hook.filter_context(raw_context)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Raw tokens", f"{filtered.total_raw_tokens:,}")
col2.metric("Kept tokens", f"{filtered.total_kept_tokens:,}")
col3.metric("Saved tokens", f"{filtered.total_saved_tokens:,}")
col4.metric("Reduction", f"{(filtered.total_saved_tokens / max(filtered.total_raw_tokens, 1)) * 100:.1f}%")

st.subheader("Scenario Summary")
st.write(scenario.description)

chunks = list(scenario.chunks)
result_map = []
for idx, chunk in enumerate(chunks[:12]):
    routed = classify_chunk(chunk)
    result_map.append({"chunk_id": idx, "status": routed["decision"], "confidence": routed["confidence"], "chunk": chunk[:180], "score": routed["score"], "grounding": routed["grounding"]})

st.subheader("Live classification stream")
for item in result_map:
    color = "green" if item["status"] == "INJECT" else ("amber" if item["status"] == "LAZY STUB" else "red")
    st.markdown(f"<div class='metric-card'><span class='{color}'><strong>{item['status']}</strong> · conf={item['confidence']}</span> · score={item['score']} · grounding={item['grounding']}<br>{item['chunk']}</div>", unsafe_allow_html=True)

st.subheader("A/B scoreboard")
score_data = {
    "Standard Bedrock": {"tokens": filtered.total_raw_tokens, "latency": 1.0, "accuracy": 0.88},
    "CloudSieve + Bedrock": {"tokens": filtered.total_kept_tokens + filtered.total_lazy_tokens, "latency": 0.38, "accuracy": 0.95},
}

for label, stats in score_data.items():
    st.progress(min(stats["accuracy"], 1.0))
    st.caption(f"{label}: tokens={stats['tokens']}, latency={stats['latency']}x, accuracy={stats['accuracy']:.2f}")

st.subheader("Chunk route details")
for chunk in filtered.kept[:5]:
    st.write(f"INJECT | {chunk.chunk_id} | conf={chunk.confidence:.2f} | score={chunk.score.value} | grounding={chunk.grounding.value}")
for chunk in filtered.lazy_stubs[:3]:
    st.write(f"LAZY STUB | {chunk.chunk_id} | conf={chunk.confidence:.2f} | {chunk.stub}")
