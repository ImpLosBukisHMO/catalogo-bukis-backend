# Proposal: Order Receipt PDF (recibo-pdf-pedidos)

## Intent

No receipt-generation surface exists today; workers hand off orders without a standard document. Add a PDF receipt downloadable by the order owner and any worker.

## Scope

### In Scope
- `GET /api/mis-pedidos/<id>/recibo/` → PDF for order owner.
- `GET /api/worker/pedidos/<pedido_id>/recibo/` → PDF for `worker_role in ('total','parcial')`.
- Snapshot data: folio, line items, subtotal, total, date, shipping address (if present), business name "Importaciones Los Bukis".
- State gate: `APPROVED | READY | SHIPPED | COMPLETED`.
- Download button on `PedidoDetallePage` and `WorkerOrdersPage` detail panel.
- Fix stale `openspec/config.yaml`: frontend `runner: none` → `vitest`.

### Out of Scope
- Email auto-send, per-locale customization, reprint-from-list, logo/branding, fiscal invoice.
- Receipt for `CANCELED` orders.

## Capabilities

### New Capabilities
- `order-receipt-pdf`: PDF generation, state-gated download endpoints (client + worker), frontend UI.

### Modified Capabilities
- None. `order-state-machine` and `worker-panel-auth` consumed as read-only invariants.

## Approach

Render via `xhtml2pdf` from a Django template under `api/templates/recibo/`. Helper `build_recibo_pdf_response()` mirrors `build_comprobante_response()` but emits `BytesIO` → `HttpResponse` with `Content-Disposition: inline; filename="recibo-{folio}.pdf"`. Two thin views reuse existing permission patterns (client: `IsAuthenticated` + `is_staff` block; worker: `IsAuthenticated, IsWorker`). Frontend adds one service call per surface and extends `PROTECTED_COMPROBANTE_PATHS`.

## Affected Areas

| Area | Impact |
|------|--------|
| `api/utils/comprobantes.py` | Mod — `build_recibo_pdf_response`. |
| `api/views/pedidosViews.py` | Mod — `MiPedidoReciboPdfView`. |
| `api/views/workerViews.py` | Mod — `WorkerPedidoReciboPdfView`. |
| `api/urls.py` | Mod — 2 new routes. |
| `api/templates/recibo/recibo_pedido.html` | New — PDF template. |
| `requirements.txt` | Mod — add `xhtml2pdf`. |
| `api/tests/test_recibo_pdf.py` | New — perms, states, contract, null-address. |
| `frontend/src/services/pedidos.ts` | Mod — `downloadReciboPdf`. |
| `frontend/src/services/comprobante.ts` | Mod — extend allowlist. |
| `frontend/src/components/pages/PedidoDetallePage.tsx` | Mod — client button. |
| `frontend/src/components/pages/WorkerOrdersPage.tsx` | Mod — worker button. |
| `openspec/config.yaml` | Mod — `runner: vitest`. |

## Risks

| Risk | Likelihood | Mitigation |
|------|---|---|
| `xhtml2pdf` deps fail on Nixpacks. | Low | Pure-Python; verify on staging. |
| `direccion` NULL → template crash. | Med | Template guard + test both branches. |
| Frontend allowlist miss → fetch throws. | Med | Tracked task; test asserts download. |
| Cross-role access. | Low | Mirror comprobante pattern; test both. |

## Rollback Plan

`git revert` + redeploy. No migration, no persisted state. Comprobante flow untouched.

## Dependencies

- `xhtml2pdf` (+ `html5lib`, `reportlab`, `svglib`) in `requirements.txt`.
- Vitest 3.2.6 (installed).

## Success Criteria

- [ ] Owner downloads PDF for APPROVED/READY/SHIPPED/COMPLETED.
- [ ] Worker (`total`/`parcial`) downloads from `WorkerOrdersPage`.
- [ ] Filename `recibo-{folio}.pdf`, inline.
- [ ] CANCELED/PENDING/DENIED → 4xx.
- [ ] Cross-role → 403.
- [ ] Tests pass in CI.
- [ ] Staging renders valid PDF.
