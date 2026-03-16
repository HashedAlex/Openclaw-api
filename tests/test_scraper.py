import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from app.services.sqlite_store import SQLiteStore
from app.services.zsxq_scraper import ZsxqScraper


class ZsxqScraperTests(unittest.TestCase):
    def test_clean_topics_response_strips_html_and_normalizes_fields(self) -> None:
        scraper = ZsxqScraper("token", "group")
        payload = {
            "resp_data": {
                "topics": [
                    {
                        "topic_id": 1,
                        "type": "talk",
                        "create_time": "2024-01-01T10:00:00.000+0800",
                        "talk": {
                            "text": "hello&lt;br&gt;<b>world</b>",
                            "images": [
                                {
                                    "image_id": 2,
                                    "type": "jpg",
                                    "large": {"url": "L", "width": 100, "height": 80},
                                }
                            ],
                        },
                        "owner": {"user_id": 9, "name": "alice"},
                        "show_comments": [
                            {
                                "comment_id": 3,
                                "create_time": "2024-01-01T11:00:00.000+0800",
                                "text": "ok<br/>fine",
                                "owner": {"user_id": 10, "name": "bob"},
                            }
                        ],
                    }
                ]
            }
        }

        cleaned = scraper.clean_topics_response(payload, requested_count=20)

        self.assertEqual(cleaned["count"], 1)
        self.assertFalse(cleaned["has_more"])
        self.assertEqual(cleaned["topics"][0]["text"], "hello\nworld")
        self.assertEqual(cleaned["topics"][0]["comments"][0]["text"], "ok\nfine")
        self.assertEqual(cleaned["topics"][0]["images"][0]["large"], "L")

    def test_fetch_all_posts_paginates_until_has_more_is_false(self) -> None:
        scraper = ZsxqScraper("token", "group")
        pages = [
            {
                "group_id": "group",
                "count": 1,
                "has_more": True,
                "next_end_time": "2024-01-01T10:00:00.000+0800",
                "topics": [{"topic_id": 1}],
            },
            {
                "group_id": "group",
                "count": 1,
                "has_more": False,
                "next_end_time": "2024-01-01T09:00:00.000+0800",
                "topics": [{"topic_id": 2}],
            },
        ]

        with patch.object(scraper, "fetch_posts", side_effect=pages) as mock_fetch_posts:
            result = scraper.fetch_all_posts(page_size=1, max_pages=5)

        self.assertEqual(result["count"], 2)
        self.assertEqual(result["pages_fetched"], 2)
        self.assertEqual([item["topic_id"] for item in result["topics"]], [1, 2])
        self.assertEqual(mock_fetch_posts.call_count, 2)

    def test_fetch_all_posts_deduplicates_topics_across_pages(self) -> None:
        scraper = ZsxqScraper("token", "group")
        pages = [
            {
                "group_id": "group",
                "count": 2,
                "has_more": True,
                "next_end_time": "2024-01-01T10:00:00.000+0800",
                "topics": [{"topic_id": 1}, {"topic_id": 2}],
            },
            {
                "group_id": "group",
                "count": 2,
                "has_more": False,
                "next_end_time": "2024-01-01T09:00:00.000+0800",
                "topics": [{"topic_id": 2}, {"topic_id": 3}],
            },
        ]

        with patch.object(scraper, "fetch_posts", side_effect=pages):
            result = scraper.fetch_all_posts(page_size=2, max_pages=5)

        self.assertEqual([item["topic_id"] for item in result["topics"]], [1, 2, 3])
        self.assertEqual(result["count"], 3)


class SQLiteStoreTests(unittest.TestCase):
    def test_upsert_topics_updates_existing_topic(self) -> None:
        with TemporaryDirectory() as temp_dir:
            store = SQLiteStore(f"{temp_dir}/openclaw.db")
            store.upsert_topics(
                [
                    {
                        "topic_id": 1,
                        "type": "talk",
                        "create_time": "2024-01-01T10:00:00.000+0800",
                        "create_time_iso": "2024-01-01T02:00:00+00:00",
                        "text": "v1",
                        "answer_text": "",
                        "owner": {"name": "alice"},
                        "like_count": 1,
                        "comment_count": 0,
                        "liked": False,
                    }
                ],
                group_id="group-1",
            )
            store.upsert_topics(
                [
                    {
                        "topic_id": 1,
                        "type": "talk",
                        "create_time": "2024-01-01T10:00:00.000+0800",
                        "create_time_iso": "2024-01-01T02:00:00+00:00",
                        "text": "v2",
                        "answer_text": "",
                        "owner": {"name": "alice"},
                        "like_count": 5,
                        "comment_count": 2,
                        "liked": True,
                    }
                ],
                group_id="group-1",
            )

            topics = store.list_topics(limit=10, offset=0, group_id="group-1")

        self.assertEqual(len(topics), 1)
        self.assertEqual(topics[0]["text"], "v2")
        self.assertEqual(topics[0]["like_count"], 5)


if __name__ == "__main__":
    unittest.main()
