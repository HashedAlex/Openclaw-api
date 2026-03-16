from fastapi import Depends, FastAPI, HTTPException, Query
import requests

from app.config import Settings, get_settings
from app.services.sqlite_store import SQLiteStore
from app.services.zsxq_scraper import ZsxqScraper

app = FastAPI(
    title="OpenClaw ZSXQ Tool API",
    version="0.1.0",
    description="A lightweight local API service for fetching and cleaning ZSXQ data.",
)


def _extract_error_detail(response: requests.Response | None) -> str:
    if response is None:
        return "Failed to fetch ZSXQ topics"

    try:
        payload = response.json()
    except ValueError:
        return response.text or "Failed to fetch ZSXQ topics"

    if isinstance(payload, dict):
        error = payload.get("error") or {}
        if isinstance(error, dict):
            for key in ("message", "msg", "detail"):
                value = error.get(key)
                if value:
                    return str(value)

        for key in ("message", "msg", "detail"):
            value = payload.get(key)
            if value:
                return str(value)

    return response.text or "Failed to fetch ZSXQ topics"


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "openclaw-zsxq-api",
    }


@app.post("/api/v1/fetch_posts")
def fetch_posts(
    count: int = Query(default=20, ge=1, le=100),
    end_time: str | None = Query(default=None),
    scope: str = Query(default="all"),
    persist: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")
    if not settings.group_id:
        raise HTTPException(status_code=400, detail="Missing GROUP_ID")

    scraper = ZsxqScraper(
        access_token=settings.zsxq_access_token,
        group_id=settings.group_id,
    )
    store = SQLiteStore(settings.sqlite_db_path)

    try:
        result = scraper.fetch_posts(count=count, end_time=end_time, scope=scope)
        if persist:
            saved = store.upsert_topics(result["topics"], settings.group_id)
            result["persisted"] = {
                "enabled": True,
                "saved_count": saved,
                "db_path": settings.sqlite_db_path,
            }
        return result
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.post("/api/v1/fetch_all_posts")
def fetch_all_posts(
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="all"),
    max_pages: int = Query(default=10, ge=1, le=100),
    persist: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")
    if not settings.group_id:
        raise HTTPException(status_code=400, detail="Missing GROUP_ID")

    scraper = ZsxqScraper(
        access_token=settings.zsxq_access_token,
        group_id=settings.group_id,
    )
    store = SQLiteStore(settings.sqlite_db_path)

    try:
        result = scraper.fetch_all_posts(
            page_size=page_size,
            scope=scope,
            max_pages=max_pages,
        )
        if persist:
            saved = store.upsert_topics(result["topics"], settings.group_id)
            result["persisted"] = {
                "enabled": True,
                "saved_count": saved,
                "db_path": settings.sqlite_db_path,
            }
        return result
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.get("/api/v1/topics")
def list_topics(
    limit: int = Query(default=20, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> dict:
    store = SQLiteStore(settings.sqlite_db_path)
    topics = store.list_topics(limit=limit, offset=offset, group_id=settings.group_id or None)
    return {
        "count": len(topics),
        "limit": limit,
        "offset": offset,
        "db_path": settings.sqlite_db_path,
        "topics": topics,
    }
