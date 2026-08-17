# Design: Order Receipt PDF (recibo-pdf-pedidos)

## Technical Approach

Two thin DRF views (client + worker) reuse existing permission and state patterns, delegate to a pure helper that renders a Django template and returns PDF bytes via `xhtml2pdf.pisa`, and wrap those bytes in an `HttpResponse` with an inline `Content-Disposition`. Frontend adds two service functions and extends the existing protected-download allowlist. No model, no migration, no settings change.

## Architecture Decisions

| # | Decision | Choice | Rejected | Rationale |
|---|---------|--------|----------|-----------|
| 1 | PDF generation location | Helper in `api/utils/recibos.py` split into `render_recibo_html(pedido)` + `render_recibo_pdf_bytes(html)` | Inline in view | Pure functions are unit-testable without HTTP fixtures; view stays a permission/state gate. |
| 2 | Response wrapper | `build_recibo_pdf_response(pdf_bytes, folio)` in same helper module | Ad-hoc `HttpResponse` per view | Mirrors `build_comprobante_response` naming; single source of truth for filename + headers. |
| 3 | Content-Disposition | `inline; filename="recibo-{folio}.pdf"` | `attachment` | Matches existing comprobante convention; browser previews PDFs, user still downloads via Cmd+S. Proposal §Approach confirms `inline`. |
| 4 | Template discovery | `api/templates/recibo/recibo_pedido.html` via `APP_DIRS: True` | Project-level `templates/` + settings change | Zero settings edit; matches Django app-conventional layout. |
| 5 | State-allowed list | Module-level constant `RECIBO_ALLOWED_STATES` in `api/utils/recibos.py`, imported by both views | Duplicate list per view | Single source; drift-proof. Frontend duplicates a small const (see Decision 8). |
| 6 | Permissions | Client: `[IsAuthenticated]` + `queryset.filter(cliente=request.user)` + explicit `is_staff` 403. Worker: `[IsAuthenticated, IsWorker]`. | New permission class | `IsWorker` already checks `worker_role in ('total','parcial')`; mirrors `MiPedidoComprobanteUpdateView` / `WorkerPedidoComprobanteDownloadView` exactly. |
| 7 | `xhtml2pdf` version pin | `xhtml2pdf==0.2.17` | Unpinned / range | Latest stable on PyPI as of 2025; all deps pure-Python (`reportlab`, `html5lib`, `svglib`, `pypdf`). Recommend verifying PyPI at implementation time — do not install here. |
| 8 | Frontend state gating | Duplicate small const `RECIBO_ALLOWED_STATES` in `services/pedidos.ts` | Fetch from backend | Loose coupling; list is 4 items and stable. Backend remains authoritative (returns 4xx on mismatch). |

## Data Flow

