# Health AI Conversational System (RAT-Based)

## Architecture & Design Report

---

## 1. Project Overview

### Title

**Health AI Conversational System**

### Motivation

Health-related conversational AI systems pose unique challenges around **safety**, **privacy**, **hallucination control**, and **explainability**. Traditional chat-based LLM systems often rely on replaying full chat history or Retrieval-Augmented Generation (RAG), which can inadvertently expose sensitive data or internal reasoning.

This project proposes a **design-first, production-grade architecture** for a Health AI chat system that:

* Supports **multiple users and chats**
* Maintains **persistent context safely**
* Uses **RAT** to prevent chain-of-thought leakage
* Is suitable for **regulated domains** such as healthcare

The focus of this work is **system design, AI safety, and architectural rigor**, rather than implementation.

---

## 2. Project Status & Scope

### Current Status

This project is currently in the **architecture and design phase**.

Deliverables include:

* System architecture
* Database schema
* API specifications
* Context handling strategy
* Safety and risk analysis
* Sample prompts and workflows

The design is **build-ready** and intended for future implementation.

### Non-Goals

* Medical diagnosis or treatment
* Replacing healthcare professionals
* Storing or exposing chain-of-thought
* Using full conversation replay as context

---

## 3. High-Level System Architecture

### Architectural Overview

```
Frontend (React)
   ↓ JWT
API Gateway (FastAPI)
   ↓
Authentication & Authorization
   ↓
Safety & Policy Engine
   ↓
Context Builder (Summarized Memory)
   ↓
RAT Reasoner (Hidden)
   ↓
Response Generator
   ↓
Metrics & Audit Logs
```

### Key Principles

* **Stateless APIs** using JWT authentication
* **Minimal data exposure** to LLMs
* **Layered safety checks** before reasoning
* **Strict separation** between user-visible output and internal reasoning

### Operational Endpoints

* **Health check**: `GET /health` — liveness for load balancers and orchestrators.
* **Readiness**: `GET /ready` — checks DB and critical dependencies (optional); used by Kubernetes or similar for traffic routing.

---

## 4. Database Design

### Entity Relationship Overview

```
User → Chat → Messages
          ↓
     Chat Context
```

### 4.1 Users Table

```sql
users
------
id (UUID, PK)
email (unique)
password_hash
created_at
```

### 4.2 Chats Table

```sql
chats
------
id (UUID, PK)
user_id (FK → users.id)
title
created_at
expires_at
is_deleted
```

**Indexes:**

* `chats(user_id, created_at DESC)` — list user's chats in reverse chronological order.

### 4.3 Messages Table

```sql
messages
---------
id (UUID, PK)
chat_id (FK → chats.id)
role (user | assistant)
content
created_at
idempotency_key (unique, nullable)  -- client-supplied for POST /message
is_deleted (boolean, default false) -- soft delete for "delete my last message"
```

**Important Constraints:**

* Only **final assistant responses** are stored.
* No internal reasoning or retrieved documents are persisted.

**Indexes:**

* `messages(chat_id, created_at)` — load messages for a chat in order.

**Idempotency:** For `POST /chats/{chat_id}/message`, the client may send an `Idempotency-Key` header. Store it in `messages.idempotency_key`; if a duplicate key is seen for the same `chat_id`, return the existing response instead of creating a new message.

### 4.4 Chat Context Table

```sql
chat_context
------------
chat_id (FK, unique)
medical_facts_summary
user_preferences_summary
risk_flags
version (integer, default 1)   -- for drift detection and re-summarization
updated_at
```

**Versioning:** Use `version` (or `updated_at` + optional checksum) to detect context drift. When drift is detected or after a defined interval, trigger re-summarization from the last N messages.

### 4.5 Safety Events Table

```sql
safety_events
-------------
id (UUID, PK)
chat_id (FK)
event_type
severity
escalation_status (none | internal_alert | external_referral)
handled_at
```

**Indexes:**

