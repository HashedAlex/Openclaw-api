---
name: zsxq-fetch
description: Use this skill when the user wants OpenClaw to sync subscribed Zhishi Xingqiu groups, inspect recent content, search downloaded documents, summarize updates, or answer questions grounded in the local OpenClaw ZSXQ API database.
---

# ZSXQ Fetch

Use this skill to operate the local OpenClaw ZSXQ API as a data source for sync, summarization, and grounded Q&A.

## When to use

- The user wants the latest subscribed ZSXQ group content synced into SQLite.
- The user wants summaries of recent ZSXQ posts by time window or by group.
- The user asks questions that should be answered from synced ZSXQ posts or downloaded documents.
- The user wants to inspect downloaded attachments or search document text.

## Preconditions

- The API project is available locally.
- Environment variables are configured for the API:
  - `ZSXQ_ACCESS_TOKEN`
  - `GROUP_ID` for a default group, optional once using multi-group endpoints
  - `SQLITE_DB_PATH`
  - `DOCS_STORAGE_PATH`
- The API server is running. Check with:

```bash
curl http://127.0.0.1:8000/health
```

If it is not running, start it from the project root:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Core workflow

1. Sync before answering time-sensitive requests.
2. Pull only the smallest relevant slice of data.
3. Prefer grounded answers from `/api/v1/topics`, `/api/v1/documents`, and `/api/v1/search_documents`.
4. Summarize with explicit scope: group, time range, or topic.

## Useful endpoints

- Sync all subscribed groups:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/sync_all_groups_posts"
```

- Sync one group:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/sync_group_posts?group_id=GROUP_ID"
```

- List groups:

```bash
curl "http://127.0.0.1:8000/api/v1/groups/all"
```

- Read recent topics:

```bash
curl "http://127.0.0.1:8000/api/v1/topics?group_id=GROUP_ID&limit=50&offset=0"
```

- List downloaded documents:

```bash
curl "http://127.0.0.1:8000/api/v1/documents?group_id=GROUP_ID&limit=50"
```

- Search document text:

```bash
curl "http://127.0.0.1:8000/api/v1/search_documents?q=KEYWORD&group_id=GROUP_ID"
```

## Summarization pattern

- Sync first if the user asks for latest updates.
- Pull recent topics for the requested group or across relevant groups.
- If documents may contain the answer, search them with keywords from the user question.
- Build the answer from retrieved records only. State when the answer is inferred from partial evidence.

## Output guidance

- For update summaries, group findings by topic or theme, not by raw post order.
- For question answering, cite the specific topic text or document match preview used.
- If the database has no relevant records, say so and recommend a sync.
