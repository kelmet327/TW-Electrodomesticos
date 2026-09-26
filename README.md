# Bear's Scourge POS

Sistema de punto de venta web para una tienda de electrodomésticos. La implementación sigue el documento **“TW A6 POS”** y convierte el diseño de base de datos en una aplicación funcional con Flask, PostgreSQL, Apache httpd y mod_wsgi.

## Funcionalidades incluidas

- Catálogo público de productos por categoría y marca.
- Autenticación por sesión restringida a vendedores; las cuentas `cliente` no pueden acceder al sistema.
- Contraseñas almacenadas mediante `werkzeug.security`.
- Panel de control con ventas del día, inventario y alertas de stock bajo.
- CRUD de productos, categorías, marcas y usuarios.
- Ajustes manuales de inventario con validación de stock no negativo.
- Pantalla POS con carrito dinámico, cálculo de IVA y pago por cinco métodos.
- Detalle de venta e impresión de comprobante.
- Anulación transaccional de ventas con devolución de unidades al inventario.
- Reportes por período, producto, categoría, vendedor y método de pago.
- Exportación de ventas a CSV.
- Protección CSRF, redirecciones seguras, contraseñas con hash y consultas parametrizadas.

## Stack

- Python 3.12+
- Flask 3.1
- PostgreSQL 16
- `psycopg2-binary`
- Flask-WTF / CSRF
- HTML5, CSS3 y JavaScript sin framework
- Apache httpd 2.4 + `mod_wsgi`

## Estructura

```text
.
├── app/
│   ├── __init__.py              # factory Flask, errores y CLI
│   ├── auth.py                  # login, logout y registro
│   ├── admin.py                 # catálogo, inventario y usuarios
│   ├── main.py                  # tienda, dashboard y compras
│   ├── sales.py                 # rutas del mostrador
│   ├── reports.py               # reportes y CSV
│   ├── services.py              # transacciones ACID de venta
│   ├── domain.py                # reglas puras y validaciones
│   ├── db.py                    # conexión y comandos de base de datos
│   ├── seed.py                  # datos de demostración
│   ├── static/                  # CSS, JavaScript e ilustraciones
│   └── templates/               # vistas Jinja2
├── sql/
│   ├── schema.sql               # tablas, índices y disparadores
│   └── reports.sql              # consultas reutilizables
├── deploy/apache/               # configuración de Apache/mod_wsgi
├── tests/                       # pruebas unitarias y smoke tests
├── wsgi.py
├── Dockerfile
└── compose.yaml
```

## Puesta en marcha local

### 1. Requisitos

Instala PostgreSQL 16 y Python 3.12 o superior. En Debian/Ubuntu:

```bash
sudo apt install postgresql-16 python3-venv python3-pip
```

Crea el usuario y la base de datos (si aún no existen):

```bash
sudo -u postgres psql -c "CREATE ROLE bears LOGIN PASSWORD 'bears_password';"
sudo -u postgres createdb -O bears bears_scourge
```

Si el servidor usa autenticación por peer y ejecutas los comandos desde una cuenta sin rol, usa `sudo -u postgres` como en los ejemplos.

### 2. Configuración

```bash
cp .env.example .env
```

Edita `.env` y cambia `SECRET_KEY` por una cadena larga y aleatoria. `DATABASE_URL` debe coincidir con el usuario y la base creados arriba.