* `safety_events(chat_id, handled_at)` — per-chat audit.
* `safety_events(event_type, severity)` — optional, for analytics and alerting.

### 4.6 Model Metrics Table

```sql
model_metrics
-------------
id (UUID, PK)
date (date)
metric_name
value
model_version        -- e.g. RAT model version
safety_version       -- e.g. safety classifier version
```

Dimensions such as `model_version` and `safety_version` allow before/after comparison when deploying new models or safety rules.

### 4.7 Database Migrations

* Use a **versioned migration strategy** (e.g. SQL migration files or a tool like Alembic) from Phase 2 onward.
* All schema changes are applied via migrations; no ad-hoc DDL in production.

---

## 5. Context Management Strategy (RAT-Safe)

### Problem

Passing full chat history to an LLM:

* Increases hallucination risk
* Leaks sensitive data
* Is cost-inefficient

### Solution: Summarized Context Memory

Each chat maintains a **rolling, sanitized summary** updated periodically.

#### Context Types

* **Medical Facts Summary**: Symptoms, durations, constraints
* **User Preferences**: Lifestyle choices, communication preferences
* **Risk Flags**: Emergency symptoms, uncertainty indicators

#### Example Safe Summary

> "User reports mild fever and sore throat for 2 days. No emergency symptoms reported. Prefers home remedies."

This summary is:

* Generated internally
* Never shown to the user
* Never exposed as chain-of-thought

### Context Update Policy

* **When to update:** Define explicitly (e.g. every N messages, or every N tokens, or on a time window). Document the chosen policy to control cost and latency.
* **Size limit:** Define a **maximum token/character limit** for the combined summary so RAT prompts stay bounded and cost is predictable.
* **Re-summarization:** On version/drift detection or on a schedule, re-summarize from the last N messages and bump `chat_context.version`.

### Sanitization Rules

Document what is **stripped or generalized** before writing to the summary so the "safe summary" is well-defined and auditable, for example:

* **PII:** No emails, names, or identifiers.
* **Dates:** Only relative (e.g. "2 days ago") or coarse ranges; no exact calendar dates.
* **Quotes:** No verbatim user quotes that could re-identify; paraphrase only.

---

## 6. Safety & Policy Layer

### Safety Flow

```
User Message
   ↓
Safety Classifier
   ↓
Allowed → Context Builder → RAT
Flagged → Safe Response Template (+ optional internal alert / external referral)
```

### Explicit Emergency Path

* **Single emergency branch:** Emergency symptoms → (1) immediate canned response to user, (2) log to `safety_events` with appropriate `event_type` and `severity`, (3) optional internal alert, (4) optional `escalation_status` (e.g. `external_referral`) when policy requires.
* Document this path in the Safety Flow so all implementations follow the same behavior.

### Escalation

* **safety_events.escalation_status:** Values such as `none`, `internal_alert`, `external_referral`.
* Define in policy **when** human review or external referral is triggered (e.g. self-harm signals, certain emergency types) and ensure it is logged and, if needed, acted upon.

### Safety Scenarios

| Scenario           | Handling                            |
| ------------------ | ----------------------------------- |
| Emergency symptoms | Immediate referral response + log + optional escalation |
| Self-harm signals  | Supportive, non-diagnostic response + escalation as per policy |
| Medication dosage  | High-level guidance only; **never output specific dosage**; always recommend consulting prescriber/pharmacist |
| Prompt injection   | System isolation (canned response, no model call) |

### Medication Rule

* **Hard rule:** Never output specific dosage in the product. All medication-related answers are high-level only (e.g. "Talk to your doctor or pharmacist about dosing"). Enforce via system prompt and safety spec.

---

## 7. RAT Reasoning Design

### Why RAT Instead of RAG?

| Aspect             | RAG          | RAT    |
| ------------------ | ------------ | ------ |
| Chain-of-thought   | Often leaked | Hidden |
| Health suitability | Risky        | Safer  |
| Control            | Low          | High   |

