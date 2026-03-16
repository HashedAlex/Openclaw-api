from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
import re
from typing import Any

import requests


class ZsxqScraper:
    def __init__(self, access_token: str, group_id: str) -> None:
        self.access_token = access_token
        self.group_id = group_id
        self.base_url = "https://api.zsxq.com/v2"

    def fetch_posts(
        self,
        count: int = 20,
        end_time: str | None = None,
        scope: str = "all",
    ) -> dict[str, Any]:
        params = {
            "scope": scope,
            "count": max(1, min(count, 100)),
        }
        if end_time:
            params["end_time"] = end_time

        response = requests.get(
            f"{self.base_url}/groups/{self.group_id}/topics",
            headers=self._build_headers(),
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()

        return self.clean_topics_response(payload, requested_count=params["count"])

    def fetch_all_posts(
        self,
        page_size: int = 20,
        scope: str = "all",
        max_pages: int = 10,
    ) -> dict[str, Any]:
        all_topics: list[dict[str, Any]] = []
        seen_topic_ids: set[Any] = set()
        next_end_time: str | None = None
        previous_end_time: str | None = None
        fetched_pages = 0
        requested_page_size = max(1, min(page_size, 100))

        for _ in range(max(1, max_pages)):
            page = self.fetch_posts(
                count=requested_page_size,
                end_time=next_end_time,
                scope=scope,
            )
            fetched_pages += 1
            topics = page.get("topics") or []

            for topic in topics:
                topic_id = topic.get("topic_id")
                dedupe_key = topic_id if topic_id is not None else (
                    topic.get("create_time"),
                    topic.get("text"),
                )
                if dedupe_key in seen_topic_ids:
                    continue
                seen_topic_ids.add(dedupe_key)
                all_topics.append(topic)

            next_end_time = page.get("next_end_time")
            if (
                not page.get("has_more")
                or not topics
                or not next_end_time
                or next_end_time == previous_end_time
            ):
                break
            previous_end_time = next_end_time

        return {
            "group_id": self.group_id,
            "count": len(all_topics),
            "page_size": requested_page_size,
            "pages_fetched": fetched_pages,
            "next_end_time": next_end_time,
            "topics": all_topics,
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "Cookie": f"zsxq_access_token={self.access_token}",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://wx.zsxq.com/",
        }

    def clean_topics_response(
        self,
        payload: dict[str, Any],
        requested_count: int | None = None,
    ) -> dict[str, Any]:
        resp_data = payload.get("resp_data") or {}
        topics = resp_data.get("topics") or []

        cleaned_topics = [self._normalize_topic(topic) for topic in topics]
        end_time = cleaned_topics[-1]["create_time"] if cleaned_topics else None
        has_more = resp_data.get("has_more")
        if has_more is None:
            has_more = bool(requested_count and len(cleaned_topics) >= requested_count)

        return {
            "group_id": self.group_id,
            "count": len(cleaned_topics),
            "has_more": has_more,
            "next_end_time": end_time,
            "topics": cleaned_topics,
        }

    def _normalize_topic(self, topic: dict[str, Any]) -> dict[str, Any]:
        talk = topic.get("talk") or {}
        question = topic.get("question") or {}
        answer = question.get("answer") or {}

        images = talk.get("images") or topic.get("images") or []
        files = topic.get("files") or talk.get("files") or []

        owner = topic.get("owner") or {}
        user_specific = topic.get("user_specific") or {}

        return {
            "topic_id": topic.get("topic_id"),
            "type": topic.get("type"),
            "create_time": topic.get("create_time"),
            "create_time_iso": self._to_iso8601(topic.get("create_time")),
            "text": self._clean_text(talk.get("text") or question.get("text") or ""),
            "answer_text": self._clean_text(answer.get("text") or ""),
            "images": [self._normalize_image(item) for item in images],
            "files": [self._normalize_file(item) for item in files],
            "owner": {
                "user_id": owner.get("user_id"),
                "name": owner.get("name"),
                "avatar_url": owner.get("avatar_url"),
                "location": owner.get("location"),
            },
            "question": {
                "owner": self._normalize_user(question.get("owner")),
                "text": self._clean_text(question.get("text") or ""),
                "images": [self._normalize_image(item) for item in question.get("images") or []],
            }
            if question
            else None,
            "answer": {
                "owner": self._normalize_user(answer.get("owner")),
                "text": self._clean_text(answer.get("text") or ""),
                "images": [self._normalize_image(item) for item in answer.get("images") or []],
            }
            if answer
            else None,
            "like_count": topic.get("likes_count", 0),
            "comment_count": topic.get("comments_count", 0),
            "liked": bool(user_specific.get("liked")),
            "comments": [self._normalize_comment(item) for item in topic.get("show_comments") or []],
            "raw": {
                "group": topic.get("group"),
                "digested": topic.get("digested"),
                "sticky": topic.get("sticky"),
            },
        }

    def _normalize_comment(self, comment: dict[str, Any]) -> dict[str, Any]:
        return {
            "comment_id": comment.get("comment_id"),
            "create_time": comment.get("create_time"),
            "create_time_iso": self._to_iso8601(comment.get("create_time")),
            "text": self._clean_text(comment.get("text") or ""),
            "owner": self._normalize_user(comment.get("owner")),
            "replied_comment_id": comment.get("replied_comment_id"),
        }

    def _normalize_image(self, image: dict[str, Any]) -> dict[str, Any]:
        large = image.get("large") or {}
        original = image.get("original") or {}
        thumbnail = image.get("thumbnail") or {}
        return {
            "image_id": image.get("image_id"),
            "type": image.get("type"),
            "large": large.get("url"),
            "original": original.get("url"),
            "thumbnail": thumbnail.get("url"),
            "width": large.get("width") or original.get("width"),
            "height": large.get("height") or original.get("height"),
        }

    def _normalize_file(self, file_item: dict[str, Any]) -> dict[str, Any]:
        return {
            "file_id": file_item.get("file_id"),
            "name": file_item.get("name"),
            "hash": file_item.get("hash"),
            "size": file_item.get("size"),
            "download_url": file_item.get("download_url"),
        }

    def _normalize_user(self, user: dict[str, Any] | None) -> dict[str, Any] | None:
        if not user:
            return None
        return {
            "user_id": user.get("user_id"),
            "name": user.get("name"),
            "avatar_url": user.get("avatar_url"),
            "location": user.get("location"),
        }

    def _clean_text(self, value: str) -> str:
        text = unescape(value)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _to_iso8601(self, value: str | None) -> str | None:
        if not value:
            return None

        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized).astimezone(timezone.utc).isoformat()
        except ValueError:
            return value
