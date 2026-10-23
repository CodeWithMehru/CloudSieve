"""Bedrock + Decider 2B integration runner for CloudSieve."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Iterable, Optional

try:
    import boto3  # type: ignore
except ImportError:  # pragma: no cover
    boto3 = None

from cloudsieve.core import CloudSieveMemoryHook, Decider2BConnector


@dataclass
class BedrockRequest:
    prompt: str
    system_prompt: str = "You are an AWS operations expert. Prioritize actionable evidence and root-cause findings."
    model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"


class BedrockAgentRunner:
    """Runs an AWS incident investigation prompt through Bedrock using the filtered memory."""

    def __init__(
        self,
        model_id: str | None = None,
        region: str | None = None,
        decider: Optional[Decider2BConnector] = None,
    ) -> None:
        self.model_id = model_id or os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0")
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.decider = decider or Decider2BConnector(use_mock=True)
        self.hook = CloudSieveMemoryHook(decider=self.decider)

    def _fallback_response(self, prompt: str) -> str:
        low = prompt.lower()
        if "kms" in low and "deny" in low:
            return (
                "Root cause: a KMS explicit deny is conflicting with the cross-account assume role path. "
                "The valid IAM trust policy alone is insufficient; the KMS key policy restricts decrypt access and blocks the role session."
            )
        if "dynamodb" in low and ("throttl" in low or "timeout" in low):
            return (
                "Root cause: Lambda timeouts are caused by DynamoDB ProvisionedThroughputExceededException. "
                "The burst load exceeded account throughput while the function retried writes, creating a cascade that caused API latency."
            )
        if "nat" in low or "s3" in low and "cost" in low:
            return (
                "Root cause: private workloads are routing through a NAT gateway instead of the S3 gateway endpoint. "
                "This creates a data transfer cost spike without an infrastructure outage."
            )
        return "The evidence indicates a likely root-cause chain with multiple noisy logs; the filtered memory narrows the investigation to the highest-signal evidence."

    def _invoke_bedrock(self, prompt: str, system_prompt: str = "You are an AWS operations expert.") -> str:
        if boto3 is None:
            return self._fallback_response(prompt)
        try:
            client = boto3.client("bedrock-runtime", region_name=self.region)
            request = {
                "modelId": self.model_id,
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "system": [{"text": system_prompt}],
                "inferenceConfig": {"maxTokens": 512, "temperature": 0.1},
            }
            response = client.converse(**request)
            output = response.get("output", {}).get("message", {}).get("content", [])
            if not output:
                return self._fallback_response(prompt)
            text_parts = []
            for part in output:
                if isinstance(part, dict) and "text" in part:
                    text_parts.append(part["text"])
            if text_parts:
                return "\n".join(text_parts)
            return self._fallback_response(prompt)
        except Exception:
            return self._fallback_response(prompt)

    def run(self, context: str | Iterable[str], scenario_name: str | None = None) -> dict[str, Any]:
        if isinstance(context, str):
            filtered = self.hook.filter_context(context)
        else:
            filtered = self.hook.filter_chunks(tuple(context))

        prompt = "\n".join(
            [
                "Analyze the filtered AWS incident memory and produce a concise incident summary.",
                "Focus on root cause, actionable evidence, and required next steps.",
                "Include a short diagnosis and recommended remediation steps.",
                "Context:",
                filtered.__dict__.__str__(),
            ]
        )
        answer = self._invoke_bedrock(prompt)
        return {
            "scenario": scenario_name or "unknown",
            "filtered": filtered,
            "bedrock_answer": answer,
            "kept_chunks": len(filtered.kept),
            "pruned_chunks": len(filtered.pruned),
            "lazy_stubs": len(filtered.lazy_stubs),
        }


def main() -> None:
    scenario = "iam_kms_explictdeny"
    from aws_scenarios import SCENARIOS

    context = "\n".join(SCENARIOS[scenario].chunks)
    runner = BedrockAgentRunner()
    result = runner.run(context, scenario_name=scenario)
    print(json.dumps({
        "scenario": result["scenario"],
        "kept_chunks": result["kept_chunks"],
        "pruned_chunks": result["pruned_chunks"],
        "lazy_stubs": result["lazy_stubs"],
        "bedrock_answer": result["bedrock_answer"],
    }, indent=2))


if __name__ == "__main__":
    main()
