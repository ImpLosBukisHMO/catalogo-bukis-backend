# Apply Progress: recibo-pdf-pedidos

## Mode

- Standard
- Delivery strategy: ask-on-risk
- Scope: backend only (Phases 1 and 2)

## Completed Tasks

- [x] 1.1 Add `xhtml2pdf==0.2.17` to `requirements.txt`.
- [x] 1.2 Create `catalogo_backend/api/utils/recibos.py` helper module.
- [x] 1.3 Create `catalogo_backend/api/templates/recibo/recibo_pedido.html`.
- [x] 2.1 Add `MiPedidoReciboPdfView`.
- [x] 2.2 Add `WorkerPedidoReciboPdfView`.
- [x] 2.3 Register receipt PDF routes.
- [x] 2.4 Add backend receipt PDF test suite.

## Work Unit Evidence

| Work Unit | Focused test command and exact result | Runtime harness command/scenario and exact result | Rollback boundary |
|---|---|---|---|
| Unit 1 — backend foundation | `DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_recibo_pdf` → `Ran 13 tests in 6.134s`, `OK` | Integration exercised through Django test client in `api.tests.test_recibo_pdf`; helper+template rendered to a real PDF (`%PDF`) during endpoint tests → pass | Revert `requirements.txt`, delete `catalogo_backend/api/utils/recibos.py`, delete `catalogo_backend/api/templates/recibo/recibo_pedido.html` |
| Unit 2 — backend views + URLs + tests | `DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_recibo_pdf` → `Ran 13 tests in 6.134s`, `OK` | `DATABASE_URL='sqlite:///db.sqlite3' python manage.py check` → `System check identified no issues (0 silenced)`; endpoint behavior exercised by APIClient matrix in `api.tests.test_recibo_pdf` → pass | Revert `catalogo_backend/api/views/pedidosViews.py`, `catalogo_backend/api/views/workerViews.py`, `catalogo_backend/api/urls.py`, `catalogo_backend/api/tests/test_recibo_pdf.py` |

## Files Changed

- `requirements.txt`
- `catalogo_backend/api/utils/recibos.py`
- `catalogo_backend/api/templates/recibo/recibo_pedido.html`
- `catalogo_backend/api/views/pedidosViews.py`
- `catalogo_backend/api/views/workerViews.py`
- `catalogo_backend/api/urls.py`
- `catalogo_backend/api/tests/test_recibo_pdf.py`
- `openspec/changes/recibo-pdf-pedidos/tasks.md`
- `openspec/changes/recibo-pdf-pedidos/apply-progress.md`

## Deviations

None — implementation matches the backend design and scope.

## Remaining Tasks

- [ ] 3.1 Add frontend receipt service exports.
- [ ] 3.2 Extend frontend protected-download allowlist.
- [ ] 3.3 Add frontend service tests.
- [ ] 4.1 Add client UI button.
- [ ] 4.2 Add worker UI button.
- [ ] 5.1 Manual end-to-end smoke test.
- [ ] 5.2 Frontend config hygiene review check.