### 3. Entorno y dependencias

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
```

### 4. Inicializar PostgreSQL

```bash
flask --app wsgi:app init-db
flask --app wsgi:app seed-db
```

`init-db` es idempotente. `seed-db` carga categorías, marcas, productos, un vendedor y tres ventas de ejemplo. El vendedor de demostración es el único usuario que puede iniciar sesión; las cuentas `cliente` quedan solo como fichas de compra y se administran desde `/usuarios`. No uses esos datos en producción.

> **Acceso exclusivo de vendedores.** El login solo admite cuentas con rol `vendedor`; el registro público de clientes y el historial de compras del cliente se eliminaron del flujo de la aplicación.

### 5. Ejecutar en desarrollo

```bash
flask --app wsgi:app run --debug
```

Abre <http://127.0.0.1:5000>.

### Usuarios de demostración

| Rol | Correo | Contraseña | Acceso |
|---|---|---|---|
| Vendedor | `vendedor@bears.local` | `Vendedor123!` | Sí |
| Cliente | `cliente@bears.local` | `Cliente123!` | No (solo ficha de compra) |
| Cliente | `carlos@ejemplo.com` | `Cliente123!` | No (solo ficha de compra) |

## Ejecución con Docker

Docker Compose levanta PostgreSQL 16 y Apache httpd con `mod_wsgi`:

```bash
docker compose up --build
```

La aplicación queda disponible en <http://127.0.0.1:8080>. El servicio web inicializa el esquema y carga datos demo al arrancar. Para detenerla:

```bash
docker compose down
```

Para borrar también el volumen de PostgreSQL:

```bash
docker compose down -v
```

## Apache httpd + mod_wsgi

`deploy/apache/bears_scourge.conf` contiene un VirtualHost de ejemplo. En una instalación local, instala `apache2` y `libapache2-mod-wsgi-py3`, habilita el módulo y ajusta las rutas de `/opt/venv` y `/ruta/al/proyecto`. Después copia la configuración, recarga Apache y usa:

```bash
sudo apache2ctl configtest
sudo systemctl reload apache2
```

El punto de entrada WSGI es `wsgi.py`. La aplicación no depende de un servidor de desarrollo para funcionar en el entorno de entrega.

## Modelo de datos

La referencia completa de campos está en [`docs/diccionario-datos.md`](docs/diccionario-datos.md) y el diagrama de relaciones en [`docs/modelo.md`](docs/modelo.md).

El script `sql/schema.sql` implementa las siete entidades del documento:

- `usuario` — vendedores y clientes.
- `categoria` — agrupación de productos.
- `marca` — fabricante.
- `producto` — precio actual, stock y clasificación.
- `venta` — cabecera, totales y estado.
- `detalle_venta` — producto, cantidad y precio histórico.
- `pago` — relación 1:1 con la venta.

Incluye claves primarias, foráneas, checks, índices y disparadores. El alta de un detalle descuenta stock con `SELECT ... FOR UPDATE`; si no hay unidades suficientes se revierte toda la transacción. Las líneas y los importes históricos son inmutables. Al anular una venta, el trigger de PostgreSQL recupera las unidades y la aplicación marca el pago como reembolsado.

El IVA se configura con `TAX_RATE`; el valor `13` significa 13 %. Todos los totales se calculan nuevamente en Python y se validan mediante constraints de PostgreSQL, por lo que el JavaScript del navegador no es una fuente de confianza.

## Rutas principales

| Ruta | Uso |
|---|---|
| `/` | Catálogo público |
| `/auth/login` | Inicio de sesión (solo vendedores) |
| `/dashboard` | Panel del vendedor |
| `/ventas/nueva` | Caja POS |
| `/ventas` | Historial y filtros |
| `/inventario` | Existencias y ajustes |
| `/productos` | Gestión de productos |
| `/catalogos` | Categorías y marcas |
| `/usuarios` | Vendedores y clientes |
| `/reportes` | Indicadores y CSV |
| `/salud` | Estado de la aplicación y PostgreSQL |

## Pruebas

Las pruebas unitarias no necesitan una base de datos:

```bash
.venv/bin/pytest -q
```

También se puede validar el esquema en PostgreSQL local con:

```bash
.venv/bin/flask --app wsgi:app init-db
.venv/bin/flask --app wsgi:app seed-db
```

Para una revisión rápida de la interfaz, inicia Flask y prueba el flujo vendedor → nueva venta → confirmar pago → detalle → anular.

## Alcance académico

La aplicación implementa el POS de mostrador completo. El acceso al sistema es exclusivo del personal vendedor; los clientes se registran únicamente como fichas de compra y pueden asociarse a una venta desde la caja. La pasarela de pago es funcional a nivel de registro del método y estado del pago, pero no procesa cobros reales con una pasarela externa. Para producción se deben agregar migraciones versionadas, una pasarela certificada, backups, logging centralizado, HTTPS, límites de intentos de acceso y una política de contraseñas más estricta.
