from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import SECRET_KEY
from app.routers import auth, tienda, gerente

app = FastAPI(title="Sistema de inventario - Ferretería")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(tienda.router)
app.include_router(gerente.router)


@app.get("/")
def root():
    return RedirectResponse("/login")
