# API Documentation

## Base URL

```
Staging: https://optimistic-youth-staging.up.railway.app/api/
Production: https://optimistic-youth.up.railway.app/api/
Local: http://localhost:8000/api/
```

---

## Autenticación

Todas las rutas protegidas requieren header:
```
Authorization: Bearer <access_token>
```

### Tokens
- **Access Token:** Válido por 5 minutos (configurable)
- **Refresh Token:** Válido por 24 horas (configurable)

---

## Endpoints

### Auth

#### POST /auth/register/
Registro de nuevo usuario.

**Request:**
```json
{
  "nombre": "Juan",
  "apellido": "Pérez",
  "correo": "juan@example.com",
  "telefono": "+1234567890",
  "password": "password123"
}
```

**Response (201):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "nombre": "Juan",
    "apellido": "Pérez",
    "correo": "juan@example.com"
  }
}
```

**Errores:**
- `400`: Datos inválidos
- `409`: Correo ya existe

---

#### POST /auth/login/
Login con credenciales.

**Request:**
```json
{
  "correo": "juan@example.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs...",
  "refresh": "eyJhbGciOiJIUzI1NiIs...",
  "user": {
    "id": 1,
    "nombre": "Juan",
    "apellido": "Pérez",
    "correo": "juan@example.com"
  }
}
```

**Errores:**
- `401`: Credenciales inválidas

---

#### POST /auth/refresh/
Obtener nuevo access token.

**Request:**
```json
{
  "refresh": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Response (200):**
```json
{
  "access": "eyJhbGciOiJIUzI1NiIs..."
}
```

**Errores:**
- `401`: Refresh token inválido o expirado

---

### Productos

#### GET /productos/
Listar productos.

**Query Parameters:**
| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `categoria` | int | Filtrar por categoría |
| `search` | string | Búsqueda por nombre |
| `disponible` | bool | Solo disponibles |
| `page` | int | Número de página |
| `page_size` | int | Tamaño de página |

**Response (200):**
```json
{
  "count": 100,
  "next": "https://api.example.com/api/productos/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "nombre": "Camiseta Azul",
      "descripcion": "Camiseta de algodón",
      "precio": "29.99",
      "disponible": true,
      "imagen": "/media/img/products/abc123.jpg",
      "categoria": {
        "id": 1,
        "nombre": "Ropa"
      }
    }
  ]
}
```

---

#### GET /productos/<id>/
Detalle de producto.

**Response (200):**
```json
{
  "id": 1,
  "nombre": "Camiseta Azul",
  "descripcion": "Camiseta de algodón",
  "precio": "29.99",
  "disponible": true,
  "imagen": "/media/img/products/abc123.jpg",
  "categoria": {
    "id": 1,
    "nombre": "Ropa"
  },
  "variantes": [
    {
      "id": 1,
      "color": {
        "id": 1,
        "nombre": "Azul",
        "hex": "#0000FF"
      },
      "item": "CAM-AZUL-001",
      "stock": 10,
      "precio": "29.99"
    }
  ],
  "imagenes": [
    {
      "id": 1,
      "url": "/media/img/products/abc123.jpg",
      "es_principal": true,
      "orden": 1
    }
  ]
}
```

**Errores:**
- `404`: Producto no encontrado

---

### Categorías

#### GET /categorias/
Listar categorías.

**Response (200):**
```json
[
  {
    "id": 1,
    "nombre": "Ropa",
    "activo": true
  }
]
```

---

### Carrito

#### GET /carrito/
Obtener carrito actual.

**Auth:** Requerido

**Response (200):**
```json
{
  "id": 1,
  "items": [
    {
      "id": 1,
      "variante": {
        "id": 1,
        "producto": {
          "id": 1,
          "nombre": "Camiseta Azul"
        },
        "color": {
          "id": 1,
          "nombre": "Azul"
        }
      },
      "cantidad": 2,
      "subtotal": "59.98"
    }
  ],
  "total": "59.98",
  "cantidad_items": 2
}
```

---

#### POST /carrito/
Agregar item al carrito.

**Auth:** Requerido

**Request:**
```json
{
  "variante_id": 1,
  "cantidad": 2
}
```

**Response (201):**
```json
{
  "id": 1,
  "variante": {
    "id": 1,
    "producto": {
      "id": 1,
      "nombre": "Camiseta Azul"
    }
  },
  "cantidad": 2,
  "subtotal": "59.98"
}
```

**Errores:**
- `400`: Stock insuficiente
- `404`: Variante no encontrada

---

#### DELETE /carrito/<id>/
Eliminar item del carrito.

**Auth:** Requerido

**Response (204):**
```
No Content
```

---

### Checkout

#### POST /carrito/checkout/
Procesar checkout.

**Auth:** Requerido

**Request:**
```json
{
  "carrito_id": 1,
  "direccion": {
    "calle": "Calle 123",
    "ciudad": "Ciudad",
    "estado": "Estado",
    "codigo_postal": "12345",
    "pais": "País"
  }
}
```

**Response (201):**
```json
{
  "pedido_id": 1,
  "total": "59.98",
  "estado": "pendiente",
  "fecha": "2026-01-15T10:30:00Z",
  "items": [
    {
      "id": 1,
      "variante": {
        "id": 1,
        "producto": {
          "nombre": "Camiseta Azul"
        }
      },
      "cantidad": 2,
      "precio": "29.99"
    }
  ]
}
```

**Errores:**
- `400`: Stock insuficiente
- `400`: Carrito vacío
- `400`: Carrito ya procesado

---

### Pedidos

#### GET /pedidos/
Listar pedidos del usuario.

**Auth:** Requerido

**Response (200):**
```json
[
  {
    "id": 1,
    "estado": "pendiente",
    "total": "59.98",
    "fecha": "2026-01-15T10:30:00Z",
    "cantidad_items": 2
  }
]
```

---

#### GET /pedidos/<id>/
Detalle de pedido.

**Auth:** Requerido

**Response (200):**
```json
{
  "id": 1,
  "estado": "pendiente",
  "total": "59.98",
  "fecha": "2026-01-15T10:30:00Z",
  "direccion": {
    "calle": "Calle 123",
    "ciudad": "Ciudad",
    "estado": "Estado",
    "codigo_postal": "12345",
    "pais": "País"
  },
  "items": [
    {
      "id": 1,
      "variante": {
        "id": 1,
        "producto": {
          "id": 1,
          "nombre": "Camiseta Azul"
        },
        "color": {
          "id": 1,
          "nombre": "Azul"
        }
      },
      "cantidad": 2,
      "precio": "29.99"
    }
  ]
}
```

---

### Worker (Admin)

#### GET /worker/productos/
Listar productos (admin).

**Auth:** Requerido (staff)

**Response (200):**
```json
{
  "count": 100,
  "results": [
    {
      "id": 1,
      "nombre": "Camiseta Azul",
      "precio": "29.99",
      "stock_total": 50,
      "disponible": true,
      "activo": true
    }
  ]
}
```

---

#### POST /worker/productos/
Crear producto.

**Auth:** Requerido (staff)

**Request:**
```json
{
  "nombre": "Camiseta Azul",
  "descripcion": "Camiseta de algodón",
  "precio": "29.99",
  "categoria_id": 1,
  "disponible": true,
  "activo": true
}
```

**Response (201):**
```json
{
  "id": 1,
  "nombre": "Camiseta Azul",
  "descripcion": "Camiseta de algodón",
  "precio": "29.99",
  "disponible": true,
  "activo": true
}
```

---

#### PUT/PATCH /worker/productos/<id>/
Actualizar producto.

**Auth:** Requerido (staff)

---

#### DELETE /worker/productos/<id>/
Eliminar producto.

**Auth:** Requerido (staff)

**Response (204):**
```
No Content
```

---

#### GET /worker/pedidos/
Listar todos los pedidos.

**Auth:** Requerido (staff)

**Response (200):**
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "usuario": {
        "id": 1,
        "nombre": "Juan",
        "correo": "juan@example.com"
      },
      "estado": "pendiente",
      "total": "59.98",
      "fecha": "2026-01-15T10:30:00Z"
    }
  ]
}
```

---

#### PATCH /worker/pedidos/<id>/
Actualizar estado del pedido.

**Auth:** Requerido (staff)

**Request:**
```json
{
  "estado": "en_proceso"
}
```

**Response (200):**
```json
{
  "id": 1,
  "estado": "en_proceso",
  "total": "59.98",
  "fecha": "2026-01-15T10:30:00Z"
}
```

---

## Códigos de Estado

| Código | Significado | Cuándo ocurre |
|--------|-------------|---------------|
| `200` | OK | Request exitoso |
| `201` | Created | Recurso creado |
| `204` | No Content | Eliminación exitosa |
| `400` | Bad Request | Datos inválidos |
| `401` | Unauthorized | Sin autenticación |
| `403` | Forbidden | Sin permisos |
| `404` | Not Found | Recurso no existe |
| `409` | Conflict | Conflicto de datos |
| `500` | Server Error | Error interno |

---

## Paginación

Todos los endpoints de listado usan paginación:

```json
{
  "count": 100,
  "next": "https://api.example.com/api/productos/?page=2",
  "previous": null,
  "results": [...]
}
```

**Parámetros:**
- `page`: Número de página (default: 1)
- `page_size`: Items por página (default: 20, max: 100)

---

## Ejemplos de Uso

### cURL

```bash
# Login
curl -X POST https://api.example.com/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"correo": "juan@example.com", "password": "password123"}'

# Listar productos
curl https://api.example.com/api/productos/

# Carrito (con token)
curl https://api.example.com/api/carrito/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."

# Checkout
curl -X POST https://api.example.com/api/carrito/checkout/ \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"carrito_id": 1}'
```

### JavaScript (Axios)

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://api.example.com/api/',
  headers: {
    'Authorization': `Bearer ${token}`
  }
});

// Login
const login = async (correo, password) => {
  const response = await api.post('/auth/login/', { correo, password });
  return response.data;
};

// Productos
const getProducts = async () => {
  const response = await api.get('/productos/');
  return response.data;
};

// Checkout
const checkout = async (carritoId) => {
  const response = await api.post('/carrito/checkout/', {
    carrito_id: carritoId
  });
  return response.data;
};
```

---

> **Nota:** Para más información, ver la documentación del backend en `catalogo-bukis-backend/README.md`.
