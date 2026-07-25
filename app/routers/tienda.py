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

        # Total vendido hoy por esta tienda (usando el "hoy" de Perú, no el de UTC)
        cursor.execute(
            """
            SELECT ISNULL(SUM(total), 0) AS total_hoy, COUNT(*) AS num_ventas_hoy
            FROM ventas
            WHERE ubicacion_id = %s
              AND CAST(DATEADD(HOUR, -5, fecha) AS DATE) = CAST(DATEADD(HOUR, -5, GETDATE()) AS DATE)
            """,
            (user["ubicacion_id"],),
        )
        resumen_hoy = cursor.fetchone()

        # Historial: cada venta individual de los últimos 60 días, para armar
        # las pestañas por día (cada día se calcula por separado).
        # Las fechas se guardan en UTC; se ajustan a hora de Perú (UTC-5) para mostrarlas.
        cursor.execute(
            """
            SELECT
                v.id,
                CAST(DATEADD(HOUR, -5, v.fecha) AS DATE) AS dia,
                DATEADD(HOUR, -5, v.fecha) AS fecha_local,
                v.total, v.punto_recojo_id, u.nombre AS punto_recojo
            FROM ventas v
            JOIN ubicaciones u ON u.id = v.punto_recojo_id
            WHERE v.ubicacion_id = %s AND v.fecha >= DATEADD(day, -61, GETDATE())
            ORDER BY v.fecha DESC
            """,
            (user["ubicacion_id"],),
        )
        ventas_detalle = cursor.fetchall()

        dias = {}
        for v in ventas_detalle:
            clave = str(v["dia"])
            if clave not in dias:
                dias[clave] = {"total": 0.0, "num_ventas": 0, "ventas": []}
            dias[clave]["total"] += float(v["total"])
            dias[clave]["num_ventas"] += 1
            dias[clave]["ventas"].append(v)

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
            "resumen_hoy": resumen_hoy,
            "dias": dias,
            "todas_ubicaciones": todas_ubicaciones,
            "otras_tiendas": otras_tiendas,
            "notas": notas,
        },
    )


@router.post("/tienda/venta")
async def registrar_venta(request: Request):
    user = get_logged_user(request)
    if not user or user["rol"] != "tienda":
        return no_autorizado()

    form = await request.form()
    punto_recojo_id = int(form.get("punto_recojo_id"))
    producto_ids = form.getlist("producto_id[]")
    cantidades = form.getlist("cantidad[]")

    items = []
    for pid, cant in zip(producto_ids, cantidades):
        if pid and cant:
            items.append((int(pid), int(cant)))

    if not items:
        set_flash(request, "Agrega al menos un producto antes de vender.")
        return RedirectResponse("/tienda", status_code=303)

    try:
        with get_db() as conn:
            cursor = conn.cursor(as_dict=True)

            total = 0.0
            detalles = []
            for producto_id, cantidad in items:
                cursor.execute("SELECT precio_venta FROM productos WHERE id = %s", (producto_id,))
                precio_unitario = cursor.fetchone()["precio_venta"]
                total += float(precio_unitario) * cantidad
                detalles.append((producto_id, cantidad, precio_unitario))

            cursor.execute(
                """
                INSERT INTO ventas (ubicacion_id, usuario_id, total, punto_recojo_id)
                OUTPUT INSERTED.id VALUES (%s, %s, %s, %s)
                """,
                (user["ubicacion_id"], user["id"], total, punto_recojo_id),
            )
            venta_id = cursor.fetchone()["id"]

            for producto_id, cantidad, precio_unitario in detalles:
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


@router.get("/tienda/venta/{venta_id}/boleta")
def ver_boleta(request: Request, venta_id: int):
    user = get_logged_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["rol"] not in ("tienda", "gerente"):
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor(as_dict=True)

        cursor.execute(
            """
            SELECT v.id, v.ubicacion_id, DATEADD(HOUR, -5, v.fecha) AS fecha_local, v.total,
                   u_venta.nombre AS tienda_venta, u_recojo.nombre AS tienda_recojo
            FROM ventas v
            JOIN ubicaciones u_venta ON u_venta.id = v.ubicacion_id
            JOIN ubicaciones u_recojo ON u_recojo.id = v.punto_recojo_id
            WHERE v.id = %s
            """,
            (venta_id,),
        )
        venta = cursor.fetchone()

        if not venta:
            return no_autorizado()

        # una tienda solo puede ver boletas de sus propias ventas; el gerente ve todas
        if user["rol"] == "tienda" and venta["ubicacion_id"] != user["ubicacion_id"]:
            return no_autorizado()

        cursor.execute(
            """
            SELECT p.sku, p.nombre, d.cantidad, d.precio_unitario,
                   (d.cantidad * d.precio_unitario) AS subtotal
            FROM venta_detalle d
            JOIN productos p ON p.id = d.producto_id
            WHERE d.venta_id = %s
            """,
            (venta_id,),
        )
        items = cursor.fetchall()

    return templates.TemplateResponse(request, "boleta.html", {"venta": venta, "items": items})


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
