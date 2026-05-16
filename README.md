# Health AI Conversational System

A **design-first, privacy-preserving** Health AI conversational system.  
Uses **Retrieval-Augmented Thought (RAT)** with a **local LLM via Ollama** — no data ever leaves your machine.

> **Status:** Architecture & Design Complete — Backend Implementation In Progress

---

## Why Local LLM?

Running inference locally via Ollama means:
- **Zero cost** — no API fees, no rate limits from a provider
- **Maximum privacy** — patient health queries never touch an external server
- **HIPAA/GDPR alignment by default** — no third-party data processor for the AI layer
- **Works offline** — no dependency on external API availability

---

## Key Design Choices

| Concern | Approach |
|---|---|
| **AI Model** | Local Ollama (`llama3.2` or `mistral`) — no external API |
| **Privacy** | Summarized context only; no full history or chain-of-thought sent to model |
| **Safety** | Layered safety classifier; emergency path, escalation, medication hard rule |
| **Reasoning** | RAT: internal reasoning hidden; only final cautious answers exposed |
| **Streaming** | SSE (Server-Sent Events) for real-time response streaming |
| **APIs** | Stateless, JWT + httpOnly refresh cookie, versioned (`/v1`), cursor-paginated, rate-limited |
| **Compliance** | Data minimization, retention/expiry, audit logging; HIPAA/GDPR alignment |
| **Consent** | Explicit user consent gate before first chat (DB-tracked) |
| **Feedback** | Thumbs up/down on every assistant message for quality tracking |

---

## Repository Layout

```
docs/
  ARCHITECTURE.md    # Full system design, DB schema, safety, RAT, compliance, roadmap
  API_SPEC.md        # REST API: versioning, auth, errors, pagination, rate limits, endpoints
README.md            # This file
```

---

## Recommended Ollama Models

| Model | RAM needed | Best for |
|---|---|---|
| `llama3.2:3b` | ~4 GB | Fast responses, low-resource machines |
| `llama3.1:8b` | ~8 GB | Better reasoning quality |
| `mistral:7b` | ~8 GB | Strong instruction-following |
| `gemma2:9b` | ~10 GB | Good balance of safety + quality |

Start with `llama3.2:3b` for dev. Switch to `llama3.1:8b` or `mistral:7b` for better health response quality.

Pull a model:
```bash
ollama pull llama3.2:3b
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| Database | PostgreSQL |
| ORM + Migrations | SQLAlchemy (async) + Alembic |
| Auth | JWT (access) + httpOnly cookie (refresh) |
| AI Inference | Ollama (local) |
| Streaming | Server-Sent Events (SSE) |
| Frontend | React via Loveable (Phase 4) |
| Deployment | Railway / Render (Phase 2+) |

---

## Non-Goals

- Medical diagnosis or treatment
- Replacing healthcare professionals
- Storing or exposing chain-of-thought or raw retrieved documents
- Sending health data to any external AI provider

---

## Implementation Phases

| Phase | Scope | Status |
|---|---|---|
| 1 | Architecture & Design | ✅ Complete |
| 2 | Backend (Auth, Chat, Message, Safety, RAT) | 🔧 In Progress |
| 3 | AI Layer Hardening (real classifier, red-team, evals) | ⬜ Planned |
| 4 | Frontend via Loveable | ⬜ Planned |

---

## About

Design-first, privacy-preserving Health AI conversational system using Retrieval-Augmented Thought (RAT) and local LLM inference via Ollama.
