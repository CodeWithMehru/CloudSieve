"""Realistic AWS outage scenarios for CloudSieve benchmarking.

Each scenario contains noisy operational context, a small number of ambiguous chunks,
and a few hidden root-cause findings that must survive the decider filter.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    chunks: tuple[str, ...]


def _scenario_one() -> Scenario:
    chunks = (
        "AWS account 986743204111 - maintenance window summary: no planned change to IAM trust policy for prod-app-us-east-1.",
        "CloudTrail event summary: AssumeRoleCall success for role arn:aws:iam::444444444444:role/prod-ops-admin on 2026-10-22T22:11:45Z.",
        "CloudTrail event summary: AccessKeyId ASIA... recovered from 2024-07-10 by internal developer last rotated 2 days ago.",
        "ACM certificate details: certificate arn:aws:acm:us-east-1:986743204111:certificate/8692abef-9014-4681-8f80-5ef0cb59705a is valid through 2030-10-01.",
        "IAM user alice has mfa enabled and last used policy statement S3:GetObject for us-east-1 on 2026-10-21.",
        "EC2 instance i-0ba0ddd2e9a75abba is in subnet subnet-0aa2215d9a2ca53bc with status ok and monitoring enabled.",
        "ALB target group tg-prodapi-443 has 6 healthy targets and 0 unhealthy targets at 22:12 UTC.",
        "KMS key alias alias/prod-ssm-key is scheduled for rotation in 90 days under AWS managed rotation policy.",
        "IAM policy evaluation: inline policy for role app-prod-reader on account 986743204111 includes sts:AssumeRole on resource arn:aws:iam::*:role/prod-reader.",
        "CloudWatch log stream /aws/lambda/prod-syncer generated 1,098 log entries in the last 15 minutes with no ERROR patterns.",
        "S3 bucket prod-ops-archive has bucket versioning enabled and lifecycle rule for 30-day retention active.",
        "CloudWatch alarm PROD-EC2-CPU-High state OK, previous state OK, evaluation 0.00 datums in not enough data.",
        "IAM Access Analyzer findings: no external role trust issues detected in prod account for the last 7 days.",
        "Status of VPC flow logs: logs are delivered to arn:aws:logs:us-east-1:986743204111:log-group:prod-flow-logs with no gaps in the 24 hour period.",
        "App deployment metadata: commit SHA 2cf19373f, environment prod, region us-east-1, service app, deployment count 31.",
        "KMS key policy statement: Sid KMS-ExplicitDeny-Prod, Effect Deny, Principal *, Action kms:Decrypt, Resource *, Condition StringNotEquals aws:PrincipalArn arn:aws:iam::112233445566:role/prod-decryptor.",
        "Cross-account IAM trust from account 112233445566 to account 986743204111: role prod-decryptor assumes role app-prod-reader with session tags {team:platform, environment:prod}.",
        "Service control policy details: all accounts in organizational unit platform-production have default deny for kms:Decrypt without an explicit allow list.",
        "RDS cluster prod-db-01 is in availability zone us-east-1a with 99.95% availability and no current failover pending.",
        "AWS Config rule compliance summary: IAM role trust relationships compliant; 0 noncompliant rules for audit period.",
        "CloudTrail insight event: unusual activity volume for AssumeRole API on role app-prod-reader in account 986743204111 at 22:12 UTC.",
        "IAM role trust policy fragment: Statement { Effect Allow, Principal AWS arn:aws:iam::112233445566:role/prod-decryptor, Action sts:AssumeRole, Resource arn:aws:iam::986743204111:role/app-prod-reader }.",
        "Explicit API failure: User is not authorized to perform sts:AssumeRole on resource arn:aws:iam::986743204111:role/app-prod-reader because a KMS key policy explicit deny is applied.",
        "Server team runbook: production rotation checklist, page 23 of 31, step 5 validate KMS access for new account.",
        "SNS topic prod-platform-notifications has message retention 1209600 seconds and subscribers 3 with no current delivery failures.",
        "CloudTrail event metadata: event source iam.amazonaws.com, event name AssumeRole, request id 05e1b38a-7f3d-41a5-a9b2-2d938ad1c3c9.",
        "IDP federation status: Okta SSO running with 2 active sessions; no auth failures on the identity provider side.",
        "IAM AWS managed policy DataScientistAccess has no effect on this production role and is suppressed as a false positive in the audit report.",
        "Audit log detail: role assumption failed after 3 retries; error message AccessDenied: User is not authorized to perform sts:AssumeRole on resource arn:aws:iam::986743204111:role/app-prod-reader.",
        "Customer-facing API error: 429 Too Many Requests due to upstream identity token validation and role assumption retries from app-prod-reader.",
        "STS endpoint metadata: region us-east-1, service endpoint sts.us-east-1.amazonaws.com, certificate age 365 days, no relevant issue.",
        "Security group sg-0a85bd9cb6af48d1d allows 443 inbound from VPN only; no ingress drift detected.",
        "KMS policy condition: StringNotEquals aws:PrincipalArn arn:aws:iam::112233445566:role/prod-decryptor caused the deny path to match even after cross-account trust policy was valid.",
        "Root cause evidence: a cross-account assume role path was valid but the KMS key policy ExplicitDeny override blocked decrypt access, causing all downstream app tokens to fail.",
        "Summary of issue: customers cannot fetch production data because app-prod-reader cannot assume the target role after KMS-denied decrypt path.",
    )
    return Scenario(
        name="Scenario 1: Cross-Account IAM and KMS ExplicitDeny",
        description="IAM role trust is valid, but KMS key policy deny blocks cross-account AssumeRole downstream decrypt flow.",
        chunks=chunks,
    )


def _scenario_two() -> Scenario:
    chunks = (
        "CloudWatch dashboard PROD/API-High-Latency shows p99 latency 4.8s for public API endpoints with 2.1k requests/min at 15:32 UTC.",
        "Lambda function prod-etl-processor runtime 3,176 ms average with 34% cold starts from the last 30 minutes.",
        "DynamoDB table app-prod-events has 1,200,000 writes/day and provisioned throughput is set to 18000 WCU; recent growth exceeded baseline at 15:33 UTC.",
        "X-Ray trace summary: 70% of requests to /extract route time out after 3s in the Lambda invocation step.",
        "CloudWatch logs /aws/lambda/prod-etl-processor: REPORT Duration 2976 ms Billed Duration 3000 ms Memory Size 2048 MB.",
        "Lambda error log: Task timed out after 3.00 seconds; client error code 504 Gateway Timeout from API Gateway.",
        "DynamoDB service metrics: Throttling events: 182, RequestLimitExceeded 16, ProviderException 7 in last 10 minutes.",
        "CloudTrail event 8de0e8c2: PutItem for table app-prod-events from lambda prod-etl-processor on account 981112233445.",
        "EC2 autoscaling group prod-etl-asg shows 2 desired, 2 running, CPU 32%, no capacity issue; scaling events 0 in 12h.",
        "SQS queue prod-etl-input has queue depth 0, no redrive errors, and no DLQ alerts triggered in the previous 8 hours.",
        "RDS DB prod-reporting is healthy and not implicated; latency and CPU stable under 35% across all regions.",
        "CloudFormation stack prod-etl-v2 status UPDATE_COMPLETE; no infrastructure drift found in template validation.",
        "Lambda environment variables include REDIS_URL, DDB_TABLE, LOG_LEVEL=INFO, and S3_BUCKET; no secrets rotation in progress.",
        "DynamoDB global secondary index gsi_status has 13% write utilization and no hot key pattern visible from the last 24h table metrics.",
        "CloudWatch alarm PROD-DDB-WriteThrottle-High state ALARM at 15:32 UTC, threshold 10 writes/s for 5 minutes.",
        "Lambda layer arn:aws:lambda:us-east-1:123456789012:layer:canary-helpers:9 is in use; no deployment in the last 46 hours.",
        "X-Ray trace annotation: downstream DynamoDB call retries 11 times before aborting with ProvisionedThroughputExceededException.",
        "Application log: WARNING BatchWriteItem failed: ValidationException and throughput threshold reached for table app-prod-events.",
        "Lambda concurrency metrics: reserved concurrency 5, actual concurrency 4, no pollution or contention from competing workloads.",
        "Kinesis analytics job prod-stream-agg shows max delay 2.3s and no backlog; ingestion not the root cause.",
        "SNS topic prod-alerts has 3 subscribers, all healthy, message retry count 0, no outage there.",
        "Load balancer metrics: request count 2100/min, HTTP 5xx 18%, target response time trending up steadily since 15:20 UTC.",
        "DynamoDB table app-prod-events has stream enabled and IteratorAge 0; stream lag not causing user-facing delay.",
        "Application health check /ready returns 200 for the API pods, but the /extract job fails after 3 seconds; queue ingestion still rising.",
        "CloudWatch metric for Lambda errors: Errors 128, Throttles 0, DeadLetterErrors 0, Duration p99 2957 ms.",
        "X-Ray service map: API Gateway -> Lambda prod-etl-processor -> DynamoDB app-prod-events (throttled) -> step function failure chain.",
        "Business impact: nightly data pipeline is delayed by 42 minutes, downstream BI dashboards missing 3.8M rows.",
        "Summary: the root cause is a DynamoDB write throughput cap triggered by a sudden producer burst; Lambda timed out while retrying writes.",
        "Runbook note: if Lambda is timing out while holding DDB writes, check for ProvisionedThroughputExceededException before increasing function memory.",
        "Operational metadata: recent deployment from 15:20 UTC increased event emission rate by 2.3x but no table scaling was configured.",
    )
    return Scenario(
        name="Scenario 2: Lambda Timeout and DynamoDB Burst",
        description="Lambda times out while retrying writes to a DynamoDB table that exceeds provisioned throughput during a bursty ingestion event.",
        chunks=chunks,
    )


def _scenario_three() -> Scenario:
    chunks = (
        "Finance dashboard shows S3 PUT and GET cost for us-east-1 increased 3.8x compared with the rolling 30-day baseline.",
        "NAT gateway data transfer price in us-east-1 rose from $0.045 to $0.052 per GB this month due to spot rate updates; this is not a service outage.",
        "S3 bucket prod-logs-archive has 1.8 PB of data and 40 million lifecycle transitions over 7 days; no storage data loss.",
        "Cost Explorer group: NATGateway-DataTransfer = $18,440 in 7 days, up 220% relative to prior week; all other compute costs flat.",
        "Billing alarms: DataTransferCostSpike-High triggered at 10:11 UTC, alarm threshold 12,000 USD/week exceeded by 39%.",
        "VPC flow logs show 4.7 TB of east-west traffic between private subnets and NAT gateway across account 447922331019.",
        "CloudWatch dashboard for private subnet NAT gateway shows 30-minute average bytes per second 2.6x above baseline, consistent with repeated egress bursts.",
        "EC2 instance metrics: app-queue-worker volume increased from 420 GB/day to 1.28 TB/day after a topology update.",
        "IAM role prod-billing-reader has read-only access for Cost Explorer and no effect on traffic patterns; not a root cause.",
        "The S3 bucket prod-model-artifacts has a cross-region replication rule to eu-west-1 that was enabled 2 days ago without an approval record.",
        "AWS support ticket notes: data transfer charges spiked following a new ML training job and a migration from one bucket to another.",
        "Architectural runbook says NAT gateway charges are highest when workloads in private subnets transfer to the internet or to S3 endpoints.",
        "Cost anomaly detector flagged a 67% increase in egress from private subnet 10.10.0.0/24 to internet addresses 34.205.0.0/16.",
        "S3 bucket prod-ml-output has object tagging set to team=ml, environment=prod, retention=365, no anomalies detected.",
        "ALB access logs are healthy and do not show a traffic spike to the public endpoints; issue is internal data transfer behavior.",
        "IAM policy summary for role data-pipeline-runner: no broad permissions; only s3:PutObject and s3:GetObject to specific prefixes.",
        "CloudTrail entries show a new worker process in private subnet launched at 08:42 UTC and downloading 1.2 TB of model outputs from S3 to EC2 via NAT.",
        "Route table update: newly introduced private subnet route to NAT gateway for internet egress replaced the previous S3 gateway endpoint path.",
        "Open support case: a new NAT gateway in subnet 10.10.21.0/24 created on 2026-10-20 caused all east-west egress to transit through NAT.",
        "Cost Explorer detail: 74% of NAT egress spend comes from S3 GET requests to public bucket data-science-archive from private subnet workloads.",
        "Firewall and security group rules: no blocks, but requests to public endpoints from private subnets still traverse NAT and incur charges.",
        "VPC endpoint health: S3 gateway endpoint is still available in subnet 10.10.2.0/24, but the new workload was launched in a subnet without a gateway endpoint.",
        "Application logs: model training job repeatedly calls GET from public S3 buckets for dataset sync to ephemeral EC2 worker nodes in private subnets.",
        "Multi-turn investigation thread: engineer A says 'maybe it is just CloudFront caching or S3 requests'; engineer B says 'cost only increased after NAT route change'; engineer C says 'bug is in subnet routing and not in IAM or compute'.",
        "Cost anomaly details: A/B comparison shows no increase in API requests, but S3 data transfer increased because private workloads routed through NAT instead of S3 gateway endpoint.",
        "A/B note: baseline architecture had an S3 gateway endpoint in every private subnet; new architecture removed it for a simplified network but increased charges by $6.4k/week.",
        "Summary: The real cause was a network routing regression: private EC2 workers were egressing to the internet and S3 public endpoints through a NAT gateway without a gateway endpoint in their subnet.",
        "Finance team confirms all spend categories are normal except NAT gateway data transfer; a targeted route fix is the correct remediation.",
    )
    return Scenario(
        name="Scenario 3: S3/NAT Gateway Cost Spike",
        description="A router and subnet change pushes private EC2 traffic through a NAT gateway instead of S3 gateway endpoints, causing a cost spike.",
        chunks=chunks,
    )


SCENARIOS: dict[str, Scenario] = {
    "iam_kms_explictdeny": _scenario_one(),
    "lambda_timeout_ddb": _scenario_two(),
    "s3_nat_cost_spike": _scenario_three(),
}


def get_scenario(name: str) -> Scenario:
    if name not in SCENARIOS:
        raise KeyError(f"Unknown scenario {name!r}. Available: {sorted(SCENARIOS)}")
    return SCENARIOS[name]


def scenario_names() -> list[str]:
    return sorted(SCENARIOS)


def load_all_scenarios() -> Iterable[Scenario]:
    return tuple(SCENARIOS.values())
