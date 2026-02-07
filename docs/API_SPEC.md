# Health AI Conversational System — API Specification

This document details the REST API for the Health AI Conversational System. All endpoints are **versioned** under `/v1`.

---

## 1. Base URL & Versioning

* **Base path:** `/v1` (e.g. `https://api.example.com/v1`).
* **Versioning:** Path-based. Future breaking changes introduce `/v2`; `/v1` remains supported per deprecation policy.

---

## 2. Authentication

### 2.1 Register

```http
POST /v1/auth/register
Content-Type: application/json
```

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Responses:**

* `201 Created` — User created; body may include `user_id`, `email` (no password).
* `400 Bad Request` — Validation error (e.g. invalid email, weak password).
* `409 Conflict` — Email already registered.

---

### 2.2 Login

```http
POST /v1/auth/login
Content-Type: application/json
```

**Request body:**

```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200 OK):**

```json
{
  "access_token": "eyJ...",
  "refresh_token": "rt_...",
  "token_type": "Bearer",
  "expires_in": 900
}
```

* **Access token:** Short-lived (e.g. 15 minutes). Send in `Authorization: Bearer <access_token>`.
* **Refresh token:** Long-lived, used only at `POST /v1/auth/refresh`. Store securely (e.g. httpOnly cookie or secure client storage). Rotate on use.

**Error responses:**

* `401 Unauthorized` — Invalid credentials.

---

### 2.3 Refresh Token

```http
POST /v1/auth/refresh
Content-Type: application/json
```

**Request body:**

```json
{
  "refresh_token": "rt_..."
}
```

**Response (200 OK):** Same shape as login (`access_token`, optional new `refresh_token`, `expires_in`).

**Error responses:**

* `401 Unauthorized` — Invalid or revoked refresh token.

---

### 2.4 Protected Endpoints

All chat and message endpoints require:

```http
Authorization: Bearer <access_token>
```

* `401 Unauthorized` — Missing or invalid/expired access token.
* `403 Forbidden` — Valid token but not allowed to access the resource (e.g. another user's chat).

---

## 3. Error Format

All error responses use a **standard envelope**:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Retry after 60 seconds.",
    "details": {
      "retry_after": 60
    }
  }
}
```

**Common HTTP status codes:**

| Status | Usage |
|--------|--------|
| 400 | Bad Request — validation, malformed body |
| 401 | Unauthorized — missing/invalid token |
| 403 | Forbidden — no access to resource |
| 404 | Not Found — chat or resource missing |
| 409 | Conflict — e.g. idempotency key duplicate (return existing response) |
| 429 | Too Many Requests — rate limit exceeded |
| 503 | Service Unavailable — model or safety service down |

**Error codes (examples):** `VALIDATION_ERROR`, `UNAUTHORIZED`, `FORBIDDEN`, `NOT_FOUND`, `RATE_LIMIT_EXCEEDED`, `SERVICE_UNAVAILABLE`, `SAFETY_OVERRIDE` (when a safe template was returned).

---

## 4. Pagination

List endpoints support **cursor-based** or **offset-based** pagination. Same pattern for `GET /v1/chats` and `GET /v1/chats/{chat_id}/messages`.

### Query parameters

| Parameter | Type   | Default | Description |
|-----------|--------|--------|-------------|
| `limit`  | integer | 20     | Page size (max 50) |
| `cursor` | string  | —      | Opaque cursor for next page (from previous response) |

**Example (cursor-based):**

```http
GET /v1/chats?limit=20
GET /v1/chats?limit=20&cursor=eyJ...
```

**Response shape (list):**

```json
{
  "data": [ ... ],
  "next_cursor": "eyJ..." | null,
  "has_more": true
}
```

If **offset-based** is used instead:

* Params: `limit` (max 50), `offset` (default 0).
* Response: `data`, `total` (optional), `limit`, `offset`.

---

## 5. Rate Limiting

* **Scope:** Per user (by `user_id` from JWT). Optionally also per IP for unauthenticated or auth endpoints.
* **Limits:** e.g. 60 requests/minute per user for chat/message endpoints; stricter for auth if needed.
* **Response when exceeded:** `429 Too Many Requests` with standard error body and `Retry-After` header (seconds).

