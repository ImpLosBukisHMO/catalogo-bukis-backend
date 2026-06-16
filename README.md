# Catalogo Bukis - Backend

## API RESTful Django

### Tech Stack
- **Framework:** Django 6.x + Django REST Framework 3.16
- **Auth:** JWT (SimpleJWT 5.5)
- **Base de datos:** PostgreSQL 16
- **Imágenes:** Cloudinary / Railway Volume
- **Tests:** Django TestCase + pytest

---

## Estructura

```mermaid
graph TD
    A[api/] --> B[models.py]
    A --> C[views/]
    A --> D[serializers/]
    A --> E[tests/]
    A --> F[migrations/]
    A --> G[admin.py]
    A --> H[urls.py]

    C --> C1[productosViews.py]
    C --> C2[carritoViews.py]
    C --> C3[authViews.py]
    C --> C4[workerViews.py]

    D --> D1[serializers.py]
    D --> D2[worker.py]

    E --> E1[test_stock.py]
    E --> E2[test_pricing.py]
    E --> E3[test_availability.py]
    E --> E4[test_item_unique.py]

    style B fill:#e8f5e9
    style C fill:#e1f5fe
    style E fill:#fff3e0
```

---

## Modelos

### Diagrama ER

```mermaid
graph TD
    subgraph "Usuarios"
        U[Usuario] --> U_id[id]
        U --> U_n[nombre]
        U --> U_a[apellido]
        U --> U_c[correo]
        U --> U_t[telefono]
        U --> U_is[is_staff]
        U --> U_isu[is_superuser]
    end

    subgraph "Productos"
        P[Producto] --> P_id[id]
        P --> P_n[nombre]
        P --> P_d[descripcion]
        P --> P_p[precio]
        P --> P_d2[disponible]
        P --> P_a[activo]
        P --> P_cat[categoria_id]

        V[Variante] --> V_id[id]
        V --> V_p[producto_id]
        V --> V_c[color_id]
        V --> V_i[item]
        V --> V_s[stock]
        V --> V_pr[precio]
        V --> V_a[activo]

        C[Color] --> C_id[id]
        C --> C_n[nombre]
        C --> C_h[hex]
    end

    subgraph "Imágenes"
        I[Imagen] --> I_id[id]
        I --> I_p[producto_id]
        I --> I_v[variante_id]
        I --> I_u[url]
        I --> I_e[es_principal]
        I --> I_o[orden]
    end

    subgraph "Carrito"
        Car[Carrito] --> Car_id[id]
        Car --> Car_u[usuario_id]
        Car --> Car_a[activo]
        Car --> Car_f[fecha]

        CarI[CarritoItem] --> CarI_id[id]
        CarI --> CarI_c[carrito_id]
        CarI --> CarI_v[variante_id]
        CarI --> CarI_cant[cantidad]
    end

    subgraph "Pedidos"
        Ped[Pedido] --> Ped_id[id]
        Ped --> Ped_u[usuario_id]
        Ped --> Ped_e[estado]
        Ped --> Ped_f[fecha]
        Ped --> Ped_t[total]

        PedP[PedidoProducto] --> PedP_id[id]
        PedP --> PedP_ped[pedido_id]
        PedP --> PedP_v[variante_id]
        PedP --> PedP_c[cantidad]
        PedP --> PedP_pr[precio]
    end

    subgraph "Categorías"
        Cat[Categoria] --> Cat_id[id]
        Cat --> Cat_n[nombre]
        Cat --> Cat_a[activo]
    end

    P --> V
    P --> I
    V --> C
    Car --> U
    Car --> CarI
    CarI --> V
    Ped --> U
    Ped --> PedP
    PedP --> V
    P --> Cat

    style U fill:#e1f5fe
    style P fill:#e8f5e9
    style V fill:#e8f5e9
    style Car fill:#fff3e0
    style Ped fill:#fff3e0
    style Cat fill:#fce4ec
```

---

## Endpoints

### Autenticación
| Endpoint | Método | Body | Respuesta |
|----------|--------|------|-----------|
| `/api/auth/register/` | POST | `{nombre, apellido, correo, telefono, password}` | `201 Created` + tokens |
| `/api/auth/login/` | POST | `{correo, password}` | `200 OK` + tokens |
| `/api/auth/refresh/` | POST | `{refresh}` | `200 OK` + access token |

