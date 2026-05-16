# Health AI Conversational System — API Specification

---

## Overview

- **Base path:** `/v1`
- **Protocol:** HTTPS (HTTP in local dev)
- **Auth:** Bearer JWT on all protected routes
- **Content-Type:** `application/json` (except SSE endpoint)
- **Errors:** Standard envelope on all 4xx/5xx
- **Pagination:** Cursor-based on all list endpoints

---

## Versioning

All endpoints are prefixed with `/v1`. Future breaking changes introduce `/v2` without removing `/v1` until clients migrate.

---

## Authentication

### Token Strategy
- **Access token:** JWT, 15-minute TTL, sent as `Authorization: Bearer <token>`
- **Refresh token:** Opaque token, 7-day TTL, stored in `httpOnly; Secure; SameSite=Strict` cookie
- On access token expiry, client calls `POST /v1/auth/refresh` to get a new one silently

---

## Error Format

All errors use this envelope:

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {}
  }
}
```

### Common Error Codes
| HTTP | code | Meaning |
|---|---|---|
| 400 | `validation_error` | Invalid request body or params |
| 401 | `unauthorized` | Missing or invalid access token |
| 403 | `forbidden` | Authenticated but not allowed (e.g. wrong user's chat) |
| 403 | `consent_required` | User has not completed consent gate |
| 404 | `not_found` | Resource does not exist |
| 409 | `conflict` | Duplicate idempotency key with different body |
| 422 | `unprocessable` | Semantically invalid input |
| 429 | `rate_limited` | Too many requests |
| 503 | `service_unavailable` | Ollama or DB not reachable |

---

## Pagination

All list endpoints use cursor-based pagination.

**Query params:** `cursor` (opaque string), `limit` (int, default 20, max 50)

**Response envelope:**
```json
{
  "data": [...],
  "next_cursor": "string | null",
  "limit": 20
}
```

`next_cursor: null` means no more pages.

---

## Endpoints

---

### Auth

#### `POST /v1/auth/register`

Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "string (min 8 chars)"
}
```

**Response `201`:**
```json
{
  "user_id": "uuid",
  "email": "user@example.com",
  "access_token": "string"
}
```
Sets `httpOnly` refresh cookie.

**Errors:** `400` validation, `409` email already registered

---

#### `POST /v1/auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "string"
}
```

**Response `200`:**
```json
{
  "user_id": "uuid",
  "access_token": "string"
}
```
Sets `httpOnly` refresh cookie.

**Errors:** `401` invalid credentials

---

#### `POST /v1/auth/refresh`

Exchange refresh cookie for a new access token. No request body needed.

**Response `200`:**
```json
{
  "access_token": "string"
}
```

**Errors:** `401` missing or expired refresh cookie

---

#### `POST /v1/auth/logout`

Clears the refresh cookie. No request body.

**Response `204`** — no content

---

### Users

#### `POST /v1/users/consent`  🔒 auth required

Record that the authenticated user has accepted the terms of use. Must be called before the first chat is created. Returns `403 consent_required` on chat/message endpoints until this is done.

**Request:**
```json
{
  "accepted": true
}
```

**Response `200`:**
```json
{
  "consent_given": true,
  "consent_at": "2025-05-17T10:00:00Z"
}
```

**Errors:** `400` if `accepted` is false

---

### Chats

All chat endpoints require auth. Users can only access their own chats.

#### `POST /v1/chats`  🔒

Create a new chat. Title is auto-generated from the first message later; placeholder used until then.

**Request:** _(empty body or optional title)_
```json
{
  "title": "string (optional)"
}
```

**Response `201`:**
```json
{
  "id": "uuid",
  "title": "New chat",
  "created_at": "ISO8601",
  "expires_at": "ISO8601"
}
```

**Errors:** `403 consent_required` if user has not consented

---

#### `GET /v1/chats`  🔒

List current user's chats, newest first.

**Query params:** `cursor`, `limit`

**Response `200`:**
```json
{
  "data": [
    {
      "id": "uuid",
      "title": "string",
      "created_at": "ISO8601",
      "expires_at": "ISO8601"
    }
  ],
  "next_cursor": "string | null",
  "limit": 20
}
```

---

#### `GET /v1/chats/{chat_id}`  🔒

**Response `200`:**
```json
{
  "id": "uuid",
  "title": "string",
  "created_at": "ISO8601",
  "expires_at": "ISO8601"
}
```

**Errors:** `403` wrong user, `404` not found

---

#### `PATCH /v1/chats/{chat_id}`  🔒

Rename a chat.

**Request:**
```json
{
  "title": "string"
}
```

**Response `200`:**
```json
{
  "id": "uuid",
  "title": "string"
}
```

---

#### `DELETE /v1/chats/{chat_id}`  🔒

Soft-deletes the chat and all its messages.

**Response `204`** — no content

---

### Messages

#### `POST /v1/chats/{chat_id}/message`  🔒

Send a message and receive the full AI response (non-streaming).

**Headers:**
- `Idempotency-Key: <uuid>` (optional) — prevents duplicate model calls on retry

**Request:**
```json
{
  "content": "string (max 1000 chars)"
}
```

**Response `200`:**
```json
{
  "message_id": "uuid",
  "role": "assistant",
  "content": "string",
  "disclaimer": "This is for informational purposes only. Please consult a healthcare professional.",
  "confidence": "low | medium | high",
  "safety_overridden": false,
  "created_at": "ISO8601"
}
```

If `safety_overridden: true`, `confidence` is omitted and `content` is a canned safe response.

**Errors:** `400` content too long, `403` wrong user / consent required, `429` rate limited, `503` Ollama unavailable

---

#### `GET /v1/chats/{chat_id}/stream`  🔒

Stream the AI response token by token via SSE.

**Query params:**
- `message` — URL-encoded message content (max 1000 chars)
- `idempotency_key` — optional

**Response:** `Content-Type: text/event-stream`

```
data: {"token": "Based"}

