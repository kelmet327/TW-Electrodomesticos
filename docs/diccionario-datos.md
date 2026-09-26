# Diccionario de datos

Implementación de referencia del diccionario del documento **TW A6 POS**. `PK` significa clave primaria, `FK` clave foránea y `UQ` restricción de unicidad.

## `usuario`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_usuario` | `SERIAL` | No | PK, identificador interno. |
| `nombre` | `VARCHAR(60)` | No | Nombre de la persona. |
| `apellido` | `VARCHAR(60)` | No | Apellido de la persona. |
| `correo` | `VARCHAR(120)` | No | Credencial de acceso, `UNIQUE`; índice normalizado sin mayúsculas. |
| `contrasena` | `VARCHAR(255)` | No | Hash de Werkzeug; nunca se guarda la contraseña en texto plano. |
| `telefono` | `VARCHAR(20)` | Sí | Contacto. |
| `direccion` | `VARCHAR(200)` | Sí | Dirección principal. |
| `ciudad` | `VARCHAR(80)` | Sí | Ciudad de residencia. |
| `rol` | `VARCHAR(20)` | No | `CHECK IN ('vendedor', 'cliente')`. |
| `fecha_registro` | `TIMESTAMP` | No | `DEFAULT CURRENT_TIMESTAMP`. |
| `estado` | `BOOLEAN` | No | `DEFAULT TRUE`; una cuenta inactiva no inicia sesión. |

## `categoria`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_categoria` | `SERIAL` | No | PK. |
| `nombre` | `VARCHAR(80)` | No | `UNIQUE`, con índice normalizado. |
| `descripcion` | `VARCHAR(255)` | Sí | Descripción de la agrupación. |
| `estado` | `BOOLEAN` | No | `DEFAULT TRUE`. |

## `marca`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_marca` | `SERIAL` | No | PK. |
| `nombre` | `VARCHAR(80)` | No | `UNIQUE`, con índice normalizado. |
| `pais_origen` | `VARCHAR(80)` | Sí | País del fabricante. |
| `estado` | `BOOLEAN` | No | `DEFAULT TRUE`. |

## `producto`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_producto` | `SERIAL` | No | PK. |
| `nombre` | `VARCHAR(150)` | No | Nombre comercial. |
| `descripcion` | `TEXT` | Sí | Características técnicas. |
| `modelo` | `VARCHAR(80)` | Sí | Referencia del fabricante. |
| `precio` | `NUMERIC(10,2)` | No | `CHECK (precio >= 0)`. |
| `stock` | `INTEGER` | No | `CHECK (stock >= 0)`, `DEFAULT 0`. |
| `imagen_url` | `VARCHAR(255)` | Sí | URL http/https o ruta local `/static/`. |
| `id_categoria` | `INTEGER` | No | FK → `categoria(id_categoria)`. |
| `id_marca` | `INTEGER` | No | FK → `marca(id_marca)`. |
| `estado` | `BOOLEAN` | No | Publicación del producto. |
| `fecha_creacion` | `TIMESTAMP` | No | `DEFAULT CURRENT_TIMESTAMP`. |

## `venta`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_venta` | `SERIAL` | No | PK. |
| `id_vendedor` | `INTEGER` | No | FK → `usuario`; trigger valida rol `vendedor`. |
| `id_cliente` | `INTEGER` | Sí | FK → `usuario`; trigger valida rol `cliente`. |
| `fecha_venta` | `TIMESTAMP` | No | `DEFAULT CURRENT_TIMESTAMP`. |
| `subtotal` | `NUMERIC(10,2)` | No | Suma de detalles antes de impuesto. |
| `impuesto` | `NUMERIC(10,2)` | No | `DEFAULT 0`, `>= 0`. |
| `total` | `NUMERIC(10,2)` | No | `CHECK (total = subtotal + impuesto)`. |
| `direccion_entrega` | `VARCHAR(200)` | Sí | Nula para entrega en mostrador. |
| `estado` | `VARCHAR(20)` | No | `pendiente`, `completada` o `anulada`. |

## `detalle_venta`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_detalle_venta` | `SERIAL` | No | PK. |
| `id_venta` | `INTEGER` | No | FK → `venta`; relación 1:N. |
| `id_producto` | `INTEGER` | No | FK → `producto`; relación 1:N. |
| `cantidad` | `INTEGER` | No | `CHECK (cantidad > 0 AND cantidad <= 999)`. |
| `precio_unitario` | `NUMERIC(10,2)` | No | Precio histórico al momento de vender. |
| `subtotal` | `NUMERIC(10,2)` | No | `round(cantidad * precio_unitario, 2)`. |

La combinación `(id_venta, id_producto)` es `UNIQUE`. Las líneas no se actualizan ni se eliminan: se conservan como evidencia histórica.

## `pago`

| Campo | PostgreSQL | Nulo | Regla / descripción |
|---|---|---:|---|
| `id_pago` | `SERIAL` | No | PK. |
| `id_venta` | `INTEGER` | No | FK + `UNIQUE` → `venta`; relación 1:1. |
| `metodo` | `VARCHAR(20)` | No | `tarjeta_credito`, `tarjeta_debito`, `transferencia`, `efectivo` o `paypal`. |
| `monto` | `NUMERIC(10,2)` | No | `CHECK (monto > 0)` y trigger contra `venta.total`. |
| `estado` | `VARCHAR(20)` | No | `pendiente`, `aprobado`, `rechazado` o `reembolsado`. |
| `referencia` | `VARCHAR(100)` | Sí | Código de la transacción externa. |
| `fecha_pago` | `TIMESTAMP` | Sí | Momento del cobro. |
