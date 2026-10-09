import psycopg2

from app.database import get_connection


def main():
    connection = None
    try:
        connection = get_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        print("Conexion con PostgreSQL exitosa: la consulta SELECT 1 funciono.")
    except psycopg2.Error as error:
        print(f"No se logro conectar o ejecutar la consulta: {error}")
        raise SystemExit(1) from error
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
