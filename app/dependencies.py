from fastapi import Request
from fastapi.responses import HTMLResponse


def get_logged_user(request: Request):
    """Devuelve el usuario guardado en la sesión, o None si no ha iniciado sesión."""
    return request.session.get("user")


def set_flash(request: Request, mensaje: str) -> None:
    """Guarda un mensaje para mostrarlo una sola vez, justo después de una redirección."""
    request.session["flash"] = mensaje


def get_and_clear_flash(request: Request):
    """Devuelve el mensaje guardado (si existe) y lo borra, para que no se repita."""
    return request.session.pop("flash", None)


def no_autorizado() -> HTMLResponse:
    return HTMLResponse(
        "<h2>403 - No tienes permiso para ver esta página</h2>"
        "<a href='/login'>Volver a iniciar sesión</a>",
        status_code=403,
    )