### Retrieval Clarification

* **Current scope:** The RAT reasoner uses **summarized context only** (no retrieval from an external knowledge base in the initial design).
* **If retrieval is added later:** Only a **summary** (or selected, sanitized facts) of retrieved content is injected into context—**never raw retrieved chunks** in user-visible or chain-of-thought form—to keep the system RAT-safe.

### RAT Prompting Strategy (Hidden System Prompt)

```
Use the provided summarized context as background only.
Do not assume facts not present.
Verify all health-related claims internally.
Produce a clear, cautious final answer.
```

The LLM never sees:

* Full message history
* Raw retrieved documents (if any)
* Previous reasoning steps

### Structured Output (Optional but Recommended)

* Consider having the model return a **structured payload** (e.g. JSON) with fields such as:
  * `answer` — user-visible text
  * `confidence` — optional, for internal metrics
  * `citations` — optional, if retrieval is added later (references only, no raw chunks)
  * `disclaimer` — e.g. "This is not medical advice"
* The API then renders the `answer` and appends the `disclaimer` consistently, improving control and consistency.

---

## 8. API Design (FastAPI)

See **[API_SPEC.md](./API_SPEC.md)** for full details. Summary below.

### Versioning

* **Path versioning** from day one: e.g. `/v1/auth/...`, `/v1/chats/...`.
* Prevents breaking existing clients when the API evolves.

### Authentication

```
POST /v1/auth/register
POST /v1/auth/login
```

* **Token strategy:** Short-lived **access JWT** + **refresh token**. Document storage (e.g. httpOnly cookie or secure client store), rotation, and revocation. Refresh token endpoint: e.g. `POST /v1/auth/refresh`.

### Chat Management

```
POST   /v1/chats
GET    /v1/chats              (paginated)
GET    /v1/chats/{chat_id}
POST   /v1/chats/{chat_id}/message   (supports Idempotency-Key)
GET    /v1/chats/{chat_id}/messages  (paginated)
DELETE /v1/chats/{chat_id}
```

### Error Format

* **Standard envelope:** e.g. `{ "error": { "code": "...", "message": "...", "details": {} } }`.
* **HTTP status:** Use 429 for rate limit, 503 for model/safety service unavailable, 4xx for client errors, 5xx for server errors.

### Pagination

* **GET /v1/chats** and **GET /v1/chats/{chat_id}/messages:** Define **cursor-based or offset-based** pagination and a **maximum page size** (e.g. 50). Document query params (e.g. `cursor`, `limit`).

### Rate Limiting

* **Per user** (and optionally per IP): Document in design and in API spec. Protects the RAT/model and prevents abuse. Return 429 when exceeded.

### Message Handling (Pseudo-code)

```python
def send_message(chat_id, user_msg, user, idempotency_key=None):
    if idempotency_key and duplicate_exists(chat_id, idempotency_key):
        return get_existing_response(chat_id, idempotency_key)

    summary = get_safe_summary(chat_id)

    if is_flagged(user_msg):
        response = safe_override_response()
        log_safety_event(chat_id, ...)
        return response

    response = rat_reason(
        user_input=user_msg,
        context_summary=summary
    )

    save_message(chat_id, "user", user_msg)
    save_message(chat_id, "assistant", response, idempotency_key=idempotency_key)

    update_safe_summary(chat_id, user_msg, response)

    return response
```

---

## 9. Authentication & Security

* **Secrets:** Model API keys, database credentials, and JWT signing secrets are stored in a **secrets manager** (e.g. HashiCorp Vault, cloud provider secret manager). Never committed in repo or plain env files.
* **Audit logging:** All access to chats/messages (read/write) and all safety overrides are written to an **append-only audit log** (tamper-evident where feasible) for compliance and forensics.

---

## 10. Compliance & Privacy

