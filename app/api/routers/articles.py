"""Public News article API routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Response

from app.core.config import settings
from app.models.article import ArticleDetail, ArticleListResponse, ArticleStatus
from app.services.article_service import (
    ensure_article_indexes,
    get_article_by_slug,
    list_articles,
    list_published_for_rss,
    seed_default_article_if_missing,
)
from app.utils.rss_feed import build_rss_xml

router = APIRouter(tags=["articles"])

_indexes_ready = False


def _ensure_articles_ready() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    ensure_article_indexes()
    seed_default_article_if_missing()
    _indexes_ready = True


def _articles_public_base_url() -> str:
    configured = (getattr(settings, "PUBLIC_WEBSITE_URL", None) or "").strip()
    if configured:
        return configured.rstrip("/")
    return "https://www.saimonsoft.com"


@router.get("/api/articles", response_model=ArticleListResponse)
def get_published_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort: str = Query("publishedAt"),
    order: str = Query("desc"),
):
    _ensure_articles_ready()
    return list_articles(
        page=page,
        per_page=per_page,
        status=ArticleStatus.published,
        sort=sort,
        order=order,
        include_all_statuses=False,
    )


@router.get("/api/articles/{slug}", response_model=ArticleDetail)
def get_published_article(slug: str):
    _ensure_articles_ready()
    return get_article_by_slug(slug, published_only=True)


@router.get("/news/rss.xml", include_in_schema=False)
def news_rss_feed():
    _ensure_articles_ready()
    limit = getattr(settings, "NEWS_RSS_MAX_ITEMS", 50)
    articles = list_published_for_rss(limit)
    xml_bytes = build_rss_xml(articles, base_url=_articles_public_base_url())
    return Response(
        content=xml_bytes,
        media_type="application/rss+xml; charset=utf-8",
        headers={"Cache-Control": "public, max-age=300"},
    )
