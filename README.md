# Sistema de inventario - Ferretería

Backend + páginas web en Python (FastAPI) conectado a SQL Server.

## 1. Requisitos previos

- Python 3.10 o superior
- SQL Server con la base de datos ya creada (tablas y triggers del script `inventario_ferreteria_sqlserver.sql`)
- **ODBC Driver 17 for SQL Server** instalado en tu computadora. Si tienes SSMS instalado
  es posible que ya lo tengas; si al ejecutar el proyecto te sale un error de "Data source
  name not found", descarga "Microsoft ODBC Driver 17 for SQL Server" desde el sitio de
  Microsoft e instálalo.

## 2. Instalación

Abre una terminal en esta carpeta y ejecuta:

```bash
python -m venv venv
venv\Scripts\activate          # en Windows
# source venv/bin/activate     # en Mac/Linux

pip install -r requirements.txt
```

## 3. Configuración

Copia el archivo `.env.example` y renómbralo a `.env`. Ábrelo y ajusta:

- `DB_SERVER`: el nombre de tu servidor tal como aparece en SSMS al conectarte
  (por ejemplo `localhost\SQLEXPRESS` o `LAPTOP-R3J1K349\NIKKO...`)
- `DB_DATABASE`: el nombre de la base de datos donde corriste el script SQL
- `SECRET_KEY`: cualquier texto largo y aleatorio

## 4. Crear los primeros usuarios

Con la base de datos ya creada, ejecuta:

```bash
python crear_usuario.py
```

Y sigue las instrucciones en pantalla. Crea al menos:
- Un usuario con rol `almacen` (ligado a la ubicación "Almacén principal")
- Un usuario con rol `tienda` para "Tienda 1"
- Un usuario con rol `tienda` para "Tienda 2"
- Un usuario con rol `gerente` (no necesita ubicación)

## 5. Cargar productos

Por ahora, carga tus productos directamente en SSMS con un INSERT, por ejemplo:

```sql
INSERT INTO productos (sku, nombre, categoria, precio_compra, precio_venta)
VALUES ('MAR-001', 'Martillo 16 oz', 'Herramientas manuales', 15.00, 25.00);
```

(Si quieres, en un siguiente paso te puedo agregar una pantalla para cargar productos
desde la propia aplicación en vez de hacerlo por SQL.)

## 6. Ejecutar la aplicación

```bash
uvicorn app.main:app --reload
```

Abre tu navegador en: **http://localhost:8000**

Inicia sesión con cualquiera de los usuarios que creaste, y verás la página
correspondiente a su rol (almacén, tienda o gerente).

## Estructura del proyecto

```
ferreteria_api/
  app/
    main.py          <- arranca la aplicación
    config.py        <- lee el archivo .env
    database.py      <- conexión a SQL Server
    security.py      <- encriptar/verificar contraseñas
    dependencies.py  <- saber quién está logueado
    routers/
      auth.py        <- login / logout
      almacen.py     <- panel de almacén
      tienda.py      <- panel de tienda
      gerente.py     <- panel de gerente
  templates/         <- páginas HTML
  crear_usuario.py   <- script para crear usuarios
  requirements.txt
  .env               <- tu configuración (créalo desde .env.example)
```

## Próximos pasos sugeridos

- Agregar una pantalla para cargar productos sin usar SQL directo
- Agregar validación de que la tienda no venda más de lo que tiene en stock
  antes de enviarlo (ahora mismo el trigger de la base de datos ya lo bloquea,
  pero sería bueno mostrar un mensaje de error amigable en la página en vez
  de un error genérico)
- Permitir ventas con varios productos en una sola boleta (por ahora cada
  venta registra un solo producto)
