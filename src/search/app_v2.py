from flask import Flask, render_template, request, g
import psycopg2
import requests
import json
import os

app = Flask(__name__)

# Подключение к БД
# conn = psycopg2.connect(
# host="localhost", port=5432, dbname="products", user="postgres", password="postgres"
# )

# Параметры подключения
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", 5432),
    "dbname": os.getenv("DB_NAME", "products"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

EMBEDDING_URL = "http://localhost:1234/v1/embeddings"
LLM_URL = "http://localhost:1234/api/v1/chat"


def get_db():
    """Возвращает соединение с БД (создаёт при первом вызове в рамках запроса)"""
    if "db" not in g:
        try:
            g.db = psycopg2.connect(**DB_CONFIG)
        except psycopg2.Error as e:
            # Логируем ошибку, но не даём приложению упасть при старте
            app.logger.error(f"Database connection failed: {e}")
            raise
    return g.db


@app.teardown_appcontext
def close_db(error=None):
    """Закрывает соединение с БД после завершения запроса"""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def parse_query_with_llm(product_name: str) -> dict:
    """Отправляем запрос в LM Studio и получаем JSON с category и attributes"""

    prompt = f"""Запрос: "{product_name}" /no_think"""

    response = requests.post(
        # "http://localhost:1234/api/v1/chat",  # эндпоинт LM Studio
        LLM_URL,  # эндпоинт LM Studio
        json={
            "model": "qwen/qwen3-4b",
            "temperature": 0.1,  # низкая температура для детерминизма
            "system_prompt": 'Ты — эксперт по классификации товаров. Выдели из запроса на поиск товара категорию (тип устройства) и атрибуты (все характеристики, бренд, модель, параметры). Ответ не переводи на русский. Верни строго JSON: {"category": "...", "attributes": "..."}',
            "input": prompt,
        },
    )
    data = response.json()

    # Извлекаем текст ответа (message content)
    message_content = None
    for item in data.get("output", []):
        if item.get("type") == "message":
            message_content = item.get("content", "")
            break

    if not message_content:
        raise ValueError("No message content in response")

    # Очищаем от лишних символов, если нужно
    cleaned = message_content.strip()
    # Удаляем возможные маркеры (например, ```json ... ```)
    if cleaned.startswith("```json") and cleaned.endswith("```"):
        cleaned = cleaned[7:-3].strip()
    elif cleaned.startswith("```") and cleaned.endswith("```"):
        cleaned = cleaned[3:-3].strip()

    # Парсим JSON
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nResponse: {cleaned}")

    return parsed


def get_embedding(text: str, dimensions: int = 1024) -> list:
    """Получаем эмбеддинг через LM Studio (для Qwen3-Embedding-4B)"""

    response = requests.post(
        # "http://127.0.0.1:1234/v1/embeddings",
        EMBEDDING_URL,
        json={
            "input": text,
            "model": "text-embedding-qwen3-embedding-4b",  # название модели в LM Studio
            "dimensions": dimensions,  # поддерживается MRL
        },
    )
    emb = response.json()["data"][0]["embedding"]
    return emb[:dimensions]  # обрезаем до нужной размерности


def search_products(cat_emb, attr_emb, top_k=5):
    """Поиск ближайших товаров по косинусному расстоянию"""
    conn = get_db()
    cur = conn.cursor()

    # Первый этап: поиск кандидатов по attributes_embedding
    cur.execute(
        """
        SELECT id, name, category, attributes,
               embedding_cat <=> %s::vector AS cat_dist,
               embedding_att <=> %s::vector AS attr_dist
        FROM products2
        ORDER BY embedding_att <=> %s::vector
        LIMIT 200
    """,
        (cat_emb if cat_emb else [0.0] * 1024, attr_emb, attr_emb),
    )
    candidates = cur.fetchall()

    # Второй этап: комбинируем расстояния
    w_cat, w_attr = 0.3, 0.7
    scored = [(w_cat * row[4] + w_attr * row[5], row[1]) for row in candidates]
    scored.sort()
    results = [name for _, name in scored[:top_k]]
    return results


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        query = request.form.get("query", "").strip()
        if query:
            # Получаем эмбеддинги запроса (категория и атрибуты)
            parsed = parse_query_with_llm(query)
            cat_emb = get_embedding(parsed["category"]) if parsed["category"] else None

            attributes = parsed.get("attributes", "")
            attr_for_embedding = f"{attributes}".strip()
            attr_emb = get_embedding(attr_for_embedding)

            # # Получить эмбеддинг запроса
            # embedding = get_embedding(query)
            # Поиск
            results = search_products(cat_emb, attr_emb, 10)
            return render_template("index.html", query=query, results=results)
    return render_template("index.html", query="", results=[])


if __name__ == "__main__":
    app.run(debug=True)
