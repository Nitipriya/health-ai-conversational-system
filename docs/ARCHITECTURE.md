# Health AI Conversational System — Architecture & Design

---

## 1. Project Overview

### Motivation

Health-related conversational AI poses unique challenges around safety, privacy, hallucination control, and explainability. Traditional chat-based LLM systems often rely on full chat history replay or cloud-based RAG, which exposes sensitive data and incurs ongoing API costs.

This project proposes a **design-first, production-grade architecture** that:
- Supports multiple users and chats
- Maintains persistent context safely using summarized memory
- Uses **Retrieval-Augmented Thought (RAT)** to prevent chain-of-thought leakage
- Runs entirely on a **local LLM via Ollama** — no health data leaves the machine
- Is suitable for regulated domains (healthcare) and student/hobbyist budgets alike

### Non-Goals
- Medical diagnosis or treatment
- Replacing healthcare professionals
- Storing or exposing chain-of-thought
- Sending patient data to any external AI provider

---

## 2. High-Level System Architecture

```
Frontend (React via Loveable)
        ↓ JWT Bearer token
API Gateway (FastAPI)
        ↓
Authentication & Authorization
        ↓
Consent Check (gate — first chat only)
        ↓
Safety & Policy Engine
   ↓ flagged           ↓ allowed
Canned Response    Context Builder (Summarized Memory)
  + log event              ↓
                     RAT Reasoner (Hidden)
                           ↓ Ollama HTTP API (local)
                     Response Generator
                           ↓
                     Structured Output Parser
                           ↓
                     Metrics & Audit Logs
```

### Key Principles
- **Stateless APIs** — JWT authentication, no server-side session
- **Minimal data exposure** — summarized context only, never full history, never raw CoT
- **Layered safety checks** before any model call
- **Strict separation** between user-visible output and internal reasoning
- **Local inference** — Ollama runs on the same machine or local network

### Operational Endpoints
- `GET /health` — liveness probe
- `GET /ready` — readiness probe (checks DB connection)

---

## 3. Local LLM — Ollama Integration

### Why Ollama
Ollama provides a simple HTTP API over locally-running open-source models. It is free, runs offline, and means no health query data is ever sent to a third-party AI provider — a significant privacy and compliance advantage.

### Recommended Models

| Model | RAM | Recommended for |
|---|---|---|
| `llama3.2:3b` | ~4 GB | Development / low-resource machines |
| `llama3.1:8b` | ~8 GB | Better reasoning; preferred for production |
| `mistral:7b` | ~8 GB | Strong instruction-following |
| `gemma2:9b` | ~10 GB | Good safety + quality balance |

Use `llama3.2:3b` during development. Switch to `llama3.1:8b` or `mistral:7b` once the stack is stable.

### Ollama API Usage
```
Base URL:  http://localhost:11434
Endpoint:  POST /api/chat          ← multi-turn, structured messages
           POST /api/generate      ← single prompt
Streaming: stream=true → NDJSON chunks
```

Example request to Ollama:
```json
POST http://localhost:11434/api/chat
{
  "model": "llama3.2:3b",
  "stream": false,
  "messages": [
    { "role": "system", "content": "..." },
    { "role": "user",   "content": "..." }
  ]
}
```

### Model Config (env-driven, hot-swappable)
```
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
OLLAMA_TIMEOUT_SECONDS=30
OLLAMA_MAX_TOKENS=512
```
Changing `OLLAMA_MODEL` in `.env` swaps the model without a code change.

---

## 4. Database Design

### Entity Relationship
```
User → Chat → Messages
                 ↓
            Chat Context
                 ↓
          Message Feedback
```

### 4.1 Users
```sql
users
-----
id              UUID        PRIMARY KEY
email           TEXT        UNIQUE NOT NULL
password_hash   TEXT        NOT NULL
consent_given   BOOLEAN     DEFAULT false
consent_at      TIMESTAMPTZ
created_at      TIMESTAMPTZ DEFAULT now()
```

### 4.2 Chats
```sql
chats
-----
id          UUID        PRIMARY KEY
user_id     UUID        REFERENCES users(id)
title       TEXT        -- auto-generated from first message; user-editable
created_at  TIMESTAMPTZ DEFAULT now()
expires_at  TIMESTAMPTZ -- retention policy (90 days from created_at)
is_deleted  BOOLEAN     DEFAULT false

INDEX: (user_id, created_at DESC)
```

