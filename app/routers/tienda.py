from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Optional

from app.database import get_db
from app.dependencies import get_logged_user, no_autorizado, set_flash, get_and_clear_flash

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def mensaje_amigable(error: Exception) -> str:
    texto = str(error)
    if "Stock insuficiente" in texto:
        return "No hay stock suficiente para completar esta operación."
    return "Ocurrió un error al procesar esta acción. Intenta de nuevo."


@router.get("/tienda")
def tienda_dashboard(request: Request):
    user = get_logged_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["rol"] != "tienda":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor(as_dict=True)

        error = get_and_clear_flash(request)

        cursor.execute(
            """
            SELECT p.sku, p.nombre, i.cantidad, p.precio_venta
            FROM inventario i
            JOIN productos p ON p.id = i.producto_id
            WHERE i.ubicacion_id = %s
            ORDER BY p.nombre
            """,
            (user["ubicacion_id"],),
        )
        stock = cursor.fetchall()

        cursor.execute("SELECT id, sku, nombre, precio_venta FROM productos ORDER BY nombre")
        productos = cursor.fetchall()

        cursor.execute(
            """
            SELECT TOP 20 v.id, v.fecha, v.total, v.punto_recojo_id, u.nombre AS punto_recojo
            FROM ventas v
            JOIN ubicaciones u ON u.id = v.punto_recojo_id
            WHERE v.ubicacion_id = %s
            ORDER BY v.fecha DESC
            """,
            (user["ubicacion_id"],),
        )
        ultimas_ventas = cursor.fetchall()

        # Total vendido hoy por esta tienda
        cursor.execute(
            """
            SELECT ISNULL(SUM(total), 0) AS total_hoy, COUNT(*) AS num_ventas_hoy
            FROM ventas
            WHERE ubicacion_id = %s AND CAST(fecha AS DATE) = CAST(GETDATE() AS DATE)
            """,
            (user["ubicacion_id"],),
        )
        resumen_hoy = cursor.fetchone()

        # Todas las ubicaciones (para elegir punto de recojo al vender)
        cursor.execute("SELECT id, nombre FROM ubicaciones ORDER BY nombre")
        todas_ubicaciones = cursor.fetchall()

        otras_tiendas = []
        if user["es_principal"]:
            cursor.execute(
                "SELECT id, nombre FROM ubicaciones WHERE id <> %s ORDER BY nombre",
                (user["ubicacion_id"],),
            )
            otras_tiendas = cursor.fetchall()

        # Notas de faltantes de esta tienda
        cursor.execute(
            """
            SELECT id, descripcion, cantidad, estado, creado_en
            FROM notas_faltantes
            WHERE ubicacion_id = %s
            ORDER BY CASE WHEN estado = 'pendiente' THEN 0 ELSE 1 END, creado_en DESC
            """,
            (user["ubicacion_id"],),
        )
        notas = cursor.fetchall()

    return templates.TemplateResponse(
        request,
        "tienda.html",
        {
            "user": user,
            "error": error,
            "stock": stock,
            "productos": productos,
            "ultimas_ventas": ultimas_ventas,
            "resumen_hoy": resumen_hoy,
            "todas_ubicaciones": todas_ubicaciones,
            "otras_tiendas": otras_tiendas,
            "notas": notas,
        },
    )


@router.post("/tienda/venta")
def registrar_venta(
    request: Request,
    producto_id: int = Form(...),
    cantidad: int = Form(...),
    punto_recojo_id: int = Form(...),
):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    try:
        with get_db() as conn:
            cursor = conn.cursor(as_dict=True)

            cursor.execute("SELECT precio_venta FROM productos WHERE id = %s", (producto_id,))
            precio_unitario = cursor.fetchone()["precio_venta"]
            total = float(precio_unitario) * cantidad

            cursor.execute(
                """
                INSERT INTO ventas (ubicacion_id, usuario_id, total, punto_recojo_id)
                OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)
                """,
                (user["ubicacion_id"], user["id"], total, punto_recojo_id),
            )
            venta_id = cursor.fetchone()["id"]

            cursor.execute(
                """
                INSERT INTO venta_detalle (venta_id, producto_id, cantidad, precio_unitario)
                VALUES (%s, %s, %s, %s)
                """,
                (venta_id, producto_id, cantidad, precio_unitario),
            )
    except Exception as e:
        set_flash(request, mensaje_amigable(e))

    return RedirectResponse("/tienda", status_code=303)


@router.post("/tienda/entrada")
def registrar_entrada(
    request: Request,
    producto_id: int = Form(...),
    cantidad: int = Form(...),
    nota: str = Form(""),
):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO movimientos (producto_id, tipo, origen_id, destino_id, cantidad, usuario_id, nota)
                VALUES (%s, 'entrada', NULL, %s, %s, %s, %s)
                """,
                (producto_id, user["ubicacion_id"], cantidad, user["id"], nota),
            )
    except Exception as e:
        set_flash(request, mensaje_amigable(e))

    return RedirectResponse("/tienda", status_code=303)


@router.post("/tienda/transferencia")
def registrar_transferencia(
    request: Request,
    producto_id: int = Form(...),
    destino_id: int = Form(...),
    cantidad: int = Form(...),
    nota: str = Form(""),
):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()
    if not user["es_principal"]:
        return no_autorizado()

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO movimientos (producto_id, tipo, origen_id, destino_id, cantidad, usuario_id, nota)
                VALUES (%s, 'transferencia', %s, %s, %s, %s, %s)
                """,
                (producto_id, user["ubicacion_id"], destino_id, cantidad, user["id"], nota),
            )
    except Exception as e:
        set_flash(request, mensaje_amigable(e))

    return RedirectResponse("/tienda", status_code=303)


@router.post("/tienda/ajuste")
def registrar_ajuste(
    request: Request,
    producto_id: int = Form(...),
    cantidad: int = Form(...),
    nota: str = Form(""),
):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO movimientos (producto_id, tipo, origen_id, destino_id, cantidad, usuario_id, nota)
                VALUES (%s, 'ajuste', NULL, %s, %s, %s, %s)
                """,
                (producto_id, user["ubicacion_id"], cantidad, user["id"], nota),
            )
    except Exception as e:
        set_flash(request, mensaje_amigable(e))

    return RedirectResponse("/tienda", status_code=303)


@router.post("/tienda/producto-nuevo")
def crear_producto(
    request: Request,
    sku: str = Form(...),
    nombre: str = Form(...),
    categoria: str = Form(""),
    precio_compra: float = Form(0),
    precio_venta: float = Form(...),
):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO productos (sku, nombre, categoria, precio_compra, precio_venta)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (sku, nombre, categoria, precio_compra, precio_venta),
        )

    return RedirectResponse("/tienda", status_code=303)


@router.post("/tienda/nota")
def crear_nota(
    request: Request,
    descripcion: str = Form(...),
    cantidad: Optional[int] = Form(None),
):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO notas_faltantes (ubicacion_id, usuario_id, descripcion, cantidad)
            VALUES (%s, %s, %s, %s)
            """,
            (user["ubicacion_id"], user["id"], descripcion, cantidad),
        )

    return RedirectResponse("/tienda", status_code=303)


@router.post("/tienda/nota/resolver")
def resolver_nota(request: Request, nota_id: int = Form(...)):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE notas_faltantes SET estado = 'resuelto' WHERE id = %s AND ubicacion_id = %s",
            (nota_id, user["ubicacion_id"]),
        )

    return RedirectResponse("/tienda", status_code=303)
