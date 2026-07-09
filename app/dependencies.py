from fastapi import Request
from fastapi.responses import HTMLResponse


def get_logged_user(request: Request):
    """Devuelve el usuario guardado en la sesión, o None si no ha iniciado sesión."""
    return request.session.get("user")


def no_autorizado() -> HTMLResponse:
    return HTMLResponse(
        "<h2>403 - No tienes permiso para ver esta página</h2>"
        "<a href='/login'>Volver a iniciar sesión</a>",
        status_code=403,
    )
