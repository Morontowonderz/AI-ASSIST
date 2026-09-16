# ShadowSpark AI-ASSIST — API Contract Specification (v1.1.0)

## 1. Global Request Headers

| Header | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `Authorization` | `string` | **Yes** | Bearer token format: `Bearer <token>`. In production, matches `SHADOWSPARK_API_TOKEN`. |
| `X-Tenant-Slug` | `string` | **Conditional** | Target tenant identifier matching `^[a-z0-9][a-z0-9_-]{0,63}$`. **Mandatory in production**. |
| `X-Tenant-ID` | `string` | **Conditional** | Alternative header alias for `X-Tenant-Slug`. Accepted interchangeably. |
| `Idempotency-Key` | `string` | **Yes (POST)** | Required on all mutating requests (`POST`). Max length 128 characters. |
| `X-Request-ID` | `string` | No | Distributed tracing UUID. Echoed back in all response headers. Generated if omitted. |

---

## 2. Global Error Format

All `4xx` and `5xx` error responses adhere to the standard error model:

```json
{
  "detail": "Human-readable explanation of failure"
}
```

Common status codes:
- `400 Bad Request`: Validation failure, missing required headers (`Idempotency-Key`), or invalid tenant identifier.
- `401 Unauthorized`: Invalid or missing `Authorization` header, or missing tenant header in production.
- `403 Forbidden`: Authenticated token lacks required scope (`compliance:read` or `compliance:review`).
- `404 Not Found`: Resource does not exist, or belongs to another tenant.
- `409 Conflict`: Reusing an `Idempotency-Key` with a different request payload or annotation text.
- `422 Unprocessable Entity`: Input contains raw sensitive personal identifiers (11-digit national identity numbers).
- `429 Too Many Requests`: Triggered if policy rate limits or budget thresholds trip (`LLM06:2026`).

---

## 3. Endpoints

### 3.1 `GET /healthz`

Service liveness and readiness probe.

- **Authentication**: None required.
- **Request Headers**: None required.
- **Success Response (200 OK)**:
  ```json
  {
    "status": "ok"
  }
  ```

---

### 3.2 `POST /v1/compliance-review-brief`

Generates or replays a deterministic compliance brief for a given exception.

- **Authentication**: Requires `compliance:read` scope.
- **Headers**:
  - `Authorization: Bearer <token>` (Required)
  - `X-Tenant-Slug: <tenant_id>` or `X-Tenant-ID: <tenant_id>` (Required in production)
  - `Idempotency-Key: <unique_key>` (Required, max 128 chars)
  - `X-Request-ID: <uuid>` (Optional)
- **Request Body (`application/json`)**:
  ```json
  {
    "exception_id": "ex_a_021",
    "tenant_id": "tenant_a"
  }
  ```
  *Note: `tenant_id` in body is optional, but if provided it MUST match the tenant header.*
- **Success Response (201 Created)**:
  ```json
  {
    "brief_id": "brief_4a8b79f1...",
    "output": {
      "exception_id": "ex_a_021",
      "status": "review_required",
      "brief": {
        "summary": "Compliance exception evaluation summary...",
        "risk_flags": ["AML_FLAG_01"],
        "recommendation": "escalate"
      }
    },
    "tool_trace": [
      {"tool": "read_exception", "result": "ok"}
    ],
    "replayed": false
  }
  ```

---

### 3.3 `GET /v1/review-queue`

Retrieves a paginated list of tenant-scoped review queue items.

- **Authentication**: Requires `compliance:read` scope.
- **Headers**:
  - `Authorization: Bearer <token>` (Required)
  - `X-Tenant-Slug: <tenant_id>` or `X-Tenant-ID: <tenant_id>` (Required in production)
- **Query Parameters**:
  - `limit`: `integer` (Optional, default: 50, min: 1, max: 100). Number of items per page.
  - `offset`: `integer` (Optional, default: 0, min: 0). Pagination offset.
  - `state`: `string` (Optional, values: `pending_review`, `annotated`). Filters queue by state.
- **Success Response (200 OK)**:
  ```json
  {
    "items": [
      {
        "brief_id": "brief_4a8b79f1...",
        "tenant_id": "tenant_a",
        "exception_id": "ex_a_021",
        "queue_state": "pending_review",
        "sor_status_unchanged": true,
        "created_at": "2026-09-16T11:45:00.000000+00:00",
        "updated_at": "2026-09-16T11:45:00.000000+00:00"
      }
    ],
    "total": 1,
    "limit": 50,
    "offset": 0
  }
  ```

---

### 3.4 `GET /v1/review-queue/{brief_id}`

Inspects a specific review queue entry, including stored brief output and full annotation history.

- **Authentication**: Requires `compliance:read` scope.
- **Headers**:
  - `Authorization: Bearer <token>` (Required)
  - `X-Tenant-Slug: <tenant_id>` or `X-Tenant-ID: <tenant_id>` (Required in production)
- **Success Response (200 OK)**:
  ```json
  {
    "brief_id": "brief_4a8b79f1...",
    "tenant_id": "tenant_a",
    "exception_id": "ex_a_021",
    "output": {
      "exception_id": "ex_a_021",
      "status": "review_required",
      "brief": { ... }
    },
    "queue_state": "annotated",
    "sor_status_unchanged": true,
    "annotations": [
      {
        "annotation_id": "8f3b2a...",
        "operator_id": "token:abc123456789",
        "annotation": "Confirmed exception details with compliance lead.",
        "created_at": "2026-09-16T11:46:12.000000+00:00"
      }
    ],
    "created_at": "2026-09-16T11:45:00.000000+00:00",
    "updated_at": "2026-09-16T11:46:12.000000+00:00"
  }
  ```

---

### 3.5 `POST /v1/review-queue/{brief_id}/annotations`

Appends an immutable audit annotation to the tenant-scoped review queue entry.

- **Authentication**: Requires `compliance:review` scope.
- **Headers**:
  - `Authorization: Bearer <token>` (Required)
  - `X-Tenant-Slug: <tenant_id>` or `X-Tenant-ID: <tenant_id>` (Required in production)
  - `Idempotency-Key: <unique_key>` (Required, max 128 chars)
  - `X-Request-ID: <uuid>` (Optional)
- **Request Body (`application/json`)**:
  ```json
  {
    "annotation": "Operator review completed. Escalation confirmed."
  }
  ```
- **Success Response (200 OK)**:
  Returns the updated `ReviewQueueResponse` model (same as `GET /v1/review-queue/{brief_id}`).
