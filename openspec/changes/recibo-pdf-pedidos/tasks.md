# Tasks: Order Receipt PDF (recibo-pdf-pedidos)

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 160–200 |
| 400-line budget risk | Low |
| Chained PRs recommended | No |
| Suggested split | Single PR |
| Delivery strategy | ask-on-risk |
| Chain strategy | N/A (single PR) |

Decision needed before apply: No
Chained PRs recommended: No
Chain strategy: pending
400-line budget risk: Low

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Backend foundation (dep + helper + template) | Single PR | N/A — no consumer yet | N/A — inert helper code, no route wired | Delete `recibos.py` + `recibo_pedido.html` + revert `requirements.txt` |
| 2 | Backend views + URLs + tests | Single PR | `DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_recibo_pdf` | `curl -H "Authorization: Bearer <token>" http://localhost:8000/api/mis-pedidos/42/recibo/` | Remove 2 views, 2 URL entries, `test_recibo_pdf.py` |
| 3 | Frontend service + allowlist + tests | Single PR | `npm run test -- services/pedidos` | N/A — no UI button yet; service is pure function | Revert `pedidos.ts` additions + `comprobante.ts` allowlist delta |
| 4 | Frontend UI buttons | Single PR | `npm run test -- PedidoDetallePage` | Open app, navigate to APPROVED order → verify button visible | Revert button JSX in `PedidoDetallePage.tsx` + `WorkerOrdersPage.tsx` |
| 5 | End-to-end smoke test | Not a commit | Manual browser test — no automated command | Start backend + frontend locally, login as client, open an APPROVED order, click "Descargar recibo", verify PDF renders correctly | N/A — no code changes |

---

## Phase 1: Backend Foundation
> Commit 1 — dep + helper module + template (inert; no view wiring)

- [x] 1.1 Add `xhtml2pdf==0.2.17` to `catalogo-bukis-backend/requirements.txt`.
  — Done when: file contains the pinned line; `pip install -r requirements.txt` resolves without error.
  — Deps: none.
  — ~1 line.

- [x] 1.2 Create `catalogo_backend/api/utils/recibos.py` with `RECIBO_ALLOWED_STATES` (frozenset), `render_recibo_html(pedido)`, `render_recibo_pdf_bytes(html) → bytes` (raises `RuntimeError` on pisa error), and `build_recibo_pdf_response(pdf_bytes, folio) → HttpResponse`.
  — Done when: module imports cleanly; `RECIBO_ALLOWED_STATES == frozenset({"APPROVED","READY","SHIPPED","COMPLETED"})`.
  — Deps: 1.1.
  — ~45 lines.

- [x] 1.3 Create `catalogo_backend/api/templates/recibo/recibo_pedido.html` adapting the Clásico mockup to xhtml2pdf CSS constraints: `<table>`-based layout, inline `<style>` only, Georgia/Times serif, centered header (`IMPORTACIONES LOS BUKIS` + subtitle), beige `#f4f1ec` items table header, conditional `{% if direccion %}` address block, em-dash for zero-discount items, italic footer. Context vars: `folio`, `fecha`, `estado_label`, `cliente`, `direccion`, `items`, `subtotal`, `total`, `business_name`.
  — Done when: `render_to_string("recibo/recibo_pedido.html", context)` returns HTML containing "Importaciones Los Bukis" and a `<table class="items">` block.
  — Deps: 1.2.
  — ~80 lines.

---

## Phase 2: Backend Views + URLs + Tests
> Commit 2 — two views, two routes, full test suite

- [x] 2.1 Add `MiPedidoReciboPdfView` to `catalogo_backend/api/views/pedidosViews.py`: `[IsAuthenticated]` permission, `queryset.filter(cliente=request.user)` (returns 404 for other clients), explicit `worker_role in ('total','parcial')` → 403 guard (mirror the exact pattern used by `MiPedidoComprobanteUpdateView` — do NOT use `is_staff`), state gate (`estado not in RECIBO_ALLOWED_STATES` → 409), calls `render_recibo_html` + `render_recibo_pdf_bytes` + `build_recibo_pdf_response`.
  — Done when: `GET /api/mis-pedidos/42/recibo/` returns 200 with `Content-Type: application/pdf` and `Content-Disposition: inline; filename="recibo-000042.pdf"` for an APPROVED order owned by the caller.
  — Deps: 1.2, 1.3.
  — ~25 lines.

- [x] 2.2 Add `WorkerPedidoReciboPdfView` to `catalogo_backend/api/views/workerViews.py`: `[IsAuthenticated, IsWorker]` permissions, `get_object_or_404(PedidosModel, pk=pedido_id)`, same state gate → 409, delegates to same helper chain.
  — Done when: `GET /api/worker/pedidos/42/recibo/` returns 200 for `worker_role='total'` user and 403 for a non-worker.
  — Deps: 1.2, 1.3.
  — ~18 lines.

- [x] 2.3 Register two URL routes in `catalogo_backend/api/urls.py`:
  - `mis-pedidos/<int:id>/recibo/` → `MiPedidoReciboPdfView` (name: `mi-pedido-recibo`)
  - `worker/pedidos/<int:pedido_id>/recibo/` → `WorkerPedidoReciboPdfView` (name: `worker-pedido-recibo`)
  — Done when: `python manage.py check` passes and both routes are listed by `python manage.py show_urls` (or equivalent).
  — Deps: 2.1, 2.2.
  — ~4 lines.