```
Client ──GET /api/mis-pedidos/{id}/recibo/──▶ MiPedidoReciboPdfView
                                                    │ perm + owner + state gate
                                                    ▼
Worker ──GET /api/worker/pedidos/{id}/recibo/─▶ WorkerPedidoReciboPdfView
                                                    │ IsWorker + state gate
                                                    ▼
                                              render_recibo_html(pedido)
                                                    │ Django template + context
                                                    ▼
                                              render_recibo_pdf_bytes(html)
                                                    │ pisa.CreatePDF → BytesIO
                                                    ▼
                                              build_recibo_pdf_response(bytes, folio)
                                                    │ HttpResponse + headers
                                                    ▼
                                              Browser (inline PDF, filename=recibo-{folio}.pdf)
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `catalogo_backend/api/utils/recibos.py` | Create | `RECIBO_ALLOWED_STATES`, `render_recibo_html`, `render_recibo_pdf_bytes`, `build_recibo_pdf_response`. |
| `catalogo_backend/api/templates/recibo/recibo_pedido.html` | Create | HTML template (inline `<style>`, table layout). |
| `catalogo_backend/api/views/pedidosViews.py` | Modify | Add `MiPedidoReciboPdfView` (mirrors `MiPedidoComprobanteUpdateView` shape, GET-only). |
| `catalogo_backend/api/views/workerViews.py` | Modify | Add `WorkerPedidoReciboPdfView` (mirrors `WorkerPedidoComprobanteDownloadView`). |
| `catalogo_backend/api/urls.py` | Modify | Two routes with names `mi-pedido-recibo`, `worker-pedido-recibo`. |
| `catalogo_backend/requirements.txt` | Modify | Add `xhtml2pdf==0.2.17`. |
| `catalogo_backend/api/tests/test_recibo_pdf.py` | Create | See Testing Strategy. |
| `catalogo-frontend/src/services/pedidos.ts` | Modify | Add `downloadReciboPdf(pedidoId)` + `downloadReciboPdfWorker(pedidoId)`; export `RECIBO_ALLOWED_STATES`. |
| `catalogo-frontend/src/services/comprobante.ts` | Modify | Extend `PROTECTED_COMPROBANTE_PATHS` allowlist. |
| `catalogo-frontend/src/components/pages/PedidoDetallePage.tsx` | Modify | Download button in existing actions row. |
| `catalogo-frontend/src/components/pages/WorkerOrdersPage.tsx` | Modify | Download button in right-panel detail section. |
| `openspec/config.yaml` | Modify | `runner: none` → `runner: vitest`. |

## Interfaces / Contracts

**Backend helper (`api/utils/recibos.py`):**
```python
RECIBO_ALLOWED_STATES = frozenset({"APPROVED", "READY", "SHIPPED", "COMPLETED"})

def render_recibo_html(pedido: PedidosModel) -> str: ...
def render_recibo_pdf_bytes(html: str) -> bytes: ...  # raises RuntimeError on pisa error
def build_recibo_pdf_response(pdf_bytes: bytes, folio: str) -> HttpResponse: ...
```

**Template context** (passed by `render_recibo_html`):
- `pedido` (model), `folio` (str), `items` (queryset of `PedidoProductosModel`), `subtotal`, `total`, `fecha` (formatted `created_at` as `15 de agosto, 2026 — 14:32` — long Spanish format with time), `estado_label` (human-readable state, e.g. "Completado" from `get_estado_display()`), `cliente` (name, email, `telefono`), `direccion` (may be `None`), `business_name = "Importaciones Los Bukis"`.
- Excluded from context: `nota_cliente`, `nota_worker`, comprobante-related fields.

**Frontend service (`services/pedidos.ts`):**
```ts
export const RECIBO_ALLOWED_STATES = ["APPROVED", "READY", "SHIPPED", "COMPLETED"] as const;
export function downloadReciboPdf(pedidoId: number): Promise<void>;
export function downloadReciboPdfWorker(pedidoId: number): Promise<void>;
```
Both delegate to `openProtectedComprobante` from `services/comprobante.ts`.

**Allowlist delta (`services/comprobante.ts`):**
```ts
const PROTECTED_COMPROBANTE_PATHS = [
  /^\/api\/mis-pedidos\/\d+\/comprobante\/?$/,
  /^\/api\/worker\/pedidos\/\d+\/comprobante\/?$/,
  /^\/api\/mis-pedidos\/\d+\/recibo\/?$/,          // NEW
  /^\/api\/worker\/pedidos\/\d+\/recibo\/?$/,      // NEW
];
```

**Config delta (`openspec/config.yaml`):**
```yaml
testing:
  frontend:
    runner: vitest        # was: none
    framework: vitest     # was: none
