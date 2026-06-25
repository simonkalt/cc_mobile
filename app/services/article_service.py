"""MongoDB-backed marketing News article service."""

from __future__ import annotations

import logging
import math
import os
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, status

from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.models.article import (
    ArticleCreateRequest,
    ArticleDetail,
    ArticleListResponse,
    ArticleSourceType,
    ArticleStatus,
    ArticleSummary,
    ArticleUpdateRequest,
)
from app.utils.article_html import wrap_article_html

logger = logging.getLogger(__name__)

DEFAULT_SEED_SLUG = "job-cover-letter-generator-ai"


def get_project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_articles_dir() -> str:
    configured = (getattr(settings, "ARTICLES_DIR", None) or "").strip()
    if configured:
        return configured
    return os.path.join(get_project_root(), "articles")


def get_articles_collection():
    if not is_connected():
        return None
    return get_collection(settings.MONGODB_ARTICLES_COLLECTION)


def ensure_article_indexes() -> None:
    coll = get_articles_collection()
    if coll is None:
        return
    try:
        coll.create_index("slug", unique=True)
        coll.create_index([("status", 1), ("publishedAt", -1)])
    except Exception as exc:
        logger.warning("Failed to ensure article indexes: %s", exc)


def _doc_to_summary(doc: dict) -> ArticleSummary:
    return ArticleSummary(
        id=str(doc["_id"]),
        slug=doc["slug"],
        title=doc["title"],
        summary=doc["summary"],
        author=doc["author"],
        publishedAt=doc.get("publishedAt"),
        updatedAt=doc.get("updatedAt"),
        status=ArticleStatus(doc.get("status", ArticleStatus.draft.value)),
        tags=doc.get("tags") or [],
        featuredImage=doc.get("featuredImage"),
    )


def _doc_to_detail(doc: dict) -> ArticleDetail:
    summary = _doc_to_summary(doc)
    return ArticleDetail(
        **summary.model_dump(),
        htmlPath=doc["htmlPath"],
        sourceType=ArticleSourceType(doc.get("sourceType", ArticleSourceType.html.value)),
        createdBy=doc.get("createdBy"),
    )


def _html_path_for_slug(slug: str) -> str:
    return f"articles/{slug}.html"


def _absolute_html_path(html_path: str) -> str:
    root = get_project_root()
    return os.path.join(root, html_path.replace("/", os.sep))


