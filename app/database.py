import pymssql
from contextlib import contextmanager

from app.config import DB_SERVER, DB_DATABASE, DB_USER, DB_PASSWORD


@contextmanager
def get_db():
    """
    Uso:
        with get_db() as conn:
            cursor = conn.cursor(as_dict=True)
            cursor.execute("SELECT ...")
    Hace commit automático si todo sale bien, y rollback si hay un error.
    Las filas se devuelven como diccionarios (fila['columna']), no como objetos con punto.
    """
    conn = pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
    )
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
