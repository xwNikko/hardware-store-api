"""
Script para crear usuarios del sistema (tienda o gerente).
Uso: python crear_usuario.py
Ejecutar desde la carpeta raíz del proyecto (donde está este archivo).
"""

from app.database import get_db
from app.security import hash_password


def main():
    print("=== Crear nuevo usuario ===")
    nombre = input("Nombre completo: ").strip()
    email = input("Email (será su usuario para iniciar sesión): ").strip()
    password = input("Contraseña: ").strip()

    print("\nRoles disponibles: tienda, gerente")
    rol = input("Rol: ").strip().lower()

    ubicacion_id = None
    if rol == "tienda":
        with get_db() as conn:
            cursor = conn.cursor(as_dict=True)
            cursor.execute("SELECT id, nombre, es_principal FROM ubicaciones ORDER BY id")
            print("\nUbicaciones disponibles:")
            for row in cursor.fetchall():
                etiqueta = " (principal)" if row["es_principal"] else ""
                print(f"  {row['id']} - {row['nombre']}{etiqueta}")
        ubicacion_id = int(input("ID de la ubicación de este usuario: ").strip())

    password_hash = hash_password(password)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO usuarios (nombre, email, password_hash, rol, ubicacion_id)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (nombre, email, password_hash, rol, ubicacion_id),
        )

    print(f"\nUsuario '{email}' creado con éxito. Rol: {rol}.")


if __name__ == "__main__":
    main()
