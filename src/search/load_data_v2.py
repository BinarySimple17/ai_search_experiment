import psycopg2
import requests
import csv
import json

# Подключение к PostgreSQL
conn = psycopg2.connect(
    host="localhost", port=5432, dbname="products", user="postgres", password="postgres"
)
cur = conn.cursor()

# URL API LM Studio для эмбеддингов (по умолчанию)
EMBEDDING_URL = "http://127.0.0.1:1234/v1/embeddings"


def parse_product_with_llm(product_name: str) -> dict:
    """Отправляем название в LM Studio и получаем JSON с category и attributes"""

    prompt = f"""Название: "{product_name}" /no_think"""

    response = requests.post(
        "http://localhost:1234/api/v1/chat",  # эндпоинт LM Studio
        json={
            "model": "qwen/qwen3-4b",
            "temperature": 0.1,  # низкая температура для детерминизма
            "system_prompt": 'Ты — эксперт по классификации товаров. Разбей следующее название товара на категорию (тип устройства) и атрибуты (все характеристики, бренд, модель, параметры). Ответ не переводи на русский. Верни строго JSON: {"category": "...", "attributes": "..."}',
            "input": prompt,
        },
        # json={
        # "prompt": prompt,
        # "max_tokens": 200,
        # "temperature": 0.1,  # низкая температура для детерминизма
        # "stop": ["\n"]
        # }
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
    # raw = response.json()["choices"][0]["text"].strip()

    # # Извлекаем JSON
    # start = raw.find("{")
    # end = raw.rfind("}") + 1
    # if start != -1 and end != 0:
    #     return json.loads(raw[start:end])
    # return {"category": "", "attributes": product_name}


def get_embedding(text: str, dimensions: int = 1024) -> list:
    """Получаем эмбеддинг через LM Studio (для Qwen3-Embedding-4B)"""

    response = requests.post(
        "http://127.0.0.1:1234/v1/embeddings",
        json={
            "input": text,
            "model": "text-embedding-qwen3-embedding-4b",  # название модели в LM Studio
            "dimensions": dimensions,  # поддерживается MRL
        },
    )
    emb = response.json()["data"][0]["embedding"]
    return emb[:dimensions]  # обрезаем до нужной размерности


# def get_embedding(text):
#     """Получить вектор для текста через LM Studio API"""
#     response = requests.post(
#         EMBEDDING_URL,
#         json={
#             "input": text,
#             "model": "text-embedding-qwen3-embedding-4b",  # имя модели, загруженной в LM Studio
#         },
#     )
#     response.raise_for_status()
#     return response.json()["data"][0]["embedding"]


# Чтение CSV и вставка в БД
with open(".csv/product_names.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)  # если есть заголовок "name"
    i = 0
    for row in reader:
        i += 1
        if i > 100:
            break

        name = row["name"]

        # Разделяем названи
        cleared_name = name.replace('"', "")
        parsed = parse_product_with_llm(cleared_name)
        category = parsed.get("category", "")
        attributes = parsed.get("attributes", cleared_name)

        # Получаем эмбеддинги (1024 измерений)
        cat_emb = get_embedding(category) if category else [0.0] * 1024
        attr_for_embedding = f"{attributes}".strip()
        attr_emb = get_embedding(attr_for_embedding)

        # embedding = get_embedding(name)
        cur.execute(
            "INSERT INTO products2 (name, category, attributes, embedding_cat, embedding_att) VALUES (%s, %s, %s, %s::vector, %s::vector)",
            (cleared_name, category, attr_for_embedding, cat_emb, attr_emb),
        )
        conn.commit()
        print(f"Добавлен: {name}")

cur.close()
conn.close()