Example error:

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Retry after 60 seconds.",
    "details": { "retry_after": 60 }
  }
}
```

---

## 6. Health & Readiness

```http
GET /health
```

* **200 OK** — Service is alive (liveness).

```http
GET /ready
```

* **200 OK** — Service is ready to accept traffic (e.g. DB and critical dependencies up).
* **503 Service Unavailable** — Not ready (e.g. DB down).

These endpoints are **unversioned** and typically **unauthenticated**.

---

## 7. Chat Endpoints

### 7.1 Create chat

```http
POST /v1/chats
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request body (optional):**

```json
{
  "title": "My first chat"
}
```

**Response (201 Created):**

```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "My first chat",
  "created_at": "2025-02-07T12:00:00Z",
  "expires_at": "2025-05-08T12:00:00Z"
}
```

---

### 7.2 List chats

```http
GET /v1/chats?limit=20&cursor=...
Authorization: Bearer <access_token>
```

* Returns only chats for the authenticated user, **excluding** soft-deleted (`is_deleted = true`).
* Ordered by `created_at` descending.
* Paginated per §4.

---

### 7.3 Get chat

```http
GET /v1/chats/{chat_id}
Authorization: Bearer <access_token>
```

**Response (200 OK):** Single chat object. **404** if not found or not owned by user.

---

### 7.4 Send message (idempotent)

```http
POST /v1/chats/{chat_id}/message
Authorization: Bearer <access_token>
Idempotency-Key: <opaque_key>
Content-Type: application/json
```

**Request body:**

```json
{
  "content": "I have had a mild fever for 2 days."
}
```

* **Idempotency-Key:** Optional. If provided and a message with the same key already exists for this chat, return **200** with the **existing** assistant response (no new model call).
* **Response (200 OK):** Assistant reply, e.g.:

```json
{
  "message_id": "uuid",
  "role": "assistant",
  "content": "...",
  "created_at": "2025-02-07T12:01:00Z"
}
```

**Errors:**

* **404** — Chat not found or not owned.
* **429** — Rate limited.
* **503** — Model or safety service unavailable (user sees safe fallback message).

---

### 7.5 List messages

```http
GET /v1/chats/{chat_id}/messages?limit=50&cursor=...
Authorization: Bearer <access_token>
```

* Returns messages for the chat in **chronological order**.
* Exclude messages with `is_deleted = true` if soft delete is implemented.
* Paginated per §4; **max page size** 50.

---

### 7.6 Delete chat

```http
DELETE /v1/chats/{chat_id}
Authorization: Bearer <access_token>
```

* Soft delete: set `is_deleted = true` (or equivalent). **204 No Content** on success. **404** if not found or not owned.

---

## 8. Admin API (Optional)

* **Scope:** Read-only or tightly scoped actions for support/compliance.
* **Auth:** Separate admin role; admin JWT or API key.
* **Examples:** `GET /v1/admin/safety-events`, export for audit. Not exposed to normal users.

---

## 9. Summary Table

| Method | Path | Auth | Pagination | Idempotency | Rate limit |
|--------|------|------|------------|-------------|------------|
| POST   | /v1/auth/register | — | — | — | Optional |
| POST   | /v1/auth/login    | — | — | — | Optional |
| POST   | /v1/auth/refresh  | — | — | — | Optional |
| GET    | /health           | — | — | — | — |
| GET    | /ready            | — | — | — | — |
| POST   | /v1/chats         | JWT | — | — | Yes |
| GET    | /v1/chats         | JWT | Yes (cursor, max 50) | — | Yes |
| GET    | /v1/chats/{id}    | JWT | — | — | Yes |
| POST   | /v1/chats/{id}/message | JWT | — | Idempotency-Key | Yes |
| GET    | /v1/chats/{id}/messages | JWT | Yes (cursor, max 50) | — | Yes |
| DELETE | /v1/chats/{id}    | JWT | — | — | Yes |
