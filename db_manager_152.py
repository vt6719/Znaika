import aiosqlite
import hashlib
import datetime

# Имя файла базы данных
DB_NAME = "consents_secure.db"


async def init_db():
    """Создает таблицу, если её нет, с полями для хеш-цепочки"""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS consent_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                doc_version TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                prev_hash TEXT NOT NULL,  -- Связь с предыдущей записью
                curr_hash TEXT NOT NULL   -- Уникальный отпечаток этой записи
            )
        """)
        await db.commit()


def calculate_hash(prev_hash, user_id, timestamp, doc_version):
    """Генерирует криптографический хеш SHA-256"""
    # Склеиваем данные в одну строку
    raw_string = f"{prev_hash}|{user_id}|{timestamp}|{doc_version}"
    # Превращаем в хеш
    return hashlib.sha256(raw_string.encode('utf-8')).hexdigest()


async def add_consent(user_id, username, full_name, doc_version):
    """Добавляет запись и пересчитывает цепочку хешей"""
    async with aiosqlite.connect(DB_NAME) as db:
        # 1. Берем хеш самой последней записи
        cursor = await db.execute("SELECT curr_hash FROM consent_log ORDER BY id DESC LIMIT 1")
        row = await cursor.fetchone()

        # Если записей нет (первый запуск), берем "нулевой" хеш
        if row:
            last_hash = row[0]
        else:
            last_hash = "0" * 64

            # 2. Фиксируем время UTC
        timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 3. Считаем хеш для НОВОЙ записи (включая хеш предыдущей)
        new_hash = calculate_hash(last_hash, user_id, timestamp, doc_version)

        # 4. Сохраняем в базу
        await db.execute("""
            INSERT INTO consent_log 
            (user_id, username, full_name, doc_version, timestamp, prev_hash, curr_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, doc_version, timestamp, last_hash, new_hash))

        await db.commit()

        return timestamp, new_hash