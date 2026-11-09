# Reliability and anomaly-detection roadmap

Reviewed: 2026-10-16 (Asia/Jakarta). Scope: current Streamlit UI, Huawei generator, CIQ ingestion, SSH, audit persistence and preparation for detecting risky configuration changes.

## Current capability and limits

The platform now validates inputs through one Pydantic contract, assesses changes with explainable rules and captures versioned features for offline analysis. No trained machine-learning model is active. A rule score is a review priority, not a probability of an incident. A low score does not establish that a change is safe.

Live execution is blocked in the UI because the application cannot yet read device state, determine ownership of shared objects, restore an exact snapshot or verify service health. Setting RELPOOL_ENABLE_LIVE alone does not unblock the UI. The lower-level transport remains a testbed primitive; callers must enforce change controls before using it directly.

## Implemented changes

| Area | Improvement |
|---|---|
| Header, KPI cards, sidebar | Removed fabricated live/connected/zero-impact claims. Actual recorded activity, current assessment, Jakarta daily counts and explicit execution readiness. |
| Styling | Offline font fallbacks, responsive spacing, visible keyboard focus, improved metric contrast and reduced-motion support. |
| Manual workflow | Validate and generate before auditing success; reject unsafe input, mask key input, redact summary, persist execution intent and correlate outcomes to the originating work order. |
| Batch workflow | Correctly quoted sample CSV, required columns/cells, unambiguous aliases, normalized filenames, duplicate-rule/shared-domain conflict checks, size/row limits and content-hash invalidation even for identical filenames. |
| Rule engine | Enforce shared validation, require explicit domains, retain v1 during revamp, remove unsafe whole-group delta rollback. Existing rollback artifacts are labeled drafts. |
| SSH | Verify known host keys, require explicit target/credentials and live opt-in, bounded prompt reads, stop after device errors or uncertain responses, redact enrichment keys and distinguish FAILED, PARTIAL_FAILED, UNKNOWN and SENT_UNVERIFIED. |
| Crypto | Require a native Fernet key; failed encryption/decryption cannot silently return plaintext. Plaintext credentials need explicit opt-in. |
| Audit | Fix fresh-install deadlock, remove fabricated default events, atomic thread-safe appends, visible corruption/write errors, recursive secret redaction, UUID identities, UTC timestamps and retention of all events. |
| ML preparation | Rule explanations, versioned pre-execution features, script fingerprints and allowlisted JSONL export. Legacy records without captured features are excluded. |
| Quality | Unit/integration discovery, failure-path tests, Streamlit workflow tests, pinned direct dependencies and a Windows/Linux CI workflow. |

Audit exports are operational data, not public artifacts. Generated CLI intentionally contains enrichment keys when requested; do not include those artifacts in training datasets.

## Prioritized engineering recommendations

| Priority | Component | Next change | Completion evidence |
|---|---|---|---|
| P0 | Device state | Read and normalize pre-change configuration; determine object existence, references and ownership. Compare a deterministic desired-state diff. | A repeated identical request creates no duplicate objects; conflicting shared objects stop before execution. |
| P0 | Rollback | Build rollback from the actual snapshot and applied diff, including hosts, filters, charging objects and profile-level changes. | Failure injected at every command boundary restores the captured state in a supported testbed. Shared objects remain intact. |
| P0 | Vendor engine | Validate syntax and qualified identifier limits against the actual Huawei release. Implement PCRF/QoS/speed/capping and charging semantics, or remove unsupported choices. | Independent engineer review plus device-backed positive and negative tests. Current comments are not treated as deployed policies. |
| P0 | Execution control | Use a deployment state machine: planned, reviewed, started, applied, verified, failed, rollback verified or unknown. Require change approval tied to immutable script hash and node identity. | A modified script invalidates its approval; a disconnect leaves an explicit unknown state and cannot trigger a blind retry. |
| P0 | Security | Add enterprise SSO, server-enforced RBAC, environment/node allowlists, least-privilege SSH accounts and managed secrets with rotation. | Unauthorized users cannot call deployment functions, even outside the UI. Credential rotation and revoked host-key scenarios pass tests. |
| P1 | Persistence | Replace JSON with transactional SQLite for a single-host service or PostgreSQL for multiple workers; migrate legacy history with provenance flags. | Parallel-process tests lose no records. IDs, parent links and schema versions are validated. Restore from backup is exercised. |
| P1 | Jobs | Move SSH to a durable worker with per-node locks, an idempotency key, execution leases and reconnect/reconciliation logic. | Browser refresh or worker restart does not duplicate a change; two jobs cannot mutate one node concurrently. |
| P1 | Observability | Capture per-command timings/errors and pre/post configuration, alarms, traffic and charging KPIs. Add correlation IDs and alerts for unresolved attempts. | Operators can trace each request through generation, execution and verification without exposing credentials. |
| P1 | Ingestion | Add XLSX decompression/resource limits, data-quality reports, versioned CIQ schema and a documented alias catalog. | Oversized compressed workbooks and malicious formula-like values cannot exhaust the service or reach CLI. |
| P1 | Testing/release | Add device-version fixtures, golden scripts reviewed by engineers, fault injection, dependency scanning and a full transitive lock with hashes. | CI runs on each PR; staging verification precedes release. Direct pins alone are not a complete reproducible environment. |
| P2 | UI | Add device/config diff review, ownership findings, approval identity, execution progress and verified rollback outcome. Validate responsive layouts in a browser. | Usability review with NOC engineers; keyboard-only operation; no status can imply an unverified deployment succeeded. |
| P2 | Scale | Measure latency, memory, event growth and batch throughput; add DB indexes and server pagination when justified. | Representative-load tests meet agreed limits, including concurrent sessions and long audit history. |