data: {"token": " on"}

data: {"token": " your"}

data: {"token": " symptoms"}

data: [DONE]
```

On safety override:
```
data: {"safety_overridden": true, "content": "Please contact emergency services immediately."}

data: [DONE]
```

On error mid-stream:
```
data: {"error": "service_unavailable"}

data: [DONE]
```

**Errors (before stream starts):** `400`, `403`, `429`, `503` — standard JSON error envelope

---

#### `GET /v1/chats/{chat_id}/messages`  🔒

Paginated message history for a chat, oldest first.

**Query params:** `cursor`, `limit`

**Response `200`:**
```json
{
  "data": [
    {
      "id": "uuid",
      "role": "user | assistant",
      "content": "string",
      "disclaimer": "string | null",
      "confidence": "low | medium | high | null",
      "safety_overridden": false,
      "created_at": "ISO8601"
    }
  ],
  "next_cursor": "string | null",
  "limit": 50
}
```

---

### Feedback

#### `POST /v1/messages/{message_id}/feedback`  🔒

Submit thumbs up/down on an assistant message. Only valid for `role: assistant` messages belonging to the authenticated user's chats.

**Request:**
```json
{
  "rating": 1,
  "note": "string (optional)"
}
```
`rating`: `1` = thumbs up, `-1` = thumbs down

**Response `201`:**
```json
{
  "id": "uuid",
  "message_id": "uuid",
  "rating": 1,
  "created_at": "ISO8601"
}
```

**Errors:** `400` invalid rating, `403` not user's message, `404` message not found, `409` feedback already submitted for this message

---

### Ops

#### `GET /health`

Always returns 200 if the process is alive. No auth required.

**Response `200`:**
```json
{
  "status": "ok"
}
```

---

#### `GET /ready`

Checks DB and Ollama connectivity. No auth required.

**Response `200`:**
```json
{
  "status": "ready",
  "db": "ok",
  "ollama": "ok"
}
```

**Response `503`:**
```json
{
  "status": "not_ready",
  "db": "ok",
  "ollama": "error"
}
```

---

## Rate Limits

| Endpoint | Limit | Response on exceed |
|---|---|---|
| `POST /v1/auth/register` | 10 req/min per IP | `429` |
| `POST /v1/auth/login` | 10 req/min per IP | `429` |
| `POST /v1/chats/{id}/message` | 20 req/min per user | `429` |
| `GET /v1/chats/{id}/stream` | 20 req/min per user | `429` |
| All other endpoints | 60 req/min per user | `429` |

`429` response includes:
```json
{
  "error": {
    "code": "rate_limited",
    "message": "Too many requests. Please slow down.",
    "details": { "retry_after_seconds": 30 }
  }
}
```

---

## Ollama Availability

If Ollama is unreachable when a message is sent:
- Return `503 service_unavailable`
- Do **not** store the user's message
- Log a `safety_events` record with `event_type: "model_unavailable"`
- Client should retry after `GET /ready` returns `"ollama": "ok"`

---

## Changelog

| Version | Change |
|---|---|
| v1.0 | Initial spec — auth, chats, messages, SSE streaming, feedback, ops |
