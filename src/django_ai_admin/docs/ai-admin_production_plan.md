# AI Admin Production Plan

## 1. Purpose
- Build production-ready AI assistant for Django Admin that answers data questions safely.
- Keep chat UX simple while improving reliability, security, and answer quality.
- Prepare module extraction into a separate reusable repository/package.
- Use a staged delivery: functionality and chat quality first, deep hardening after core UX is stable.

## 2. Product Scope
- In scope:
- Natural-language data questions in admin UI.
- Safe read-only ORM execution with strict controls.
- Clarification flow when query is ambiguous or outside project scope.
- Chat memory and multi-turn context.
- Out of scope (initial production releases):
- General-purpose assistant capabilities unrelated to project data.
- Arbitrary code execution and unrestricted imports.

## 2.1 Current Prioritization Mode
- Priority now: correctness, context-aware dialogs, routing, and UX.
- Deferred (later release): strict import filtering and advanced sandbox hardening.
- Baseline protections that remain active now:
- Read-only DB transaction.
- Statement timeout.
- Staff-only API access.

## 3. Unified Runtime Contract

### 3.1 Request (chat message)
- Endpoint: `POST /ai-assistant/api/chats/{chat_id}/message`
- Request body:
```json
{
  "content": "How many new users signed up in the last 7 days?",
  "client_context": {
    "timezone": "UTC",
    "locale": "en-US"
  }
}
```

### 3.2 Response envelope
- Every response must use one envelope:
```json
{
  "type": "answer|clarification|out_of_scope|error",
  "message": "text for user",
  "data": {},
  "meta": {
    "chat_id": 12,
    "intent_label": "DATA_QUERY",
    "intent_confidence": 0.92,
    "trace_id": "uuid"
  }
}
```

### 3.3 Response by type
- `answer`:
- `data.result`, `data.truncated`, `data.explanation`, optional `data.code` (gated by settings).
- `clarification`:
- `data.question`, `data.options[]`, `data.pending_clarification_id`.
- `out_of_scope`:
- `data.reason`, `data.how_to_rephrase`.
- `error`:
- `data.error_code`, `data.retryable`.

## 4. Target Architecture
- `IntentRouter`:
- Classifies input into `DATA_QUERY`, `CLARIFICATION`, `OUT_OF_SCOPE`, `GENERAL_HELP`.
- `ContextBuilder`:
- Builds prompt context from recent messages + short session summary.
- `Planner`:
- Produces normalized plan JSON before code generation.
- `CodeGenerator`:
- Generates ORM snippet constrained by manifest and policy.
- `ExecutionEngine`:
- Validates code with AST guards, then executes read-only transaction.
- `ResponseComposer`:
- Produces typed envelope for frontend.
- `Observability`:
- Structured logs, metrics, trace IDs, query audit.

## 5. Import/Execution Policy (Phased)

### 5.1 Why this matters
- Unrestricted `import` in executed code allows access to filesystem/network/process APIs and increases risk.

### 5.2 Phase A (now, functionality-first)
- Keep current import behavior to avoid blocking delivery of routing/context features.
- Improve prompt and planner behavior first so generated code quality stabilizes.
- Keep existing execution baseline controls (read-only transaction + timeout + staff gating).

### 5.3 Phase B (later, hardening release)
- Move to strict execution policy:
- Disallow imports in LLM-generated code by default.
- Preload approved symbols in execution globals (models + helpers).
- Optional compatibility mode via whitelisted `__import__`.

### 5.4 Migration note for hardening phase
- Update prompt rules: no `from <app>.models import ...`.
- Use already-available model classes from execution globals.

## 6. Release Roadmap

## Release 0.1.0 (Contract + Intent Routing)
- Goals:
- Stabilize API contract and stop forcing every message into ORM execution.
- Features:
- Unified typed response envelope (`answer|clarification|out_of_scope|error`).
- Add `IntentRouter` and confidence thresholds.
- Add clarification responses with options.
- Add out-of-scope fallback with rephrase hints.
- Log `intent_label`, `intent_confidence`, candidate models.
- Acceptance:
- Ambiguous prompts produce clarification, not execution.
- Out-of-scope prompts produce helpful fallback.
- Frontend handles all response types consistently.

