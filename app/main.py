from fastapi import Depends, FastAPI, HTTPException, Query
import requests

from app.config import Settings, get_settings
from app.services.document_ingestor import DocumentIngestor
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
    group_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")
    resolved_group_id = group_id or settings.group_id
    if not resolved_group_id:
        raise HTTPException(status_code=400, detail="Missing GROUP_ID")

    scraper = ZsxqScraper(
        access_token=settings.zsxq_access_token,
        group_id=resolved_group_id,
    )
    store = SQLiteStore(settings.sqlite_db_path)

    try:
        result = scraper.fetch_posts(count=count, end_time=end_time, scope=scope)
        if persist:
            kept_topics, filtered_topics = scraper.filter_promotional_topics(result["topics"])
            saved = store.upsert_topics(kept_topics, resolved_group_id)
            ingestor = DocumentIngestor(settings.docs_storage_path, scraper._build_headers())
            documents = []
            for topic in kept_topics:
                documents.extend(ingestor.ingest_topic_documents(resolved_group_id, topic))
            documents_saved = store.upsert_documents(documents) if documents else 0
            result["persisted"] = {
                "enabled": True,
                "saved_count": saved,
                "filtered_topics_count": len(filtered_topics),
                "documents_saved_count": documents_saved,
                "db_path": settings.sqlite_db_path,
                "docs_storage_path": settings.docs_storage_path,
            }
        return result
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.post("/api/v1/fetch_all_posts")
def fetch_all_posts(
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="all"),
    max_pages: int = Query(default=10, ge=1, le=100),
    persist: bool = Query(default=False),
    group_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")
    resolved_group_id = group_id or settings.group_id
    if not resolved_group_id:
        raise HTTPException(status_code=400, detail="Missing GROUP_ID")

    scraper = ZsxqScraper(
        access_token=settings.zsxq_access_token,
        group_id=resolved_group_id,
    )
    store = SQLiteStore(settings.sqlite_db_path)

    try:
        result = scraper.fetch_all_posts(
            page_size=page_size,
            scope=scope,
            max_pages=max_pages,
        )
        if persist:
            kept_topics, filtered_topics = scraper.filter_promotional_topics(result["topics"])
            saved = store.upsert_topics(kept_topics, resolved_group_id)
            ingestor = DocumentIngestor(settings.docs_storage_path, scraper._build_headers())
            documents = []
            for topic in kept_topics:
                documents.extend(ingestor.ingest_topic_documents(resolved_group_id, topic))
            documents_saved = store.upsert_documents(documents) if documents else 0
            result["persisted"] = {
                "enabled": True,
                "saved_count": saved,
                "filtered_topics_count": len(filtered_topics),
                "documents_saved_count": documents_saved,
                "db_path": settings.sqlite_db_path,
                "docs_storage_path": settings.docs_storage_path,
            }
        return result
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.get("/api/v1/groups")
def list_groups(
    count: int = Query(default=20, ge=1, le=100),
    end_time: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")

    scraper = ZsxqScraper(access_token=settings.zsxq_access_token)

    try:
        return scraper.list_groups(count=count, end_time=end_time)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.get("/api/v1/groups/all")
def list_all_groups(
    page_size: int = Query(default=20, ge=1, le=100),
    max_pages: int = Query(default=10, ge=1, le=100),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")

    scraper = ZsxqScraper(access_token=settings.zsxq_access_token)

    try:
        return scraper.fetch_all_groups(page_size=page_size, max_pages=max_pages)
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.post("/api/v1/sync_group_posts")
def sync_group_posts(
    page_size: int = Query(default=20, ge=1, le=100),
    scope: str = Query(default="all"),
    max_pages: int = Query(default=10, ge=1, le=100),
    group_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")
    resolved_group_id = group_id or settings.group_id
    if not resolved_group_id:
        raise HTTPException(status_code=400, detail="Missing GROUP_ID")

    scraper = ZsxqScraper(
        access_token=settings.zsxq_access_token,
        group_id=resolved_group_id,
    )
    store = SQLiteStore(settings.sqlite_db_path)

    try:
        result = scraper.sync_group_posts(
            store=store,
            docs_storage_path=settings.docs_storage_path,
            page_size=page_size,
            scope=scope,
            max_pages=max_pages,
        )
        result["db_path"] = settings.sqlite_db_path
        result["docs_storage_path"] = settings.docs_storage_path
        return result
    except requests.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else 502
        detail = _extract_error_detail(exc.response)
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Network error: {exc}") from exc


@app.post("/api/v1/sync_all_groups_posts")
def sync_all_groups_posts(
    group_page_size: int = Query(default=20, ge=1, le=100),
    max_group_pages: int = Query(default=10, ge=1, le=100),
    topic_page_size: int = Query(default=20, ge=1, le=100),
    topic_max_pages: int = Query(default=10, ge=1, le=100),
    scope: str = Query(default="all"),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.zsxq_access_token:
        raise HTTPException(status_code=400, detail="Missing ZSXQ_ACCESS_TOKEN")

    scraper = ZsxqScraper(access_token=settings.zsxq_access_token)
    store = SQLiteStore(settings.sqlite_db_path)

    try:
        result = scraper.sync_all_groups_posts(
            store=store,
            docs_storage_path=settings.docs_storage_path,
            group_page_size=group_page_size,
            max_group_pages=max_group_pages,
            topic_page_size=topic_page_size,
            topic_max_pages=topic_max_pages,
            scope=scope,
        )
        result["db_path"] = settings.sqlite_db_path
        result["docs_storage_path"] = settings.docs_storage_path
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
    group_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    store = SQLiteStore(settings.sqlite_db_path)
    topics = store.list_topics(limit=limit, offset=offset, group_id=group_id or settings.group_id or None)
    return {
        "count": len(topics),
        "limit": limit,
        "offset": offset,
        "group_id": group_id or settings.group_id or None,
        "db_path": settings.sqlite_db_path,
        "topics": topics,
    }


@app.get("/api/v1/documents")
def list_documents(
    limit: int = Query(default=20, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    group_id: str | None = Query(default=None),
    topic_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    store = SQLiteStore(settings.sqlite_db_path)
    documents = store.list_documents(limit=limit, offset=offset, group_id=group_id, topic_id=topic_id)
    return {
        "count": len(documents),
        "limit": limit,
        "offset": offset,
        "group_id": group_id,
        "topic_id": topic_id,
        "db_path": settings.sqlite_db_path,
        "docs_storage_path": settings.docs_storage_path,
        "documents": documents,
    }


@app.get("/api/v1/search_documents")
def search_documents(
    q: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    group_id: str | None = Query(default=None),
    settings: Settings = Depends(get_settings),
) -> dict:
    store = SQLiteStore(settings.sqlite_db_path)
    documents = store.search_documents(
        query_text=q,
        limit=limit,
        offset=offset,
        group_id=group_id,
    )
    return {
        "count": len(documents),
        "query": q,
        "limit": limit,
        "offset": offset,
        "group_id": group_id,
        "db_path": settings.sqlite_db_path,
        "docs_storage_path": settings.docs_storage_path,
        "documents": documents,
    }
