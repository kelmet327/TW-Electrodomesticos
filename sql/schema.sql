-- Bear's Scourge POS
-- Esquema relacional PostgreSQL 16 basado en el diccionario de datos del proyecto.
-- El script es idempotente y puede ejecutarse más de una vez.

BEGIN;

CREATE TABLE IF NOT EXISTS usuario (
    id_usuario      SERIAL PRIMARY KEY,
    nombre          VARCHAR(60)  NOT NULL CHECK (char_length(btrim(nombre)) > 0),
    apellido        VARCHAR(60)  NOT NULL CHECK (char_length(btrim(apellido)) > 0),
    correo          VARCHAR(120) NOT NULL UNIQUE CHECK (char_length(btrim(correo)) > 0),
    contrasena      VARCHAR(255) NOT NULL,
    telefono        VARCHAR(20),
    direccion       VARCHAR(200),
    ciudad          VARCHAR(80),
    rol             VARCHAR(20)  NOT NULL DEFAULT 'cliente'
                     CHECK (rol IN ('vendedor', 'cliente')),
    fecha_registro  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    estado          BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS categoria (
    id_categoria  SERIAL PRIMARY KEY,
    nombre        VARCHAR(80)  NOT NULL UNIQUE CHECK (char_length(btrim(nombre)) > 0),
    descripcion   VARCHAR(255),
    estado        BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS marca (
    id_marca      SERIAL PRIMARY KEY,
    nombre        VARCHAR(80)  NOT NULL UNIQUE CHECK (char_length(btrim(nombre)) > 0),
    pais_origen   VARCHAR(80),
    estado        BOOLEAN      NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS producto (
    id_producto   SERIAL PRIMARY KEY,
    nombre        VARCHAR(150) NOT NULL CHECK (char_length(btrim(nombre)) > 0),
    descripcion   TEXT,
    modelo        VARCHAR(80),
    precio        NUMERIC(10,2) NOT NULL CHECK (precio >= 0),
    stock         INTEGER      NOT NULL DEFAULT 0 CHECK (stock >= 0),
    imagen_url    VARCHAR(255),
    id_categoria  INTEGER      NOT NULL,
    id_marca      INTEGER      NOT NULL,
    estado        BOOLEAN      NOT NULL DEFAULT TRUE,
    fecha_creacion TIMESTAMP   NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_producto_categoria
        FOREIGN KEY (id_categoria) REFERENCES categoria (id_categoria)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_producto_marca
        FOREIGN KEY (id_marca) REFERENCES marca (id_marca)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS venta (
    id_venta             SERIAL PRIMARY KEY,
    id_vendedor          INTEGER      NOT NULL,
    id_cliente           INTEGER,
    fecha_venta          TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    subtotal             NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (subtotal >= 0),
    impuesto             NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (impuesto >= 0),
    total                NUMERIC(10,2) NOT NULL CHECK (total >= 0),
    direccion_entrega    VARCHAR(200),
    estado               VARCHAR(20)  NOT NULL
                         CHECK (estado IN ('pendiente', 'completada', 'anulada')),
    CONSTRAINT ck_venta_total CHECK (total = subtotal + impuesto),
    CONSTRAINT ck_venta_subtotal_positivo CHECK (subtotal > 0),
    CONSTRAINT ck_venta_cliente_diferente CHECK (id_cliente IS NULL OR id_cliente <> id_vendedor),
    CONSTRAINT fk_venta_vendedor
        FOREIGN KEY (id_vendedor) REFERENCES usuario (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_venta_cliente
        FOREIGN KEY (id_cliente) REFERENCES usuario (id_usuario)
        ON UPDATE RESTRICT ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS detalle_venta (
    id_detalle_venta  SERIAL PRIMARY KEY,
    id_venta          INTEGER      NOT NULL,
    id_producto       INTEGER      NOT NULL,
    cantidad          INTEGER      NOT NULL CHECK (cantidad > 0 AND cantidad <= 999),
    precio_unitario   NUMERIC(10,2) NOT NULL CHECK (precio_unitario >= 0),
    subtotal          NUMERIC(10,2) NOT NULL CHECK (subtotal >= 0),
    CONSTRAINT ck_detalle_subtotal
        CHECK (subtotal = round(cantidad * precio_unitario, 2)),
    CONSTRAINT fk_detalle_venta
        FOREIGN KEY (id_venta) REFERENCES venta (id_venta)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_detalle_producto
        FOREIGN KEY (id_producto) REFERENCES producto (id_producto)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT uq_detalle_venta_producto UNIQUE (id_venta, id_producto)
);

CREATE TABLE IF NOT EXISTS pago (
    id_pago       SERIAL PRIMARY KEY,
    id_venta      INTEGER      NOT NULL UNIQUE,
    metodo        VARCHAR(20)  NOT NULL
                  CHECK (metodo IN ('tarjeta_credito', 'tarjeta_debito', 'transferencia', 'efectivo', 'paypal')),
    monto         NUMERIC(10,2) NOT NULL CHECK (monto > 0),
    estado        VARCHAR(20)  NOT NULL
                  CHECK (estado IN ('pendiente', 'aprobado', 'rechazado', 'reembolsado')),
    referencia    VARCHAR(100),
    fecha_pago    TIMESTAMP
);

-- Índices para las consultas más frecuentes del POS y los reportes.
CREATE INDEX IF NOT EXISTS idx_usuario_rol_estado ON usuario (rol, estado);
CREATE INDEX IF NOT EXISTS idx_usuario_fecha ON usuario (fecha_registro DESC);
CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_correo_normalizado ON usuario (lower(correo));
CREATE UNIQUE INDEX IF NOT EXISTS uq_categoria_nombre_normalizado ON categoria (lower(nombre));
CREATE UNIQUE INDEX IF NOT EXISTS uq_marca_nombre_normalizado ON marca (lower(nombre));
CREATE INDEX IF NOT EXISTS idx_producto_catalogo
    ON producto (estado, id_categoria, id_marca, nombre);
CREATE INDEX IF NOT EXISTS idx_producto_categoria ON producto (id_categoria);
CREATE INDEX IF NOT EXISTS idx_producto_marca ON producto (id_marca);
CREATE INDEX IF NOT EXISTS idx_producto_stock ON producto (stock) WHERE stock <= 10;
CREATE INDEX IF NOT EXISTS idx_venta_fecha ON venta (fecha_venta DESC);
CREATE INDEX IF NOT EXISTS idx_venta_vendedor_fecha ON venta (id_vendedor, fecha_venta DESC);
CREATE INDEX IF NOT EXISTS idx_venta_cliente_fecha ON venta (id_cliente, fecha_venta DESC);
CREATE INDEX IF NOT EXISTS idx_venta_estado ON venta (estado);
CREATE INDEX IF NOT EXISTS idx_detalle_producto ON detalle_venta (id_producto);

-- Verifica que los usuarios asociados a una venta tengan el rol correcto.
CREATE OR REPLACE FUNCTION validar_usuarios_venta()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM usuario
        WHERE id_usuario = NEW.id_vendedor
          AND rol = 'vendedor'
          AND estado = TRUE
    ) THEN
        RAISE EXCEPTION 'El vendedor no existe, está inactivo o no tiene el rol requerido'
            USING ERRCODE = '23514';
    END IF;

    IF NEW.id_cliente IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM usuario
        WHERE id_usuario = NEW.id_cliente
          AND rol = 'cliente'
          AND estado = TRUE
    ) THEN
        RAISE EXCEPTION 'El cliente no existe, está inactivo o no tiene el rol requerido'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_usuarios_venta ON venta;
CREATE TRIGGER trg_validar_usuarios_venta
BEFORE INSERT OR UPDATE OF id_vendedor, id_cliente ON venta
FOR EACH ROW EXECUTE FUNCTION validar_usuarios_venta();

-- Un cambio de rol no puede invalidar ventas históricas de vendedor o cliente.
CREATE OR REPLACE FUNCTION proteger_rol_usuario()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.rol = 'vendedor' AND NEW.rol = 'cliente'
       AND EXISTS (SELECT 1 FROM venta WHERE id_vendedor = OLD.id_usuario) THEN
        RAISE EXCEPTION 'No se puede cambiar a cliente un vendedor con ventas registradas'
            USING ERRCODE = '23514';
    END IF;

    IF OLD.rol = 'cliente' AND NEW.rol = 'vendedor'
       AND EXISTS (SELECT 1 FROM venta WHERE id_cliente = OLD.id_usuario) THEN
        RAISE EXCEPTION 'No se puede cambiar a vendedor un cliente con compras registradas'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_proteger_rol_usuario ON usuario;
CREATE TRIGGER trg_proteger_rol_usuario
BEFORE UPDATE OF rol ON usuario
FOR EACH ROW EXECUTE FUNCTION proteger_rol_usuario();

-- Los importes, el vendedor, el cliente y la fecha son históricos e inmutables.
CREATE OR REPLACE FUNCTION proteger_datos_venta()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF ROW(NEW.id_vendedor, NEW.id_cliente, NEW.fecha_venta,
           NEW.subtotal, NEW.impuesto, NEW.total)
       IS DISTINCT FROM
       ROW(OLD.id_vendedor, OLD.id_cliente, OLD.fecha_venta,
           OLD.subtotal, OLD.impuesto, OLD.total) THEN
        RAISE EXCEPTION 'Los datos económicos de una venta son inmutables'
            USING ERRCODE = '23514';
    END IF;

    IF OLD.estado = 'anulada' AND NEW.estado <> 'anulada' THEN
        RAISE EXCEPTION 'Una venta anulada no puede reactivarse'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_proteger_datos_venta ON venta;
CREATE TRIGGER trg_proteger_datos_venta
BEFORE UPDATE ON venta
FOR EACH ROW EXECUTE FUNCTION proteger_datos_venta();

-- Calcula el subtotal de la línea y valida la venta y el producto antes de insertar.
CREATE OR REPLACE FUNCTION preparar_detalle_venta()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    venta_estado VARCHAR(20);
    producto_estado BOOLEAN;
BEGIN
    SELECT estado INTO venta_estado
    FROM venta WHERE id_venta = NEW.id_venta;

    IF venta_estado IS NULL OR venta_estado = 'anulada' THEN
        RAISE EXCEPTION 'No se pueden agregar productos a una venta inexistente o anulada'
            USING ERRCODE = '23514';
    END IF;

    SELECT estado INTO producto_estado
    FROM producto WHERE id_producto = NEW.id_producto;

    IF producto_estado IS NULL OR producto_estado = FALSE THEN
        RAISE EXCEPTION 'El producto no existe o está inactivo'
            USING ERRCODE = '23514';
    END IF;

    NEW.subtotal := round(NEW.cantidad * NEW.precio_unitario, 2);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_preparar_detalle_venta ON detalle_venta;
CREATE TRIGGER trg_preparar_detalle_venta
BEFORE INSERT ON detalle_venta
FOR EACH ROW EXECUTE FUNCTION preparar_detalle_venta();

-- Un detalle de venta es evidencia histórica: solo puede insertarse, no modificarse.
CREATE OR REPLACE FUNCTION impedir_cambio_detalle()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'Las líneas de una venta son inmutables; anule la venta si corresponde'
        USING ERRCODE = '55000';
END;
$$;

DROP TRIGGER IF EXISTS trg_impedir_cambio_detalle ON detalle_venta;
CREATE TRIGGER trg_impedir_cambio_detalle
BEFORE UPDATE OR DELETE ON detalle_venta
FOR EACH ROW EXECUTE FUNCTION impedir_cambio_detalle();

-- Descuento de inventario con bloqueo de fila para evitar sobreventa concurrente.
CREATE OR REPLACE FUNCTION descontar_stock_venta()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    stock_actual INTEGER;
BEGIN
    SELECT stock INTO stock_actual
    FROM producto
    WHERE id_producto = NEW.id_producto
    FOR UPDATE;

    IF stock_actual IS NULL OR stock_actual < NEW.cantidad THEN
        RAISE EXCEPTION 'Stock insuficiente para el producto %', NEW.id_producto
            USING ERRCODE = '23514';
    END IF;

    UPDATE producto
    SET stock = stock - NEW.cantidad
    WHERE id_producto = NEW.id_producto;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_descontar_stock_venta ON detalle_venta;
CREATE TRIGGER trg_descontar_stock_venta
AFTER INSERT ON detalle_venta
FOR EACH ROW EXECUTE FUNCTION descontar_stock_venta();

-- Al anular una venta, recupera exactamente las unidades de sus líneas.
CREATE OR REPLACE FUNCTION restaurar_stock_anulacion()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF OLD.estado IS DISTINCT FROM NEW.estado AND NEW.estado = 'anulada' THEN
        UPDATE producto AS p
        SET stock = p.stock + d.cantidad
        FROM detalle_venta AS d
        WHERE d.id_venta = OLD.id_venta
          AND d.id_producto = p.id_producto;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_restaurar_stock_anulacion ON venta;
CREATE TRIGGER trg_restaurar_stock_anulacion
AFTER UPDATE OF estado ON venta
FOR EACH ROW EXECUTE FUNCTION restaurar_stock_anulacion();

-- El pago debe cubrir exactamente el total de una venta activa.
CREATE OR REPLACE FUNCTION validar_pago()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    total_venta NUMERIC(10,2);
    estado_venta VARCHAR(20);
BEGIN
    SELECT total, estado INTO total_venta, estado_venta
    FROM venta WHERE id_venta = NEW.id_venta;

    IF total_venta IS NULL THEN
        RAISE EXCEPTION 'La venta asociada al pago no existe'
            USING ERRCODE = '23514';
    END IF;
    IF estado_venta = 'anulada' THEN
        RAISE EXCEPTION 'No se puede registrar un pago para una venta anulada'
            USING ERRCODE = '23514';
    END IF;
    IF NEW.monto <> total_venta THEN
        RAISE EXCEPTION 'El monto del pago debe coincidir con el total de la venta'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_pago ON pago;
CREATE TRIGGER trg_validar_pago
BEFORE INSERT OR UPDATE OF id_venta, monto ON pago
FOR EACH ROW EXECUTE FUNCTION validar_pago();

COMMIT;
