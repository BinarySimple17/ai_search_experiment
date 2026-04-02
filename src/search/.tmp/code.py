def parse_product_with_llm(product_name: str) -> dict:
    """Отправляем название в LM Studio и получаем JSON с category и attributes"""

    prompt = f"""Название: "{product_name}" /no_think"""

    response = requests.post(
        "http://localhost:1234/api/v1/chat",  # эндпоинт LM Studio
        json={
            "model": "qwen/qwen3-4b",
            "system_prompt": 'Ты — эксперт по классификации товаров. Разбей следующее название товара на категорию (тип устройства) и атрибуты (все характеристики, бренд, модель, параметры). Верни строго JSON: {"category": "...", "attributes": "..."}',
            "input": prompt,
        },
        # json={
        # "prompt": prompt,
        # "max_tokens": 200,
        # "temperature": 0.1,  # низкая температура для детерминизма
        # "stop": ["\n"]
        # }
    )
    raw = response.json()["choices"][0]["text"].strip()