# Order Receipt PDF Specification

## Purpose

Defines the behavior for PDF receipt generation and download for orders in allowed states,
accessible by the order owner (client) and any authorized worker.

---

## Requirements

### Requirement: Client Download Own Receipt

An authenticated client MUST be able to download a PDF receipt for an order they own
when the order is in state APPROVED, READY, SHIPPED, or COMPLETED.
The endpoint MUST return 404 (not 403) when the order ID does not belong to the requesting
client, preventing order enumeration.
The endpoint MUST return 409 when the order is in state PENDING, DENIED, or CANCELED.
Staff users (workers) MUST be blocked from this endpoint with 403.

> **State gate choice**: 409 Conflict (not 400) — the request is syntactically valid but
> conflicts with the current resource state. This matches DRF's `ValidationError` pattern
> for state precondition failures and is semantically cleaner than a generic 400.

#### Scenario: Client downloads receipt for APPROVED order

- GIVEN an authenticated client who owns order `#000042` in state APPROVED
- WHEN they `GET /api/mis-pedidos/42/recibo/`
- THEN the response is HTTP 200 with `Content-Type: application/pdf`
- AND `Content-Disposition: inline; filename="recibo-000042.pdf"`

#### Scenario: Client requests receipt for PENDING order

- GIVEN an authenticated client who owns order `#000099` in state PENDING
- WHEN they `GET /api/mis-pedidos/99/recibo/`
- THEN the response is HTTP 409

#### Scenario: Client requests receipt for CANCELED order

- GIVEN an authenticated client who owns order `#000010` in state CANCELED
- WHEN they `GET /api/mis-pedidos/10/recibo/`
- THEN the response is HTTP 409

#### Scenario: Client A tries to download Client B's receipt

- GIVEN authenticated client A and order `#000077` owned by client B
- WHEN client A sends `GET /api/mis-pedidos/77/recibo/`
- THEN the response is HTTP 404 (not 403, preventing enumeration)

#### Scenario: Worker (staff) hits the client endpoint

- GIVEN an authenticated user with `worker_role = 'total'`
- WHEN they `GET /api/mis-pedidos/42/recibo/`
- THEN the response is HTTP 403

---

### Requirement: Worker Download Any Receipt

An authenticated user with `worker_role in ('total', 'parcial')` MUST be able to download
a PDF receipt for any order via the worker endpoint when the order is in an allowed state.
Any authenticated user without a valid `worker_role` MUST receive 403.
The same state gate applies: APPROVED, READY, SHIPPED, COMPLETED → 200; otherwise → 409.

#### Scenario: Worker (total) downloads receipt

- GIVEN an authenticated user with `worker_role = 'total'` and order `#000042` in state READY
- WHEN they `GET /api/worker/pedidos/42/recibo/`
- THEN the response is HTTP 200 with `Content-Type: application/pdf`

#### Scenario: Worker (parcial) downloads receipt

- GIVEN an authenticated user with `worker_role = 'parcial'` and order `#000055` in state SHIPPED
- WHEN they `GET /api/worker/pedidos/55/recibo/`
- THEN the response is HTTP 200 with `Content-Type: application/pdf`

#### Scenario: Non-worker authenticated user hits worker endpoint

- GIVEN an authenticated user with `worker_role = ''` (no role)
- WHEN they `GET /api/worker/pedidos/42/recibo/`
- THEN the response is HTTP 403

---

### Requirement: PDF Content Contract

The generated PDF MUST contain all of the following fields, reading exclusively from
snapshot data on `PedidoProductosModel` — never from live product or variant records:

| Field | Source |
|-------|--------|
| Business name | Hardcoded: "Importaciones Los Bukis" |
| Folio | `PedidosModel.folio` (zero-padded 6-digit: `000042`) |
| Order created date + time | `PedidosModel.created_at` (long Spanish format with time, e.g. `15 de agosto, 2026 — 14:32`) |
| Order state | `PedidosModel.estado` (human-readable, e.g. "Completado") |
| Client name | `PedidosModel.cliente.nombre + apellido` |
| Client email | `PedidosModel.cliente.correo` |
| Client phone | `PedidosModel.cliente.telefono` (always present; field is non-null) |
| Shipping address | `PedidosModel.direccion.*` (only if non-null) |
| Line items | `PedidoProductosModel`: name, color, qty, unit price, discount %, subtotal — all from snapshot fields |
| Order subtotal | `PedidosModel.subtotal_snapshot` |
| Order total | `PedidosModel.precio_total` |

