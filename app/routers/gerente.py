from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.dependencies import get_logged_user, no_autorizado

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/gerente")
def gerente_dashboard(request: Request):
    user = get_logged_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if user["rol"] != "gerente":
        return no_autorizado()

    with get_db() as conn:
        cursor = conn.cursor(as_dict=True)

        cursor.execute(
            """
            SELECT u.nombre AS ubicacion, p.sku, p.nombre AS producto, i.cantidad
            FROM inventario i
            JOIN productos p ON p.id = i.producto_id
            JOIN ubicaciones u ON u.id = i.ubicacion_id
            ORDER BY u.nombre, p.nombre
            """
        )
        inventario = cursor.fetchall()

        cursor.execute(
            """
            SELECT u.nombre AS ubicacion, COUNT(v.id) AS num_ventas, ISNULL(SUM(v.total), 0) AS total_vendido
            FROM ubicaciones u
            LEFT JOIN ventas v ON v.ubicacion_id = u.id AND CAST(v.fecha AS DATE) = CAST(GETDATE() AS DATE)
            GROUP BY u.nombre
            """
        )
        ventas_hoy = cursor.fetchall()

        cursor.execute(
            """
            SELECT u.nombre AS ubicacion, n.descripcion, n.cantidad, n.creado_en
            FROM notas_faltantes n
            JOIN ubicaciones u ON u.id = n.ubicacion_id
            WHERE n.estado = 'pendiente'
            ORDER BY n.creado_en DESC
            """
        )
        notas_pendientes = cursor.fetchall()

    return templates.TemplateResponse(
        request,
        "gerente.html",
        {
            "user": user,
            "inventario": inventario,
            "ventas_hoy": ventas_hoy,
            "notas_pendientes": notas_pendientes,
        },
    )