### Productos (Público)
| Endpoint | Método | Query Params | Respuesta |
|----------|--------|-------------|-----------|
| `/api/productos/` | GET | `?categoria=`, `?search=`, `?disponible=` | Lista de productos |
| `/api/productos/<id>/` | GET | - | Detalle del producto |
| `/api/categorias/` | GET | - | Lista de categorías |

### Carrito (Autenticado)
| Endpoint | Método | Body | Respuesta |
|----------|--------|------|-----------|
| `/api/carrito/` | GET | - | Carrito actual |
| `/api/carrito/` | POST | `{variante_id, cantidad}` | `201 Created` |
| `/api/carrito/<id>/` | DELETE | - | `204 No Content` |
| `/api/carrito/checkout/` | POST | `{carrito_id}` | `201 Created` + pedido |

### Pedidos (Autenticado)
| Endpoint | Método | Respuesta |
|----------|--------|-----------|
| `/api/pedidos/` | GET | Lista de pedidos del usuario |
| `/api/pedidos/<id>/` | GET | Detalle del pedido |

### Worker (Admin/Staff)
| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/api/worker/productos/` | GET/POST | CRUD productos |
| `/api/worker/productos/<id>/` | GET/PUT/PATCH/DELETE | Producto individual |
| `/api/worker/pedidos/` | GET | Listar todos los pedidos |
| `/api/worker/pedidos/<id>/` | GET/PUT/PATCH | Actualizar estado |
| `/api/worker/usuarios/` | GET | Listar usuarios |

---

## Estados de Pedido

```mermaid
graph TD
    A[Pendiente] --> B[En Proceso]
    B --> C[Enviado]
    C --> D[Entregado]
    C --> E[Cancelado]
    B --> E
    A --> E

    style A fill:#fff3e0
    style B fill:#e1f5fe
    style C fill:#e8f5e9
    style D fill:#e8f5e9
    style E fill:#ffebee
```

| Estado | Valor | Descripción |
|--------|-------|-------------|
| Pendiente | `pendiente` | Recién creado |
| En Proceso | `en_proceso` | Preparando |
| Enviado | `enviado` | En camino |
| Entregado | `entregado` | Entregado al cliente |
| Cancelado | `cancelado` | Cancelado |

---

## Tests

### Ejecutar tests

```bash
# Todos los tests
DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests

# Tests específicos
DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_stock
DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_pricing
DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_availability
DATABASE_URL='sqlite:///db.sqlite3' python manage.py test api.tests.test_item_unique

# Verificar migraciones
python manage.py makemigrations --check --dry-run
```

### Estructura de Tests

```mermaid
graph TD
    A[api/tests/] --> B[test_order_state.py]
    A --> C[test_stock.py]
    A --> D[test_pricing.py]
    A --> E[test_images.py]
    A --> F[test_availability.py]
    A --> G[test_item_unique.py]

    B --> B1[Estados de pedido]
    C --> C1[Concurrencia stock]
    D --> D1[Precio efectivo]
    E --> E1[Imágenes fallback]
    F --> F1[Disponibilidad]
    G --> G1[Unicidad SKU]

    style B fill:#fff3e0
    style C fill:#ffebee
    style D fill:#e8f5e9
    style E fill:#e1f5fe
    style F fill:#fff3e0
    style G fill:#e8f5e9
```

---

## Variables de Entorno

```env
# Base de datos
DATABASE_URL=postgresql://user:pass@localhost:5432/catalogo

# Django
SECRET_KEY=tu-secret-key-super-seguro
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Cloudinary (imágenes)
CLOUDINARY_URL=cloudinary://api_key:api_secret@cloud_name

# JWT
ACCESS_TOKEN_LIFETIME=5
REFRESH_TOKEN_LIFETIME=1440

# Railway
PORT=8000
```

---

## Comandos Útiles

```bash
# Crear superusuario
python manage.py createsuperuser

# Shell de Django
python manage.py shell

# Exportar datos
python manage.py dumpdata api > backup.json

# Importar datos
python manage.py loaddata backup.json

# Generar migraciones
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Checks de sistema
python manage.py check
python manage.py check --deploy
```

---

> **Nota:** Ver [WORKFLOW.md](../WORKFLOW.md) para el flujo de trabajo del equipo.
