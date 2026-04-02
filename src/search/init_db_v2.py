import psycopg2


def create_table():
    # Параметры подключения к PostgreSQL (измените под себя)
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        dbname="products",
        user="postgres",
        password="postgres",
    )
    cur = conn.cursor()

    # Включаем расширение vector (если ещё не включено)
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # првоерка размерности
    #     SELECT
    #     attname AS column_name,
    #     atttypmod AS dimension
    # FROM pg_attribute
    # WHERE attrelid = 'public.products'::regclass
    #   AND attname = 'embedding';

    # Создаём таблицу products
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products2 (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            attributes TEXT NOT NULL,
            embedding_cat VECTOR(1024),
            embedding_att VECTOR(1024)
        );
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("Таблица 'products2' успешно создана.")


if __name__ == "__main__":
    create_table()
