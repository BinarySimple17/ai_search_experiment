#### эксперименты с qwen-embedding

##### prepeqs
- PostgreSQL с pgvector
- модели для эмбеддинга и моделью общего назначения.

##### ADR
- запуск локальный, в докере БД PostgreSQL с pgvector.
- LMStudio с text-embedding-qwen3-embedding-4b и qwen/qwen3-4b

init_db_v2.py - создание схемы БД
load_data_v2.py - загрузка названий товаров из тестового набора и расчет векторов
app_v2.py - web-сервис с полем для ввода запроса и простым выводом результатов

##### install
- pip install -r requirements.txt
- в docker-compose.yaml установка postgres с локальным volume в папке проекта.

##### загрузка csv
```mermaid
sequenceDiagram
    participant CSV as CSV-файл (product_names.csv)
    participant LoadScript as load_data_v2.py
    participant LMStudio as LM Studio (локальный сервер)
    participant PG as PostgreSQL (pgvector)

    LoadScript->>CSV: открыть файл, читать строки (DictReader)
    loop для каждой строки (limit 100)
        LoadScript->>LoadScript: очистить name (удалить кавычки)
        LoadScript->>LMStudio: POST /api/v1/chat (qwen/qwen3-4b)<br>system_prompt + input: название товара
        LMStudio-->>LoadScript: JSON {category, attributes}
        note right of LMStudio: Разбивка названия<br>на категорию и атрибуты

        alt category не пуста
            LoadScript->>LMStudio: POST /v1/embeddings<br>model: text-embedding-qwen3-embedding-4b<br>input: category
            LMStudio-->>LoadScript: вектор category (1024d)
        else category пуста
            LoadScript->>LoadScript: создать нулевой вектор [0.0]*1024
        end

        LoadScript->>LMStudio: POST /v1/embeddings<br>model: text-embedding-qwen3-embedding-4b<br>input: attributes
        LMStudio-->>LoadScript: вектор attributes (1024d)

        LoadScript->>PG: INSERT INTO products2<br>(name, category, attributes, embedding_cat, embedding_att)
        PG-->>LoadScript: подтверждение
        LoadScript->>LoadScript: print(f"Добавлен: {name}")
    end
    LoadScript->>PG: закрыть курсор и соединение
```

##### поиск
```mermaid
sequenceDiagram
    participant User as Пользователь (браузер)
    participant Flask as Flask-сервис (app_v2.py)
    participant LMStudio as LM Studio (локальный сервер)
    participant PG as PostgreSQL (pgvector)

    User->>Flask: POST / (запрос search query)
    activate Flask

    Flask->>LMStudio: POST /api/v1/chat (qwen/qwen3-4b)<br>system_prompt + input: query
    LMStudio-->>Flask: JSON {category, attributes}
    note right of LMStudio: Парсинг запроса<br>на категорию и атрибуты

    alt category не пуста
        Flask->>LMStudio: POST /v1/embeddings<br>model: text-embedding-qwen3-embedding-4b<br>input: category
        LMStudio-->>Flask: вектор category (1024d)
    end

    Flask->>LMStudio: POST /v1/embeddings<br>model: text-embedding-qwen3-embedding-4b<br>input: attributes
    LMStudio-->>Flask: вектор attributes (1024d)

    Flask->>PG: SELECT ... ORDER BY embedding_att <=> %s<br>LIMIT 200 (кандидаты)
    PG-->>Flask: 200 строк с id, name, cat_dist, attr_dist

    Flask->>Flask: Вычисление взвешенного расстояния<br>w_cat*cat_dist + w_attr*attr_dist<br>(w_cat=0.3, w_attr=0.7)<br>сортировка и отбор top_k

    Flask-->>User: render_template с результатами поиска
    deactivate Flask
```