- [x] 2.4 Create `catalogo_backend/api/tests/test_recibo_pdf.py` covering all spec scenarios:
  - Client: owner+APPROVED → 200, owner+PENDING → 409, owner+CANCELED → 409, other-client → 404, unauthenticated → 401, worker-on-client-endpoint → 403.
  - Worker: total+READY → 200, parcial+SHIPPED → 200, no-role+any → 403.
  - Content contract: response `Content-Type == "application/pdf"`, `Content-Disposition` contains `"recibo-000042.pdf"`, bytes start with `b"%PDF"`.
  - Null-address: order with `direccion=None` → 200, no exception.
  — Done when: `DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_recibo_pdf` passes all cases.
  — Deps: 2.1, 2.2, 2.3.
  — ~55 lines.

---

## Phase 3: Frontend Service + Allowlist + Tests
> Commit 3 — service functions + allowlist delta + service tests

- [ ] 3.1 Add to `catalogo-frontend/src/services/pedidos.ts`:
  - Export `RECIBO_ALLOWED_STATES = ["APPROVED","READY","SHIPPED","COMPLETED"] as const`.
  - Export `downloadReciboPdf(pedidoId: number): Promise<void>` — calls `openProtectedComprobante("/api/mis-pedidos/${pedidoId}/recibo/")`.
  - Export `downloadReciboPdfWorker(pedidoId: number): Promise<void>` — calls `openProtectedComprobante("/api/worker/pedidos/${pedidoId}/recibo/")`.
  — Done when: functions are exported and TypeScript compiles without errors (`npx tsc -b --noEmit`).
  — Deps: none (pure additions).
  — ~12 lines.

- [ ] 3.2 Extend `PROTECTED_COMPROBANTE_PATHS` in `catalogo-frontend/src/services/comprobante.ts` with two new regexes: `/^\/api\/mis-pedidos\/\d+\/recibo\/?$/` and `/^\/api\/worker\/pedidos\/\d+\/recibo\/?$/`.
  — Done when: `openProtectedComprobante("/api/mis-pedidos/42/recibo/")` no longer throws "must target a protected comprobante endpoint".
  — Deps: 3.1.
  — ~2 lines.

- [ ] 3.3 Write service unit tests (Vitest) verifying: `downloadReciboPdf` calls `openProtectedComprobante` with correct client URL; `downloadReciboPdfWorker` calls it with correct worker URL; allowlist accepts `/api/mis-pedidos/42/recibo/` and `/api/worker/pedidos/42/recibo/`; allowlist rejects `/api/mis-pedidos/42/recibo-x/` and paths with query params.
  — Done when: `npm run test -- services/pedidos` passes all assertions (mock `openProtectedComprobante`).
  — Deps: 3.1, 3.2.
  — ~30 lines.

---

## Phase 4: Frontend UI Buttons
> Commit 4 — client button + worker button

- [ ] 4.1 Add "Descargar recibo" button to `catalogo-frontend/src/components/pages/PedidoDetallePage.tsx` in the existing actions row. Button renders only when `pedido.estado ∈ RECIBO_ALLOWED_STATES`. On click: spinner replaces label, calls `downloadReciboPdf(pedido.id)`, on error shows existing toast. Import `RECIBO_ALLOWED_STATES` and `downloadReciboPdf` from `services/pedidos.ts`.
  — Done when: button is visible for APPROVED order, absent for PENDING, download triggers correctly (manual test or RTL assertion).
  — Deps: 3.1, 3.2.
  — ~15 lines.

- [ ] 4.2 Add "Descargar recibo" button to right panel of `catalogo-frontend/src/components/pages/WorkerOrdersPage.tsx` inside the `selectedOrder !== null` block, adjacent to existing per-order actions. Same state gate and spinner pattern. Calls `downloadReciboPdfWorker(selectedOrder.id)`.
  — Done when: button renders for READY worker order, absent for CANCELED; no layout regression in right panel.
  — Deps: 3.1, 3.2, 4.1.
  — ~15 lines.

---

## Phase 5: End-to-End Smoke Test (no commit)
> Manual verification before opening PR — no code, no commit

- [ ] 5.1 Start backend + frontend locally, log in as a client with an APPROVED (or later state) order. Navigate to the order detail page. Click "Descargar recibo". Verify: (a) PDF opens inline in the browser, (b) filename is `recibo-{folio}.pdf`, (c) all fields render (business name, folio, fecha with time, estado label, cliente with phone, dirección if present, items table with correct snapshots, subtotal, total), (d) discount column shows em-dash for zero-discount items and `{pct}%` otherwise, (e) layout matches the Clásico mockup visually (serif font, beige items header, centered title).
  — Done when: PDF opens correctly with all fields readable and layout matches mockup.
  — Deps: 4.1, 4.2 (and Railway deploy for prod smoke — separate concern).
  — Not a commit — this is a pre-PR verification step. If it fails, fix in a follow-up task in the same PR before opening review.

- [ ] 5.2 Verify `openspec/config.yaml` still has `testing.frontend.runner: vitest` and `testing.frontend.framework: vitest` (applied 2026-08-17). No edit required — this check happens as part of PR review, not as a commit.
  — Done when: `grep "runner: vitest" openspec/config.yaml` exits 0.
  — Deps: none.

---

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Backend helper + template | ~126 lines (recibos.py ~45, template ~80, requirements +1) |
| Backend views + URLs | ~47 lines (pedidosViews +25, workerViews +18, urls +4) |
| Backend tests | ~55 lines |
| Frontend service + allowlist + tests | ~44 lines |
| Frontend UI buttons | ~30 lines |
| Config hygiene | ~0 lines (already applied) |
| **Total estimate** | **~160–200 lines** |
| 400-line budget risk | **Low** |
| Chained PRs recommended | **No** |
| Decision needed before apply | **No** |
