# Arquitectura del Sistema

## Visión General

Catalogo Bukis es una aplicación e-commerce de catálogo de productos con las siguientes características:

```mermaid
graph TB
    subgraph "Cliente"
        A[React SPA]
        A --> B[Browser]
    end

    subgraph "Railway"
        C[Railway Proxy]
        C --> D[Frontend Service]
        C --> E[Backend Service]
        C --> F[PostgreSQL]
        C --> G[Railway Volume]
    end

    B --> C
    D --> B
    E --> F
    E --> G

    style A fill:#e1f5fe
    style E fill:#e8f5e9
    style F fill:#fff3e0
    style G fill:#fce4ec
```

---

## Componentes Principales

### Frontend

| Componente | Tecnología | Rol |
|------------|-----------|-----|
| **React SPA** | React 19 + Vite | Interfaz de usuario |
| **Tailwind CSS** | CSS Framework | Estilos utilitarios |
| **Bulma** | CSS Framework | Componentes base |
| **TanStack Query** | Data Fetching | Cache y sincronización |
| **Axios** | HTTP Client | Comunicación con API |

### Backend

| Componente | Tecnología | Rol |
|------------|-----------|-----|
| **Django** | Python Framework | Framework web |
| **DRF** | REST Framework | API RESTful |
| **SimpleJWT** | Auth Library | Autenticación JWT |
| **PostgreSQL** | Database | Persistencia de datos |
| **Railway Volume** | File Storage | Almacenamiento de imágenes locales |

---

## Flujo de Request

```mermaid
sequenceDiagram
    participant User as Usuario
    participant Browser as Browser
    participant Railway as Railway Proxy
    participant Frontend as React App
    participant Backend as Django API
    participant DB as PostgreSQL
    participant Storage as Railway Volume

    User->>Browser: Navega a la app
    Browser->>Railway: GET /
    Railway->>Frontend: Request SPA
    Frontend->>Browser: HTML + JS + CSS
    Browser->>User: Renderiza app

    User->>Frontend: Click "Ver Productos"
    Frontend->>Railway: GET /api/productos/
    Railway->>Backend: Proxy request
    Backend->>DB: SELECT productos
    DB->>Backend: Resultados
    Backend->>Railway: JSON + image URLs
    Railway->>Frontend: Datos
    Frontend->>User: Muestra productos
```

---

## Base de Datos

### Diagrama Entidad-Relación

```mermaid
erDiagram
    USUARIO ||--o{ PEDIDO : "tiene"
    USUARIO ||--o{ CARRITO : "tiene"
    CATEGORIA ||--o{ PRODUCTO : "contiene"
    PRODUCTO ||--o{ VARIANTE : "tiene"
    PRODUCTO ||--o{ IMAGEN : "tiene"
    COLOR ||--o{ VARIANTE : "tiene"
    VARIANTE ||--o{ CARRITO_ITEM : "en"
    VARIANTE ||--o{ PEDIDO_PRODUCTO : "en"
    CARRITO ||--o{ CARRITO_ITEM : "contiene"
    PEDIDO ||--o{ PEDIDO_PRODUCTO : "contiene"

    USUARIO {
        int id PK
        string nombre
        string apellido
        string correo
        string telefono
        string password
        boolean is_staff
        boolean is_superuser
    }

    CATEGORIA {
        int id PK
        string nombre
        boolean activo
    }

    PRODUCTO {
        int id PK
        string nombre
        string descripcion
        decimal precio
        boolean disponible
        boolean activo
        int categoria_id FK
    }

    VARIANTE {
        int id PK
        int producto_id FK
        int color_id FK
        string item
        int stock
        decimal precio
        boolean activo
    }

    COLOR {
        int id PK
        string nombre
        string hex
    }

    IMAGEN {
        int id PK
        int producto_id FK
        int variante_id FK
        string url
        boolean es_principal
        int orden
    }

    CARRITO {
        int id PK
        int usuario_id FK
        boolean activo
        datetime fecha
    }

    CARRITO_ITEM {
        int id PK
        int carrito_id FK
        int variante_id FK
        int cantidad
    }

    PEDIDO {
        int id PK
        int usuario_id FK
        string estado
        datetime fecha
        decimal total
    }

    PEDIDO_PRODUCTO {
        int id PK
        int pedido_id FK
        int variante_id FK
        int cantidad
        decimal precio
    }
```

---

## Autenticación

### JWT Flow

```mermaid
sequenceDiagram
    participant Client as React
    participant API as Django API
    participant DB as PostgreSQL

    Client->>API: POST /auth/login/ {correo, password}
    API->>DB: Validar credenciales
    DB->>API: OK
    API->>API: Generar JWT (access + refresh)
    API->>Client: {access_token, refresh_token}

    Note over Client: Almacenar tokens

    Client->>Client: Request protegido
    Client->>API: GET /carrito/ (Authorization: Bearer <access>)
    API->>API: Validar JWT
    API->>DB: SELECT carrito
    DB->>API: Datos
    API->>Client: 200 OK

    Note over Client: Access expiró

    Client->>API: POST /auth/refresh/ {refresh_token}
    API->>API: Validar refresh
    API->>Client: {access_token}
```

---

## Carrito de Compras

