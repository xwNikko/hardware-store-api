from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.dependencies import get_logged_user, no_autorizado

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/tienda")
def tienda_dashboard(request: Request):
    user = get_logged_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["rol"] != "tienda":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor(as_dict=True)

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
            SELECT TOP 20 v.id, v.fecha, v.total
            FROM ventas v
            WHERE v.ubicacion_id = %s
            ORDER BY v.fecha DESC
            """,
            (user["ubicacion_id"],),
        )
        ultimas_ventas = cursor.fetchall()

        otras_tiendas = []
        if user["es_principal"]:
            cursor.execute(
                "SELECT id, nombre FROM ubicaciones WHERE id <> %s ORDER BY nombre",
                (user["ubicacion_id"],),
            )
            otras_tiendas = cursor.fetchall()

    return templates.TemplateResponse(
        request,
        "tienda.html",
        {
            "user": user,
            "stock": stock,
            "productos": productos,
            "ultimas_ventas": ultimas_ventas,
            "otras_tiendas": otras_tiendas,
        },
    )


@router.post("/tienda/venta")
def registrar_venta(request: Request, producto_id: int = Form(...), cantidad: int = Form(...)):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor(as_dict=True)

        cursor.execute("SELECT precio_venta FROM productos WHERE id = %s", (producto_id,))
        precio_unitario = cursor.fetchone()["precio_venta"]
        total = float(precio_unitario) * cantidad

        cursor.execute(
            "INSERT INTO ventas (ubicacion_id, usuario_id, total) OUTPUT INSERTED.id VALUES (%s, %s, %s)",
            (user["ubicacion_id"], user["id"], total),
        )
        venta_id = cursor.fetchone()["id"]

        cursor.execute(
            """
            INSERT INTO venta_detalle (venta_id, producto_id, cantidad, precio_unitario)
            VALUES (%s, %s, %s, %s)
            """,
            (venta_id, producto_id, cantidad, precio_unitario),
        )

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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO movimientos (producto_id, tipo, origen_id, destino_id, cantidad, usuario_id, nota)
            VALUES (%s, 'entrada', NULL, %s, %s, %s, %s)
            """,
            (producto_id, user["ubicacion_id"], cantidad, user["id"], nota),
        )

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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO movimientos (producto_id, tipo, origen_id, destino_id, cantidad, usuario_id, nota)
            VALUES (%s, 'transferencia', %s, %s, %s, %s, %s)
            """,
            (producto_id, user["ubicacion_id"], destino_id, cantidad, user["id"], nota),
        )

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

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO movimientos (producto_id, tipo, origen_id, destino_id, cantidad, usuario_id, nota)
            VALUES (%s, 'ajuste', NULL, %s, %s, %s, %s)
            """,
            (producto_id, user["ubicacion_id"], cantidad, user["id"], nota),
        )

    return RedirectResponse("/tienda", status_code=303)
