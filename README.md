# Health AI Conversational System

A **design-first, production-grade** architecture for a privacy-preserving Health AI conversational system.  
The system uses **Retrieval-Augmented Thought (RAT)** to enable safe reasoning without exposing chain-of-thought.

> **Status:** Architecture & Design Phase

---

## What This Repo Is

* **Reference architecture** for building safe, multi-user Health AI chat systems.
* **Build-ready design** — database schema, API spec, context strategy, safety flows, and risk analysis.
* **Demonstration** of AI systems thinking and safety-aware design.

This repository is currently in the **architecture and design phase**. Implementation follows the roadmap in the architecture document.

---

## Key Design Choices

| Concern | Approach |
|--------|----------|
| **Privacy** | Summarized context only; no full chat history or chain-of-thought stored or sent to the model. |
| **Safety** | Layered safety classifier; emergency path and escalation; medication rule (no specific dosage). |
| **Reasoning** | RAT: internal reasoning hidden; only final, cautious answers exposed. |
| **APIs** | Stateless, JWT + refresh tokens, versioned (`/v1`), paginated, rate-limited, standard errors. |
| **Compliance** | Data minimization, retention/expiry, audit logging; HIPAA/GDPR alignment in roadmap. |

---

## Repository Layout

```
docs/
  ARCHITECTURE.md   # Full system design, DB schema, safety, context, RAT, compliance, roadmap
  API_SPEC.md       # REST API: versioning, auth, errors, pagination, rate limits, endpoints
README.md           # This file
```

---

## Quick Links

* **[Architecture & design](docs/ARCHITECTURE.md)** — System overview, database design, context management, safety layer, RAT design, compliance, risk analysis, implementation roadmap.
* **[API specification](docs/API_SPEC.md)** — Endpoints, authentication, error format, pagination, rate limiting, health checks.

---

## Non-Goals

* Medical diagnosis or treatment.
* Replacing healthcare professionals.
* Storing or exposing chain-of-thought or raw retrieved documents.
