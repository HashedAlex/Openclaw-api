import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import app
from app.services.sqlite_store import SQLiteStore


class FetchPostsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)
        self.temp_dir = TemporaryDirectory()
        self.db_path = f"{self.temp_dir.name}/test.db"

    def tearDown(self) -> None:
        app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    def override_settings(self) -> Settings:
        return Settings(
            zsxq_access_token="token",
            group_id="group-id",
            sqlite_db_path=self.db_path,
        )

    def test_fetch_posts_returns_cleaned_payload(self) -> None:
        app.dependency_overrides.clear()
        from app.main import get_settings

        app.dependency_overrides[get_settings] = self.override_settings

        with patch("app.main.ZsxqScraper.fetch_posts") as mock_fetch_posts:
            mock_fetch_posts.return_value = {
                "group_id": "group-id",
                "count": 1,
                "has_more": False,
                "next_end_time": "2024-01-01T10:00:00.000+0800",
                "topics": [{"topic_id": 1, "text": "hello"}],
            }

            response = self.client.post("/api/v1/fetch_posts?count=1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["topics"][0]["topic_id"], 1)

    def test_fetch_all_posts_returns_paginated_payload(self) -> None:
        app.dependency_overrides.clear()
        from app.main import get_settings

        app.dependency_overrides[get_settings] = self.override_settings

        with patch("app.main.ZsxqScraper.fetch_all_posts") as mock_fetch_all_posts:
            mock_fetch_all_posts.return_value = {
                "group_id": "group-id",
                "count": 2,
                "page_size": 1,
                "pages_fetched": 2,
                "next_end_time": "2024-01-01T09:00:00.000+0800",
                "topics": [{"topic_id": 1}, {"topic_id": 2}],
            }

            response = self.client.post("/api/v1/fetch_all_posts?page_size=1&max_pages=2")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pages_fetched"], 2)
        self.assertEqual(len(response.json()["topics"]), 2)

    def test_fetch_posts_persist_true_saves_to_sqlite(self) -> None:
        app.dependency_overrides.clear()
        from app.main import get_settings

        app.dependency_overrides[get_settings] = self.override_settings

        with patch("app.main.ZsxqScraper.fetch_posts") as mock_fetch_posts:
            mock_fetch_posts.return_value = {
                "group_id": "group-id",
                "count": 1,
                "has_more": False,
                "next_end_time": None,
                "topics": [
                    {
                        "topic_id": 1,
                        "type": "talk",
                        "create_time": "2024-01-01T10:00:00.000+0800",
                        "create_time_iso": "2024-01-01T02:00:00+00:00",
                        "text": "hello",
                        "answer_text": "",
                        "owner": {"name": "alice"},
                        "like_count": 0,
                        "comment_count": 0,
                        "liked": False,
                    }
                ],
            }

            response = self.client.post("/api/v1/fetch_posts?count=1&persist=true")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["persisted"]["saved_count"], 1)

        store = SQLiteStore(self.db_path)
        topics = store.list_topics(limit=10, offset=0, group_id="group-id")
        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0]["topic_id"], 1)

    def test_list_topics_returns_saved_topics(self) -> None:
        app.dependency_overrides.clear()
        from app.main import get_settings

        app.dependency_overrides[get_settings] = self.override_settings
        SQLiteStore(self.db_path).upsert_topics(
            topics=[
                {
                    "topic_id": 2,
                    "type": "talk",
                    "create_time": "2024-01-01T10:00:00.000+0800",
                    "create_time_iso": "2024-01-01T02:00:00+00:00",
                    "text": "saved",
                    "answer_text": "",
                    "owner": {"name": "bob"},
                    "like_count": 0,
                    "comment_count": 0,
                    "liked": False,
                }
            ],
            group_id="group-id",
        )

        response = self.client.get("/api/v1/topics?limit=10&offset=0")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["topics"][0]["topic_id"], 2)


if __name__ == "__main__":
    unittest.main()