```

## Template Design

Based on the "Clásico" mockup selected by the user (`/tmp/recibos-mockups/1-clasico.html`):

- **Layout**: `<table>`-based (no flex/grid — xhtml2pdf lacks support). Serif typography (Georgia / Times New Roman), centered header with business name + "Recibo de pedido" subtitle, thick horizontal rule under header, two-column meta row (Folio + Fecha on top, Estado on bottom), section-titled blocks for Cliente / Dirección de envío / Artículos, striped items table with tan/beige header row (`#f4f1ec`), right-aligned totals with thick rule above Total row, italic footer.
- **CSS**: inline `<style>` only. Safe subset: `font-family`, `font-size`, `margin/padding`, `border`, `text-align`, `background-color`, `width`, `letter-spacing`, `text-transform`. No external assets (no logo — Q4 explicitly deferred).
- **Money format**: `{{ value|floatformat:2 }}` — Django built-in, no new filter, matches numeric snapshot fields (`precio_unitario_snapshot`, `subtotal_snapshot`, `precio_total`).
- **Date format**: `{{ fecha }}` pre-formatted by view as `15 de agosto, 2026 — 14:32` using Django's `date` filter with locale `es` (`{{ pedido.created_at|date:"j \d\e F, Y — H:i" }}`).
- **State label**: `{{ estado_label }}` from `pedido.get_estado_display()` — never raw enum value.
- **Line items**: read `producto_nombre_snapshot`, `color_nombre_snapshot`, `cantidad`, `precio_unitario_snapshot`, `descuento_porcentaje_snapshot`, `subtotal_linea_snapshot` only. Ignore nullable legacy FK fields.
- **Discount column**: show `"—"` (em-dash) when `descuento_porcentaje_snapshot == 0`, otherwise `"{{ pct }}%"`.
- **Client block**: name (bold) + email + phone.
- **Reference mockup**: `/tmp/recibos-mockups/1-clasico.html` — copy structure and CSS as starting point; adapt to xhtml2pdf CSS constraints.

## Frontend Button Placement

- **Client (`PedidoDetallePage.tsx`)**: place in the existing actions row alongside the comprobante upload trigger. Rationale: users already look there for order-document actions; keeps the receipt discoverable next to related affordances.
- **Worker (`WorkerOrdersPage.tsx`)**: inside the right-panel detail block, adjacent to existing per-order actions (state transitions, comprobante download). Rationale: worker workflow is inline; matches existing action locality.
- **State-conditional rendering**: button hidden unless `pedido.estado ∈ RECIBO_ALLOWED_STATES` (frontend const, Decision 8).
- **UX**: spinner replaces button label while blob fetch is in flight; on error, existing toast surface (used by comprobante download) shows a short message. No new UI primitives.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Backend unit | `RECIBO_ALLOWED_STATES` membership; `render_recibo_html` renders both address branches; `build_recibo_pdf_response` sets correct headers | Direct function calls; assert bytes start with `%PDF-` for smoke, headers exact-match. |
| Backend integration | Permission matrix (owner-200, other-client-404, worker-on-client-endpoint-403, unauth-401); state gate matrix (each of 7 states → 200 or 4xx); worker endpoint (worker-200, client-on-worker-endpoint-403) | `test_recibo_pdf.py` mirroring `test_comprobante.py` base class + fixtures. |
| Frontend unit | `downloadReciboPdf` and `downloadReciboPdfWorker` call `openProtectedComprobante` with correct URL; allowlist accepts new paths and still rejects tampered variants (`/recibo-x/`, query params) | Vitest + mocked `API.get`. |
| Frontend (optional) | Button hidden for PENDING/DENIED/CANCELED, visible for APPROVED+ | React Testing Library on `PedidoDetallePage` — optional if button state logic is trivial. |

**What NOT to test**: xhtml2pdf PDF byte correctness (trust the lib), Django template engine internals, PDF visual layout (manual staging smoke covers this).

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary. Only data-shaped I/O (DB read → template render → HTTP response).

## Migration / Rollout

- No DB migration (no model changes).
- Railway Nixpacks: `pip install -r requirements.txt` on next deploy pulls `xhtml2pdf` + transitive deps. All pure-Python; no system packages needed. Endpoint returns 500 until deploy completes — acceptable because no existing endpoint depends on it (net-new surface).
- Rollback: `git revert` the commit + redeploy. No data cleanup; no persisted state.

## Open Questions

None blocking. Q1 (CANCELED), Q2 (Content-Disposition), Q3 (filename), Q4 (logo) were all locked during proposal/exploration. Q5 (config.yaml) is fixed in this change (Decision + File Changes).