* **Data minimization:** Only data necessary for the product is stored. No raw logs of full prompts/responses beyond what is in `messages` and `safety_events` (and any approved audit records).
* **Retention:** `chats.expires_at` is tied to a **retention policy** (e.g. 90 days). Automated deletion or anonymization is run periodically; document in risk analysis and runbooks.
* **Regulatory alignment:**
  * **US (HIPAA):** If handling PHI, plan for BAA with model/provider, encryption at rest and in transit, access controls, and audit logging. Call out in roadmap (e.g. Phase 2 or 3).
  * **EU (GDPR):** Legal basis for processing, data subject rights (access, deletion, portability), and DPAs with sub-processors. Document retention and deletion in privacy notice.

---

## 11. Evaluation & Monitoring

### Metrics Tracked

| Metric               | Purpose           |
| -------------------- | ----------------- |
| Hallucination rate   | Reliability       |
| Safety override rate | Guardrail quality |
| Context drift        | Memory accuracy   |
| Response consistency | Clinical safety   |

* **Hallucination rate:** Define the **method** (e.g. sample-based human review, or model-based checks against a golden Q&A set) so the metric is implementable.

### SLOs (Service Level Objectives)

* Define at least one or two SLOs, e.g.:
  * p95 latency for `send_message` &lt; X seconds
  * Safety override rate within expected band (e.g. &lt; Y% or alert if &gt; Z%)
* Document where these are monitored (e.g. dashboard, alerting).

### Metrics Table

See **4.6 Model Metrics Table** — include `model_version` and `safety_version` for comparability.

---

## 12. Failure & Risk Analysis

| Risk                     | Mitigation |
| ------------------------ | ---------- |
| Hallucinated advice      | Strict prompts + summarized context only |
| Context corruption       | Periodic re-summarization; version in `chat_context` |
| Token leakage            | JWT expiry; refresh token rotation |
| Data over-retention      | Auto-expiry; retention policy; automated deletion |
| Model/safety service down| Fallback: "Sorry, I can't process this right now"; do not store user message until service is back |
| Summary corruption / stuck context | Periodic re-summarization from last N messages; version check |
| Abuse / prompt injection | Rate limiting, input length limits, safety classifier → system isolation response |

---

## 13. Optional Enhancements

* **Feature flags:** Toggle safety rules, model version, or context strategy without redeploy (e.g. for A/B testing or rollback).
* **Admin API:** Read-only or tightly scoped admin endpoints (e.g. list `safety_events`, export for audit), behind a separate admin role and auth.

---

## 14. Implementation Roadmap

### Phase 1 – Architecture (Completed)

* System design
* Safety planning
* API & schema definition
* **Design refinements:** Indexes, idempotency, context versioning, safety escalation, compliance notes, risk table, SLOs

### Phase 2 – Backend

* Auth & chat APIs (with versioning, errors, pagination, rate limiting)
* Context summarizer (update policy, sanitization, size limit)
* **Database migrations strategy** (versioned migrations)
* **Audit logging** for chat access and safety events

### Phase 3 – AI Layer

* RAT reasoner (hidden CoT; optional structured output)
* Safety classifier (emergency path, escalation, medication rule)
* Evaluation metrics (with model/safety version dimensions)
* **Prompt and context-summary testing** (golden datasets, red-team style safety cases)
* **HIPAA alignment** (if US and PHI): BAA, encryption, access controls, audit

### Phase 4 – Frontend

* Login (and refresh token flow)
* Chat UI
* Chat history (paginated)
* **Accessibility (WCAG)** and **mobile-responsive** UI

---

## 15. Conclusion

This project demonstrates a **design-first approach to building safe, scalable Health AI systems**. By prioritizing **privacy, safety, and reasoning integrity**, and by incorporating **indexing, idempotency, context versioning, explicit safety escalation, API versioning, rate limiting, compliance alignment, and SLOs**, the architecture is production-ready and provides a strong foundation for implementation.

---

## 16. Repository Usage

This repository serves as:

* A reference architecture for Health AI systems
* A foundation for future development
* A demonstration of AI systems thinking and safety-aware design
