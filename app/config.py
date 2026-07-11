import os
from dotenv import load_dotenv

load_dotenv()

DB_SERVER = os.getenv("DB_SERVER", "localhost")
DB_DATABASE = os.getenv("DB_DATABASE", "Ferreteria")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
SECRET_KEY = os.getenv("SECRET_KEY", "clave-temporal-cambiar-en-produccion")