## Release 0.2.0 (Chat Memory + Multi-Turn)
- Goals:
- Multi-turn conversations with real context.
- Features:
- Add `conversation_summary` to chat/session state.
- Include last N messages + summary in prompt context.
- Add `pending_clarification` state machine.
- Auto-title chats from first stable intent.
- Acceptance:
- Follow-up questions resolve prior topic correctly.
- Clarification answer flow works end-to-end.

## Release 0.3.0 (Generation Quality)
- Goals:
- Improve first-pass success and reduce retries.
- Features:
- Add plan JSON step before code generation.
- Add schema validation for model output.
- Error-aware retry strategy by error class.
- Add deterministic normalization for result payload.
- Acceptance:
- First-pass success increases on test set.
- Retry count and failure rate decrease.

## Release 0.4.0 (UX and Chat Controls)
- Goals:
- Production-ready admin experience.
- Features:
- Quick actions for clarification options.
- Show query interpretation before run.
- Optional “show generated code” permission gate.
- Better large result handling (pagination/cursor).
- Acceptance:
- UX tests pass for clarification and long-result flows.

## Release 0.5.0 (Extraction and OSS)
- Goals:
- Move module to standalone repository/package.
- Features:
- Package as `djai`.
- Provider abstraction and settings-driven integration.
- Demo project + Docker setup + seed data.
- CI with tests, lint, coverage, release workflow.
- Security and limitations docs.
- Acceptance:
- Installable package works in clean Django sample app.

## Release 0.6.0 (Security Hardening)
- Goals:
- Move from baseline protections to strict execution hardening.
- Features:
- Restrict imports in generated code (default deny + whitelist mode).
- Add AST validator for blocked nodes and dangerous attribute access.
- Add strict error taxonomy and standardized non-200 failure statuses.
- Add stronger limits/redaction/rate controls.
- Acceptance:
- Security regression suite passes.
- Dangerous snippets are blocked before execution.
- No UX regressions vs 0.5.0 benchmark prompts.

## 7. Data Model and API Changes
- Add to `Chat`:
- `conversation_summary` (TextField), `current_topic`, `pending_clarification`.
- Add to `QueryLog`:
- `intent_label`, `intent_confidence`, `route`, `llm_latency_ms`, `db_latency_ms`, `retry_count`, `error_code`, `trace_id`.
- Add immutable event/audit table (optional but recommended):
- `ChatEvent` for transitions and user-visible events.

## 8. Observability and SLO
- Metrics:
- `first_pass_success_rate`, `clarification_rate`, `out_of_scope_rate`.
- `p50/p95 latency` (router, LLM, execution separately).
- `error_rate` by error code.
- Suggested SLO:
- p95 end-to-end response < 6s for non-truncated answers.
- first-pass success > 75% on benchmark set.

## 9. Testing Strategy
- Unit:
- Intent routing, context builder, planner/schema validation, response composer.
- Integration:
- Full chat flow with clarification and context carry-over.
- Security (hardening release):
- Read-only enforcement, blocked import/path/network attempts.
- Contract tests:
- Envelope schema per response type.
- Regression benchmark:
- Fixed dataset of prompts with expected intent and result shape.

## 10. Delivery Plan (5 Sprints)
- Sprint 1:
- Release 0.1.0 (contract + routing).
- Sprint 2:
- Release 0.2.0 (memory) + start 0.3.0.
- Sprint 3:
- Release 0.3.0 + 0.4.0 (quality + UX).
- Sprint 4:
- Release 0.5.0 extraction and publish prep.
- Sprint 5:
- Release 0.6.0 security hardening.

## 11. Open Questions to Resolve Before Implementation
- Should generated code be visible to all staff or only privileged roles?
- Do we need tenant/data-domain restrictions in addition to staff check?
- What benchmark prompts define “acceptable quality” for release gates?
- What redaction rules are required for PII in logs and responses?
- Current manifest clipping is `200 models x 30 fields`; confirm strategy for larger projects (chunking/paging/model-priority index).