def write_article_html_file(
    *,
    slug: str,
    title: str,
    author: str,
    summary: str,
    body_html: str,
    published_at: Optional[datetime],
) -> str:
    articles_dir = get_articles_dir()
    os.makedirs(articles_dir, exist_ok=True)
    html_path = _html_path_for_slug(slug)
    abs_path = _absolute_html_path(html_path)
    content = wrap_article_html(
        title=title,
        author=author,
        body_html=body_html,
        published_at=published_at,
        summary=summary,
    )
    with open(abs_path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return html_path


def delete_article_html_file(html_path: str) -> None:
    abs_path = _absolute_html_path(html_path)
    if os.path.isfile(abs_path):
        os.remove(abs_path)


def read_article_body_html(html_path: str) -> Optional[str]:
    abs_path = _absolute_html_path(html_path)
    if not os.path.isfile(abs_path):
        return None
    with open(abs_path, encoding="utf-8") as fh:
        content = fh.read()
    from app.utils.article_html import extract_body_from_html

    return extract_body_from_html(content)


def list_articles(
    *,
    page: int = 1,
    per_page: int = 25,
    status: Optional[ArticleStatus] = None,
    sort: str = "publishedAt",
    order: str = "desc",
    include_all_statuses: bool = False,
) -> ArticleListResponse:
    coll = get_articles_collection()
    if coll is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")

    query: Dict[str, Any] = {}
    if status is not None:
        query["status"] = status.value
    elif not include_all_statuses:
        query["status"] = ArticleStatus.published.value

    sort_dir = -1 if order.lower() == "desc" else 1
    sort_field = sort if sort in {"publishedAt", "updatedAt", "title", "author"} else "publishedAt"

    total = coll.count_documents(query)
    pages = max(1, math.ceil(total / per_page)) if per_page else 1
    page = max(1, min(page, pages))
    skip = (page - 1) * per_page

    cursor = (
        coll.find(query)
        .sort(sort_field, sort_dir)
        .skip(skip)
        .limit(per_page)
    )
    articles = [_doc_to_summary(doc) for doc in cursor]
    return ArticleListResponse(
        articles=articles,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


def get_article_by_slug(slug: str, *, published_only: bool = True) -> ArticleDetail:
    coll = get_articles_collection()
    if coll is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")

    query: Dict[str, Any] = {"slug": slug}
    if published_only:
        query["status"] = ArticleStatus.published.value

    doc = coll.find_one(query)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return _doc_to_detail(doc)


def get_article_by_id(article_id: str) -> ArticleDetail:
    coll = get_articles_collection()
    if coll is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    try:
        oid = ObjectId(article_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid article id") from exc

    doc = coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")
    return _doc_to_detail(doc)


def _validate_slug_unique(coll, slug: str, exclude_id: Optional[ObjectId] = None) -> None:
    query: Dict[str, Any] = {"slug": slug}
    if exclude_id is not None:
        query["_id"] = {"$ne": exclude_id}
    if coll.find_one(query):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Slug already exists: {slug}")


def create_article(payload: ArticleCreateRequest, *, created_by: Optional[str] = None) -> ArticleDetail:
    coll = get_articles_collection()
    if coll is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")

    _validate_slug_unique(coll, payload.slug)
    now = datetime.now(UTC)
    published_at = payload.publishedAt
    if payload.status == ArticleStatus.published and published_at is None:
        published_at = now

    html_path = write_article_html_file(
        slug=payload.slug,
        title=payload.title,
        author=payload.author,
        summary=payload.summary,
        body_html=payload.htmlBody,
        published_at=published_at,
    )

    doc = {
        "slug": payload.slug,
        "title": payload.title,
        "summary": payload.summary,
        "author": payload.author,
        "publishedAt": published_at,
        "updatedAt": now,
        "status": payload.status.value,
        "htmlPath": html_path,
        "sourceType": payload.sourceType.value,
        "tags": payload.tags,
        "featuredImage": payload.featuredImage,
        "createdBy": created_by,
    }
    result = coll.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _doc_to_detail(doc)


def update_article(article_id: str, payload: ArticleUpdateRequest) -> ArticleDetail:
    coll = get_articles_collection()
    if coll is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")

    try:
        oid = ObjectId(article_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid article id") from exc

    doc = coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")

    updates: Dict[str, Any] = {}
    now = datetime.now(UTC)
    updates["updatedAt"] = now

    new_slug = payload.slug if payload.slug is not None else doc["slug"]
    if payload.slug is not None and payload.slug != doc["slug"]:
        _validate_slug_unique(coll, payload.slug, exclude_id=oid)

    title = payload.title if payload.title is not None else doc["title"]
    author = payload.author if payload.author is not None else doc["author"]
    summary = payload.summary if payload.summary is not None else doc["summary"]
    status_value = payload.status.value if payload.status is not None else doc["status"]
    published_at = payload.publishedAt if payload.publishedAt is not None else doc.get("publishedAt")
    tags = payload.tags if payload.tags is not None else doc.get("tags") or []
    featured = (
        payload.featuredImage if payload.featuredImage is not None else doc.get("featuredImage")
    )
    source_type = (
        payload.sourceType.value if payload.sourceType is not None else doc.get("sourceType", "html")
    )

    if status_value == ArticleStatus.published.value and published_at is None:
        published_at = now

    old_html_path = doc["htmlPath"]
    html_path = _html_path_for_slug(new_slug)

    body_html = payload.htmlBody
    if body_html is None:
        body_html = read_article_body_html(old_html_path) or ""

    write_article_html_file(
        slug=new_slug,
        title=title,
        author=author,
        summary=summary,
        body_html=body_html,
        published_at=published_at,
    )

    if html_path != old_html_path and os.path.isfile(_absolute_html_path(old_html_path)):
        delete_article_html_file(old_html_path)

    field_map = {
        "slug": new_slug,
        "title": title,
        "author": author,
        "summary": summary,
        "status": status_value,
        "publishedAt": published_at,
        "htmlPath": html_path,
        "tags": tags,
        "featuredImage": featured,
        "sourceType": source_type,
    }
    updates.update(field_map)

    coll.update_one({"_id": oid}, {"$set": updates})
    updated = coll.find_one({"_id": oid})
    return _doc_to_detail(updated)


def delete_article(article_id: str, *, hard_delete: bool = True) -> None:
    coll = get_articles_collection()
    if coll is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")

    try:
        oid = ObjectId(article_id)
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid article id") from exc

    doc = coll.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Article not found")

    if hard_delete:
        delete_article_html_file(doc["htmlPath"])
        coll.delete_one({"_id": oid})
    else:
        coll.update_one(
            {"_id": oid},
            {"$set": {"status": ArticleStatus.archived.value, "updatedAt": datetime.now(UTC)}},
        )


def list_published_for_rss(limit: int) -> List[ArticleDetail]:
    coll = get_articles_collection()
    if coll is None:
        return []
    cursor = (
        coll.find({"status": ArticleStatus.published.value})
        .sort("publishedAt", -1)
        .limit(limit)
    )
    return [_doc_to_detail(doc) for doc in cursor]


def get_article_html_absolute_path(html_path: str) -> str:
    return _absolute_html_path(html_path)


def seed_default_article_if_missing() -> None:
    """Upsert metadata for the bundled first article when HTML exists on disk."""
    coll = get_articles_collection()
    if coll is None:
        return
    html_path = _html_path_for_slug(DEFAULT_SEED_SLUG)
    if not os.path.isfile(_absolute_html_path(html_path)):
        return
    if coll.find_one({"slug": DEFAULT_SEED_SLUG}):
        return

    now = datetime.now(UTC)
    body = read_article_body_html(html_path) or ""
    coll.insert_one(
        {
            "slug": DEFAULT_SEED_SLUG,
            "title": "Job Cover Letter Generator - AI Brings Faster, Smarter Personalization to the Modern Job Search",
            "summary": (
                "Discover seven standout features of Job Cover Letter Generator - AI, "
                "including unlimited tones, five AI models, Word-style editing, and "
                "share-from-job-site automation."
            ),
            "author": "sAImon Software",
            "publishedAt": now,
            "updatedAt": now,
            "status": ArticleStatus.published.value,
            "htmlPath": html_path,
            "sourceType": ArticleSourceType.html.value,
            "tags": ["product", "cover-letter", "ai"],
            "featuredImage": None,
            "createdBy": None,
        }
    )
    logger.info("Seeded default News article: %s", DEFAULT_SEED_SLUG)