### 4.3 Messages
```sql
messages
--------
id               UUID        PRIMARY KEY
chat_id          UUID        REFERENCES chats(id)
role             TEXT        CHECK (role IN ('user', 'assistant'))
content          TEXT        NOT NULL
created_at       TIMESTAMPTZ DEFAULT now()
idempotency_key  TEXT        UNIQUE  -- nullable; client-supplied on POST /message
is_deleted       BOOLEAN     DEFAULT false

INDEX: (chat_id, created_at)
```

Only final assistant responses are stored. No internal reasoning, no retrieved documents.

**Idempotency:** Client sends `Idempotency-Key` header on `POST /message`. If key exists for that `chat_id`, return the existing response instead of calling the model again.

### 4.4 Message Feedback
```sql
message_feedback
----------------
id          UUID        PRIMARY KEY
message_id  UUID        REFERENCES messages(id)  -- assistant messages only
rating      SMALLINT    CHECK (rating IN (-1, 1))  -- -1 = thumbs down, 1 = thumbs up
note        TEXT        -- optional free-text from user
created_at  TIMESTAMPTZ DEFAULT now()

INDEX: (message_id)
```

### 4.5 Chat Context
```sql
chat_context
------------
chat_id                  UUID    PRIMARY KEY REFERENCES chats(id)
medical_facts_summary    TEXT
user_preferences_summary TEXT
risk_flags               TEXT[]
version                  INTEGER DEFAULT 1
updated_at               TIMESTAMPTZ
```

### 4.6 Safety Events
```sql
safety_events
-------------
id                UUID        PRIMARY KEY
chat_id           UUID        REFERENCES chats(id)
event_type        TEXT        -- e.g. "emergency", "self_harm", "dosage_request", "classifier_error"
severity          TEXT        -- "low" | "medium" | "high" | "critical"
escalation_status TEXT        CHECK (escalation_status IN ('none','internal_alert','external_referral'))
handled_at        TIMESTAMPTZ DEFAULT now()

INDEX: (chat_id, handled_at)
INDEX: (event_type, severity)
```

### 4.7 Model Metrics
```sql
model_metrics
-------------
id              UUID    PRIMARY KEY
date            DATE
metric_name     TEXT    -- e.g. "safety_override_rate", "avg_response_tokens"
value           NUMERIC
model_version   TEXT    -- e.g. "llama3.2:3b"
safety_version  TEXT    -- e.g. "keyword-v1"
```

### 4.8 Migrations
All schema changes applied via Alembic versioned migrations. No ad-hoc DDL in production.

---

## 5. Context Management Strategy (RAT-Safe)

### Problem
Passing full chat history to the local LLM:
- Increases hallucination risk (older models especially)
- Is slow and memory-intensive with local inference
- Leaks sensitive details across unrelated conversation turns

### Solution: Summarized Context Memory

Each chat maintains a rolling, sanitized summary stored in `chat_context`.

**Context types:**
- `medical_facts_summary` — Symptoms, durations, stated conditions
- `user_preferences_summary` — Communication style, preferred remedies
- `risk_flags` — Emergency indicators, uncertainty signals

**Example safe summary:**
> "User reports mild fever and sore throat for 2 days. No emergency symptoms. Prefers home remedies over medication."

This summary is generated internally, never shown to the user, and never exposed as chain-of-thought.

### Update Policy
- **Trigger:** Every 5 messages OR when accumulated tokens exceed 800
- **Max context size:** 1000 tokens (combined summary sent to model)
- **Re-summarization:** Triggered on version drift or manually; bumps `chat_context.version`

### Sanitization Rules (enforced before writing to summary)
| Data type | Rule |
|---|---|
| Email / phone / name | Strip entirely |
| Exact dates | Convert to relative ("2 days ago", "last week") |
| Verbatim user quotes | Paraphrase only — no direct quotes |
| Specific dosages mentioned | Generalize ("user mentioned a medication") |

---

## 6. Safety & Policy Layer

### Safety Flow
```
User Message
    ↓
Safety Classifier (keyword rules → v1; LLM-based → v3)
    ↓
Allowed ──────────────→ Context Builder → RAT Reasoner → Response
    ↓ flagged
Canned Safe Response
    + log to safety_events
    + escalation if policy requires
```

### Classifier Resilience
- Hard timeout: **2 seconds** on classifier call
- On timeout or error → canned fallback ("I'm having trouble processing this right now")
- Log `event_type: "classifier_error"` to `safety_events`
- Do NOT call the model if classifier fails

### Explicit Emergency Path
1. Emergency keywords detected → immediate canned response (e.g. "Please call emergency services")
2. Log to `safety_events` with `severity: "critical"`, `event_type: "emergency"`
3. Set `escalation_status: "external_referral"` if self-harm signal present
4. No model call is made

