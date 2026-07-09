import pyodbc
from contextlib import contextmanager

from app.config import DB_SERVER, DB_DATABASE, DB_TRUSTED_CONNECTION, DB_USER, DB_PASSWORD


def _connection_string() -> str:
    if DB_TRUSTED_CONNECTION.lower() == "yes":
        return (
            "DRIVER={ODBC Driver 17 for SQL Server};"
            f"SERVER={DB_SERVER};DATABASE={DB_DATABASE};Trusted_Connection=yes;"
        )
    return (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={DB_SERVER};DATABASE={DB_DATABASE};"
        f"UID={DB_USER};PWD={DB_PASSWORD};"
    )


@contextmanager
def get_db():
    """
    Uso:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ...")
    Hace commit automático si todo sale bien, y rollback si hay un error.
    """
    conn = pyodbc.connect(_connection_string())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
