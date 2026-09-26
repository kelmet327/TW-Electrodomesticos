# Modelo de datos y reglas implementadas

Este documento resume cómo el código relaciona la base de datos con el diseño de **TW A6 POS**.

```mermaid
erDiagram
    USUARIO ||--o{ VENTA : "registra / compra"
    USUARIO ||--o{ VENTA : "cliente"
    CATEGORIA ||--o{ PRODUCTO : clasifica
    MARCA ||--o{ PRODUCTO : produce
    VENTA ||--|{ DETALLE_VENTA : compone
    PRODUCTO ||--o{ DETALLE_VENTA : vende
    VENTA ||--o| PAGO : "se abona con"

    USUARIO {
        serial id_usuario PK
        varchar nombre
        varchar apellido
        varchar correo UK
        varchar contrasena
        varchar rol
        boolean estado
    }
    CATEGORIA {
        serial id_categoria PK
        varchar nombre UK
        varchar descripcion
        boolean estado
    }
    MARCA {
        serial id_marca PK
        varchar nombre UK
        varchar pais_origen
        boolean estado
    }
    PRODUCTO {
        serial id_producto PK
        varchar nombre
        numeric precio
        integer stock
        integer id_categoria FK
        integer id_marca FK
    }
    VENTA {
        serial id_venta PK
        integer id_vendedor FK
        integer id_cliente FK
        numeric subtotal
        numeric impuesto
        numeric total
        varchar estado
    }
    DETALLE_VENTA {
        serial id_detalle_venta PK
        integer id_venta FK
        integer id_producto FK
        integer cantidad
        numeric precio_unitario
        numeric subtotal
    }
    PAGO {
        serial id_pago PK
        integer id_venta FK_UK
        varchar metodo
        numeric monto
        varchar estado
    }
```

## Integridad

- `producto.stock >= 0` y los locks de fila impiden sobreventa concurrente.
- `venta.total = venta.subtotal + venta.impuesto`.
- `detalle_venta.subtotal = round(cantidad * precio_unitario, 2)`.
- Un trigger bloquea cambios en líneas de venta para conservar el precio histórico.
- Un trigger valida los roles de vendedor y cliente.
- Un trigger impide cambiar el rol de un usuario que ya tiene ventas históricas.
- Un trigger valida que el pago sea igual al total de la venta.
- `pago.id_venta` es `UNIQUE` para respetar la relación 1:1.
- Las entidades de catálogo se desactivan (`estado`) en vez de borrarse cuando ya tienen referencias.

## Código relacionado

- `sql/schema.sql`: DDL, índices y funciones PL/pgSQL.
- `app/services.py`: frontera transaccional de venta y anulación.
- `app/domain.py`: cálculos y validaciones puras.
- `sql/reports.sql`: consultas gerenciales de apoyo.