### Safety Scenarios
| Scenario | Handling |
|---|---|
| Emergency symptoms (chest pain, difficulty breathing etc.) | Immediate referral response + critical log |
| Self-harm signals | Supportive, non-diagnostic + escalation |
| Medication dosage request | High-level only; **never specific dosage**; recommend prescriber |
| Prompt injection attempt | System isolation; canned response; no model call |
| Classifier timeout / error | Canned fallback; log event |

### Rate Limits
| Endpoint | Limit |
|---|---|
| Auth endpoints | 10 req/min per IP |
| `POST /v1/chats/{id}/message` | 20 req/min per user |
| Safety classifier (internal) | 50 req/min budget |

---

## 7. RAT Reasoning Design

### Why RAT (not standard RAG)?

| Aspect | Standard RAG | RAT |
|---|---|---|
| Chain-of-thought | Often leaked to user | Hidden internally |
| Retrieved docs | Passed raw to model | Summarized only |
| Health suitability | Risky | Safer |

### v1 — Summarized Context Only (No External Retrieval)

The model receives:
```
SYSTEM PROMPT (hidden):
  You are a cautious health information assistant.
  Use only the context summary below as background. Do not assume facts not present.
  Never provide a diagnosis. Never output specific medication dosages.
  If uncertain, say so clearly.
  Always recommend consulting a qualified healthcare professional.
  Respond ONLY with a JSON object in this format:
  {
    "answer": "<your response>",
    "confidence": "low|medium|high",
    "disclaimer": "This is for informational purposes only. Please consult a healthcare professional."
  }

CONTEXT SUMMARY:
  {sanitized_summary}

USER MESSAGE:
  {current_message}
```

The model never sees: full message history, previous reasoning steps, or raw retrieved documents.

### v2 — Retrieval (Planned, Not in Scope)
Candidate sources (open-access, no licensing cost):
- WHO guidelines (who.int)
- NHS Inform (nhsinform.scot)
- MedlinePlus (medlineplus.gov)

When added: only sanitized fact summaries will be injected — never raw document chunks.

### Structured Output Parsing
```python
# Expected model output (JSON):
{
  "answer": "string",
  "confidence": "low | medium | high",
  "disclaimer": "This is for informational purposes only..."
}
```
If the model returns malformed JSON (common with smaller models):
- Attempt regex extraction of an `answer` field
- Fall back to treating entire response as the answer
- Append standard disclaimer regardless
- Log a `metric_name: "json_parse_failure"` event

---

## 8. Streaming (SSE)

For `GET /v1/chats/{chat_id}/stream`:
- Accept `?message=<encoded>` query param OR prior POST creates a pending stream
- Call Ollama with `stream: true` → receives NDJSON chunks
- Re-emit each token as an SSE event to the client
- Emit a final `data: [DONE]` event on completion
- SSE is unidirectional and HTTP-native — no WebSocket complexity

```
Client  →  GET /v1/chats/{id}/stream
Server  →  text/event-stream
           data: {"token": "Based"}
           data: {"token": " on"}
           data: {"token": " your"}
           ...
           data: [DONE]
```

---

## 9. Authentication & Security

- **Access JWT:** 15 minutes TTL; signed with `JWT_SECRET` from env/secrets manager
- **Refresh token:** 7-day TTL; stored in `httpOnly`, `Secure`, `SameSite=Strict` cookie
- **Refresh endpoint:** `POST /v1/auth/refresh` — validates cookie, issues new access JWT
- **Logout:** clears refresh cookie server-side
- **Secrets management:** All secrets (DB URL, JWT secret) in `.env`; never committed. Production uses a secrets manager (e.g. Railway env vars, Vault)
- **Audit logging:** All chat access (read/write) and safety overrides logged to append-only `safety_events`

---

## 10. Compliance & Privacy

- **Data minimization:** Only what is needed is stored. No raw LLM prompt/response logs beyond `messages` and `safety_events`
- **Retention:** `chats.expires_at` = 90 days from creation. Automated deletion job runs nightly
- **Local inference = no third-party AI processor** — eliminates the largest GDPR/HIPAA data-processor concern
- **HIPAA (US):** If PHI is involved, add encryption at rest (Postgres column-level or disk encryption), TLS in transit, access controls. Document in Phase 3
- **GDPR:** Legal basis for processing, data subject deletion right (`DELETE /v1/chats/{id}` + account deletion endpoint in Phase 3), DPA not required for Ollama (local)

---

## 11. Evaluation & Monitoring

