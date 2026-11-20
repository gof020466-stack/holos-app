import os
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("DBManager")

DEFAULT_DB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_DB_PATH = os.path.join(DEFAULT_DB_DIR, "transcriptions.db")

class DBManager:
    """
    Менеджер базы данных SQLite для постоянного хранения истории транскрибаций.
    """
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        self._ensure_db_dir()
        self._init_db()

    def _ensure_db_dir(self):
        directory = os.path.dirname(self.db_path)
        if directory and not os.path.exists(directory):
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                logger.error(f"Не удалось создать директорию для БД: {e}")

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # [v3] Встроенный LIKE в SQLite не учитывает регистр только для латиницы;
        # для кириллицы поиск «москва» не находил «Москва» — сравниваем через Python lower()
        conn.create_function("py_lower", 1, lambda s: s.lower() if isinstance(s, str) else s, deterministic=True)
        return conn

    def _init_db(self):
        """
        Инициализирует схему таблиц при первом запуске.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS transcriptions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        text TEXT NOT NULL,
                        words_json TEXT,
                        source TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                # Индекс для ускорения поиска
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_transcriptions_created_at
                    ON transcriptions(created_at DESC)
                """)
                # [v3] Миграция: путь к исходному медиафайлу (для плеера в истории)
                columns = {row[1] for row in cursor.execute("PRAGMA table_info(transcriptions)")}
                if "media_path" not in columns:
                    cursor.execute("ALTER TABLE transcriptions ADD COLUMN media_path TEXT")
                conn.commit()
                logger.info(f"База данных успешно инициализирована: {self.db_path}")
        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")

    def add_item(self, title: str, text: str, words: list, source: str, media_path: Optional[str] = None) -> Optional[int]:
        """
        Добавляет новую запись в базу данных и возвращает её ID.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        words_json = json.dumps(words, ensure_ascii=False) if words else "[]"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO transcriptions (title, text, words_json, source, created_at, updated_at, media_path)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (title, text, words_json, source, now, now, media_path))
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"Ошибка при сохранении транскрибации в БД: {e}")
            return None

    def get_all_items(self) -> List[Dict[str, Any]]:
        """
        Возвращает все записи, отсортированные от новых к старым.
        """
        items = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, text, words_json, source, created_at, updated_at, media_path
                    FROM transcriptions
                    ORDER BY id DESC
                """)
                items = [self._row_to_item(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка при чтении истории из БД: {e}")
        return items

    @staticmethod
    def _row_to_item(row) -> Dict[str, Any]:
        try:
            words = json.loads(row["words_json"]) if row["words_json"] else []
        except Exception:
            words = []
        return {
            "id": row["id"],
            "title": row["title"],
            "text": row["text"],
            "words": words,
            "source": row["source"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "media_path": row["media_path"],
        }

    def search_items(self, query: str) -> List[Dict[str, Any]]:
        """
        Ищет записи по вхождению подстроки в название или текст расшифровки.
        """
        if not query or not query.strip():
            return self.get_all_items()

        q = f"%{query.strip().lower()}%"
        items = []
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, text, words_json, source, created_at, updated_at, media_path
                    FROM transcriptions
                    WHERE py_lower(title) LIKE ? OR py_lower(text) LIKE ?
                    ORDER BY id DESC
                """, (q, q))
                items = [self._row_to_item(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка при поиске в БД: {e}")
        return items

    def update_item(self, item_id: int, title: str, text: str, words: list,
                    media_path: Optional[str] = None) -> bool:
        """[v3, 12.11.2026] Полное обновление записи: черновик на паузе → итог после «стоп запись»."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        words_json = json.dumps(words, ensure_ascii=False) if words else "[]"
        try:
            with self._get_connection() as conn:
                conn.execute("""
                    UPDATE transcriptions
                    SET title = ?, text = ?, words_json = ?, media_path = ?, updated_at = ?
                    WHERE id = ?
                """, (title, text, words_json, media_path, now, item_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении записи ID {item_id}: {e}")
            return False

    def update_item_text(self, item_id: int, new_text: str) -> bool:
        """
        Обновляет отредактированный текст записи.
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE transcriptions
                    SET text = ?, updated_at = ?
                    WHERE id = ?
                """, (new_text, now, item_id))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка при обновлении текста записи ID {item_id}: {e}")
            return False

    def delete_item(self, item_id: int) -> bool:
        """
        Удаляет запись по ID.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transcriptions WHERE id = ?", (item_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка при удалении записи ID {item_id} из БД: {e}")
            return False

    def clear_all(self) -> bool:
        """
        Полностью очищает историю записей.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM transcriptions")
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Ошибка при очистке истории в БД: {e}")
            return False
