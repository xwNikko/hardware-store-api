from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.database import get_db
from app.security import verify_password

router = APIRouter()
templates = Jinja2Templates(directory="templates")

DESTINO_POR_ROL = {
    "tienda": "/tienda",
    "gerente": "/gerente",
}


@router.get("/login")
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)):
    with get_db() as conn:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(
            """
            SELECT u.id, u.nombre, u.password_hash, u.rol, u.ubicacion_id, ub.es_principal
            FROM usuarios u
            LEFT JOIN ubicaciones ub ON ub.id = u.ubicacion_id
            WHERE u.email = %s
            """,
            (email,),
        )
        row = cursor.fetchone()

    if not row or not verify_password(password, row["password_hash"]):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Correo o contraseña incorrectos"},
        )

    request.session["user"] = {
        "id": row["id"],
        "nombre": row["nombre"],
        "rol": row["rol"],
        "ubicacion_id": row["ubicacion_id"],
        "es_principal": bool(row["es_principal"]) if row["es_principal"] is not None else False,
    }

    return RedirectResponse(DESTINO_POR_ROL[row["rol"]], status_code=303)


@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