```mermaid
sequenceDiagram
    participant User as Usuario
    participant Client as React
    participant API as Django API
    participant DB as PostgreSQL

    User->>Client: Agregar producto al carrito
    Client->>API: POST /carrito/ {variante_id, cantidad}
    API->>DB: SELECT variante (stock)
    DB->>API: Stock disponible
    API->>DB: INSERT carrito_item
    DB->>API: OK
    API->>Client: 201 Created
    Client->>User: Actualizar UI

    User->>Client: Ir a checkout
    Client->>API: POST /carrito/checkout/
    API->>DB: SELECT items del carrito
    API->>DB: SELECT variantes (stock)
    DB->>API: Stock OK
    API->>DB: INSERT pedido
    API->>DB: INSERT pedido_productos
    API->>DB: UPDATE stock
    API->>DB: UPDATE carrito (desactivar)
    API->>Client: 201 Created
    Client->>User: Confirmación
```

---

## Estados del Pedido

```mermaid
stateDiagram-v2
    [*] --> Pendiente
    Pendiente --> EnProceso
    Pendiente --> Cancelado
    EnProceso --> Enviado
    EnProceso --> Cancelado
    Enviado --> Entregado
    Enviado --> Cancelado
    Entregado --> [*]
    Cancelado --> [*]

    note right of Pendiente
        Pedido recién creado
    end note

    note right of EnProceso
        Preparando orden
    end note

    note right of Enviado
        En camino
    end note
```

---

## Escalabilidad

### Horizontal

```mermaid
graph TB
    subgraph "Load Balancer"
        LB[Railway Proxy]
    end

    subgraph "Backend Instances"
        B1[Django 1]
        B2[Django 2]
        B3[Django 3]
    end

    subgraph "Database"
        DB[(PostgreSQL)]
    end

    subgraph "Cache"
        Redis[(Redis)]
    end

    subgraph "Storage"
        S3[Cloud Storage]
    end

    LB --> B1
    LB --> B2
    LB --> B3
    B1 --> DB
    B2 --> DB
    B3 --> DB
    B1 --> Redis
    B2 --> Redis
    B3 --> Redis
    B1 --> S3
    B2 --> S3
    B3 --> S3

    style LB fill:#e1f5fe
    style B1 fill:#e8f5e9
    style DB fill:#fff3e0
    style Redis fill:#fff3e0
    style S3 fill:#fce4ec
```

**Consideraciones:**
- Railway maneja automáticamente el scaling horizontal
- PostgreSQL puede manejar miles de conexiones
- Railway Volume para almacenamiento de imágenes locales
- Redis para cache de sesiones (opcional)

---

## Seguridad

### Capas de Seguridad

```mermaid
graph TD
    A[Seguridad] --> B[Transporte]
    A --> C[Autenticación]
    A --> D[Autorización]
    A --> E[Validación]
    A --> F[Datos]

    B --> B1[HTTPS/TLS]
    B --> B2[CORS]

    C --> C1[JWT]
    C --> C2[Password Hashing]

    D --> D1[IsAuthenticated]
    D --> D2[IsAdminUser]

    E --> E1[Input Validation]
    E --> E2[SQL Injection Prevention]
    E --> E3[XSS Protection]

    F --> F1[Environment Variables]
    F --> F2[Secrets Management]

    style B fill:#e1f5fe
    style C fill:#e8f5e9
    style D fill:#fff3e0
    style E fill:#ffebee
    style F fill:#fce4ec
```

---

## Performance

### Optimizaciones

| Área | Optimización | Impacto |
|------|-------------|---------|
| **Imágenes** | Railway Volume | Almacenamiento local persistente |
| **DB** | Índices + `select_related` | Menos queries N+1 |
| **Frontend** | Code splitting + lazy loading | Bundle más pequeño |
| **API** | Paginación | Respuestas más rápidas |
| **Cache** | TanStack Query | Menos requests al backend |
| **Assets** | Railway CDN | Static files rápidos |

---

## Monitoreo

### Métricas a monitorear

| Métrica | Herramienta | Umbral |
|---------|------------|--------|
| **Response time** | Railway Logs | < 500ms |
| **Error rate** | Railway Logs | < 1% |
| **DB connections** | PostgreSQL | < 80% |
| **Memory usage** | Railway | < 80% |
| **CPU usage** | Railway | < 80% |
| **Uptime** | Railway | > 99% |

---

## Backup y Recuperación

### Estrategia

| Componente | Backup | Frecuencia |
|------------|--------|------------|
| **Base de datos** | Railway automatic backups | Diario |
| **Imágenes** | Railway Volume | Con backup de Railway |
| **Código** | GitHub | Cada commit |

### Recuperación

```mermaid
graph TD
    A[Disaster Recovery] --> B[DB Corrupta]
    A --> C[Deploy Fallido]
    A --> D[Data Loss]

    B --> B1[Restaurar desde Railway Backup]
    B --> B2[Verificar integridad]

    C --> C1[Revertir a último commit estable]
    C --> C2[Deploy anterior]

    D --> D1[Restaurar desde backup más reciente]
    D --> D2[Re-run migrations]

    style B fill:#ffebee
    style C fill:#ffebee
    style D fill:#ffebee
```

---

> **Nota:** Esta documentación se actualiza con cada cambio significativo de arquitectura.