The current JSON lock protects threads within one process. Legacy save_history is a compatibility snapshot API and can overwrite stale data if external callers use it; new event producers should use append_history or append_history_entries.

## Data needed for anomaly detection

Use a deployment attempt as the primary observation. Link its feature snapshot, immutable script fingerprint, work order, source CIQ version, node/software version, approval and outcome through stable identifiers. Keep batch rows and retries in the same group.

The current export captures product/profile/charging type, domain and wildcard counts, command and undo counts, enrichment flag, QCI, throttling flag and capping request. It omits raw domains, APNs, node addresses, credentials and CLI. Correlation IDs and observations sit outside the feature vector.

Before training, add features that describe the actual change: added/removed/modified object counts, shared-reference counts, prior-state conflicts, diff size, affected profiles/subscribers, device software version, pre-change KPI baselines and recent incident context. Gather historical features using only information available at request time.

Maintain a separate reviewed label table: event ID, configuration anomaly classification, incident outcome, observation window, severity, reviewer, evidence and label version. Distinguish configuration defects from authentication/VPN failures. Record unknown and unreviewed explicitly; absence of an incident report is not proof of normality. Simulations, generated scripts and old SUCCESS records are not verified normal deployments.

Suggested independent targets:

- Configuration anomaly: an engineer-reviewed unexpected or invalid change relative to desired state and baseline.
- Service incident after deployment: an attributed incident inside an agreed observation window, verified with telemetry and incident review.

Do not train on the rule score as ground truth. Do not feed outcomes, future alarms, rollback decisions, reviewer labels or execution duration into a model intended to score a change before execution.

## Model development and release

1. Establish the rule baseline and measure its alert quality with engineers. Version the policy and feature definitions.
2. After collecting representative verified-normal observations, evaluate Isolation Forest as an offline baseline for unusual feature combinations. Anomaly scores flag unusual requests; they do not prove a change is harmful. Compare with simple cohort thresholds before adding complexity. [Isolation Forest documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html).
3. When reviewed risk/incident labels are sufficient, compare a simple supervised classifier with the anomaly baseline. Choose based on held-out operational performance; data representativeness matters more than an arbitrary row-count threshold.
4. Split chronologically before fitting preprocessing, preserve work-order/batch/retry groups and reserve unseen nodes or software cohorts for a separate generalization check. Fit encoders/scalers only on training data through a pipeline. The present export lacks node cohorts, so capture a protected cohort identifier before this evaluation. [scikit-learn leakage guidance](https://scikit-learn.org/stable/common_pitfalls.html).
5. Evaluate recall for severe changes, precision, false alerts per 100 requests, PR-AUC for imbalanced reviewed labels, missed-severity cost, cohort performance and inference latency. Report confidence intervals and review missed incidents. Agree an alert budget with NOC before setting thresholds.
6. Track code/data/feature versions, random seeds, preprocessing, metrics, thresholds and model artifacts. Maintain a rollbackable approved model version. [MLflow tracking](https://www.mlflow.org/docs/latest/tracking/) supports recording experiments and artifacts.
7. Run in shadow mode first. Compare model alerts with operator decisions without letting the model deploy or roll back configurations. Promote only after independent held-out evaluation and operational review.
8. Monitor feature availability, schema mismatch, score/feature drift, alert rate and delayed-label quality by cohort. On an invalid/missing model or unsupported input, report model unavailable and retain deterministic validation and review. Never describe an unavailable prediction as low risk. Test before deployment and monitor during operation, consistent with [NIST AI RMF measurement guidance](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/).

No ML packages are added to the serving application yet. Keep training dependencies and model artifacts isolated until the dataset, feature contract and evaluation are ready.

## Migration and verification

- Existing .env and audit records were not rewritten by this change.
- SECRET_KEY must now be a native key generated by Fernet.generate_key(). Existing passphrase-derived keys must be migrated: decrypt existing tokens offline with the previous method, generate a native key, re-encrypt and rotate the stored credentials. Keep both keys protected during migration. Do not log plaintext.
- A corrupt or unreadable audit file now stops workflows and preserves the original file. Back up and repair it instead of silently resetting evidence.
- Timestamps are UTC ISO-8601 for new events. Legacy naive timestamps are treated as Jakarta time for daily counts.
- Work-order IDs now use a full UUID suffix; display-history length no longer determines identity. Separate execution events link to the generation work order.
- Delta rollback emits explanatory comments only. New-product rollback remains a draft and does not restore every shared/profile setting.
- Run: python -m unittest discover -s tests -p "test_*.py" -v.
- Verified locally with Python 3.11.9 and the direct versions in requirements.txt. Tests exercise fake SSH clients and temporary audit stores; no real network changes were made. Cross-platform CI and device-backed verification have not been run in this workspace.