### Metrics
| Metric | How measured |
|---|---|
| Hallucination rate | Sample-based review against golden Q&A set |
| Safety override rate | `safety_events` count / total messages |
| Context drift | `chat_context.version` increment frequency |
| JSON parse failure rate | Logged to `model_metrics` |
| Avg response latency | Middleware timing → `model_metrics` |

### SLOs
- p95 `POST /message` latency < 10s (local model; hardware-dependent)
- Safety override rate < 5% of messages in normal use
- Classifier error rate < 0.5%

---

## 12. Failure & Risk Analysis

| Risk | Mitigation |
|---|---|
| Hallucinated advice | Strict system prompt + summarized context only + confidence field |
| Ollama model not running | `GET /ready` checks Ollama ping; return 503 if down |
| Small model bad JSON output | JSON parse fallback + disclaimer always appended |
| Context corruption | Periodic re-summarization; version in `chat_context` |
| Token leakage | JWT expiry; refresh rotation; httpOnly cookie |
| Data over-retention | Auto-expiry; `expires_at`; nightly deletion job |
| Abuse / prompt injection | Rate limiting + input length cap (1000 chars) + keyword classifier |
| Summary stuck / corrupt | Re-summarize from last N messages on version mismatch |
| Model swap breaks output format | JSON parse fallback; model version logged in metrics |

---

## 13. Implementation Roadmap

### Phase 1 — Architecture ✅ Complete
- System design, DB schema, safety planning, API spec, RAT design, compliance notes

### Phase 2 — Backend 🔧 In Progress
- FastAPI project setup + Alembic migrations
- Auth (register, login, refresh, logout, consent)
- Chat CRUD + auto-title generation
- Message endpoint (idempotency, safety stub, RAT stub returning placeholder)
- SSE streaming endpoint
- Real RAT: Ollama integration + structured output parser
- Real safety classifier: keyword rules
- Context builder: summarization + sanitization
- Message feedback endpoint
- Structured JSON logging + request IDs

### Phase 3 — AI Layer Hardening
- LLM-based safety classifier (replace keyword rules)
- Red-team safety test suite (injection, roleplay bypass, dosage fishing)
- Evaluation pipeline vs golden Q&A set
- Confidence-threshold logic (low confidence → stronger disclaimer)
- HIPAA alignment if needed

### Phase 4 — Frontend (Loveable)
- Login / register / consent gate
- Chat sidebar + paginated history
- Chat window with SSE streaming
- Thumbs up/down feedback
- Mobile-responsive + WCAG AA

---

## 14. Folder Structure (Backend)

```
health-ai-backend/
├── app/
│   ├── main.py              # FastAPI app + middleware registration
│   ├── config.py            # Settings from env (pydantic-settings)
│   ├── database.py          # Async SQLAlchemy engine + session
│   ├── middleware/
│   │   ├── auth.py          # JWT verification dependency
│   │   └── request_id.py    # Inject X-Request-ID header
│   ├── routers/
│   │   ├── auth.py          # /v1/auth/* + /v1/users/consent
│   │   ├── chats.py         # /v1/chats/*
│   │   ├── messages.py      # /v1/chats/{id}/message + /stream + feedback
│   │   └── ops.py           # /health + /ready
│   ├── services/
│   │   ├── context.py       # Context builder, summarizer, sanitizer
│   │   ├── safety.py        # Classifier, emergency path, escalation
│   │   ├── rat.py           # RAT reasoner → Ollama call + output parser
│   │   └── titles.py        # Auto-title generation from first message
│   ├── models/
│   │   └── db.py            # SQLAlchemy ORM models
│   └── schemas/
│       └── api.py           # Pydantic request/response schemas
├── migrations/
│   └── versions/
├── tests/
│   ├── unit/                # Safety classifier, context sanitizer, JSON parser
│   └── integration/         # Auth flow, chat CRUD, message flow, SSE
├── .env.example
├── alembic.ini
└── requirements.txt
```

---

## 15. Key Decisions

| Decision | Choice | Reason |
|---|---|---|
| AI inference | Ollama (local) | Zero cost; maximum privacy; no external data processor |
| Refresh token storage | httpOnly cookie | Prevents JS access; standard for web clients |
| Response delivery | SSE | Simpler than WebSocket for unidirectional streaming |
| Context update trigger | Every 5 messages OR >800 tokens | Balances freshness vs local inference cost |
| Max context size | 1000 tokens | Keeps prompts bounded for smaller local models |
| Chat title | Auto-generated from first message; user-editable | Best UX default |
| v1 retrieval | None — summarized context only | Tight scope; retrieval is Phase 3 |
| Recommended dev model | `llama3.2:3b` | Fast on low RAM; swap via env var |