Fields explicitly excluded from the receipt: `nota_cliente`, `nota_worker` (internal notes),
`comprobante_pago`, `comprobante_deadline`, `requiere_reembolso`.

The system MUST NOT read live product or variant data for any line item field.
When `direccion` is NULL the PDF MUST render successfully without an address block.

#### Scenario: PDF renders all required fields

- GIVEN order `#000042` in COMPLETED state with 2 line items and a shipping address
- WHEN the PDF is generated
- THEN the output contains "Importaciones Los Bukis", "000042", client name, address, both line items with snapshot values, subtotal, and total

#### Scenario: PDF renders without address when direccion is NULL

- GIVEN order `#000007` in APPROVED state where `direccion` is NULL
- WHEN the PDF is generated
- THEN the output contains all required fields except the address block
- AND no error is raised during rendering

#### Scenario: Line items use snapshot data only

- GIVEN an order whose line item has `producto_nombre_snapshot = "Camisa Azul"` but the live product was deleted
- WHEN the PDF is generated
- THEN the line item shows "Camisa Azul" (from snapshot), not an error

---

### Requirement: HTTP Response Contract

The endpoint MUST return:

- HTTP 200 on success
- `Content-Type: application/pdf`
- `Content-Disposition: inline; filename="recibo-{folio}.pdf"` (e.g. `recibo-000042.pdf`)

#### Scenario: Response headers are correct

- GIVEN a successful PDF generation for order `#000042`
- WHEN the response is returned
- THEN `Content-Type` is `application/pdf`
- AND `Content-Disposition` is `inline; filename="recibo-000042.pdf"`

---

### Requirement: Frontend Download Surface — Client

The client order detail page (`PedidoDetallePage`) MUST display a "Descargar recibo" button
when the order state is APPROVED, READY, SHIPPED, or COMPLETED.
The button MUST be absent or disabled when the order state is PENDING, DENIED, or CANCELED.
The download MUST use the existing protected-blob fetch pattern; the new client endpoint path
MUST be included in `PROTECTED_COMPROBANTE_PATHS`.

#### Scenario: Download button visible for APPROVED order

- GIVEN the client is viewing order detail for order `#000042` in state APPROVED
- WHEN the page renders
- THEN a "Descargar recibo" button is visible and enabled

#### Scenario: Download button absent for PENDING order

- GIVEN the client is viewing order detail for order `#000099` in state PENDING
- WHEN the page renders
- THEN no "Descargar recibo" button is visible (or it is disabled)

---

### Requirement: Frontend Download Surface — Worker

The worker order panel (`WorkerOrdersPage` right panel) MUST display a "Descargar recibo"
button when a selected order is in state APPROVED, READY, SHIPPED, or COMPLETED.
The button MUST be absent or disabled for all other states.
The new worker endpoint path MUST be included in `PROTECTED_COMPROBANTE_PATHS`.

#### Scenario: Download button visible for READY order in worker panel

- GIVEN the worker has selected order `#000042` in state READY in the right panel
- WHEN the panel renders
- THEN a "Descargar recibo" button is visible and enabled

#### Scenario: Download button absent for CANCELED order in worker panel

- GIVEN the worker has selected order `#000010` in state CANCELED
- WHEN the panel renders
- THEN no "Descargar recibo" button is visible (or it is disabled)

---

### Requirement: Config Hygiene — Frontend Test Runner

`openspec/config.yaml` frontend testing section MUST reflect the actual runner.
The `runner` field MUST be updated from `none` to `vitest` and the `framework` field
from `none` to `vitest` to match the installed Vitest 3.2.6 and existing `.test.tsx` files.
`strict_tdd_override` MUST remain `false` — adopting strict TDD is a separate process
decision, out of scope for this change.

#### Scenario: Config reflects actual runner after update

- GIVEN `openspec/config.yaml` has been updated as part of this change
- WHEN a reviewer reads the config
- THEN `testing.frontend.runner` is `vitest`, not `none`
- AND `testing.frontend.strict_tdd_override` is `false` (unchanged)
