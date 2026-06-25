"""Pydantic models for marketing News articles."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ArticleStatus(str, Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class ArticleSourceType(str, Enum):
    html = "html"
    pdf = "pdf"


class ArticleSummary(BaseModel):
    id: str
    slug: str
    title: str
    summary: str
    author: str
    publishedAt: Optional[datetime] = None
    updatedAt: Optional[datetime] = None
    status: ArticleStatus
    tags: List[str] = Field(default_factory=list)
    featuredImage: Optional[str] = None


class ArticleDetail(ArticleSummary):
    htmlPath: str
    sourceType: ArticleSourceType = ArticleSourceType.html
    createdBy: Optional[str] = None


class ArticleListResponse(BaseModel):
    articles: List[ArticleSummary]
    total: int
    page: int
    per_page: int
    pages: int


class ArticleCreateRequest(BaseModel):
    slug: str
    title: str
    summary: str
    author: str
    status: ArticleStatus = ArticleStatus.draft
    htmlBody: str
    publishedAt: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    featuredImage: Optional[str] = None
    sourceType: ArticleSourceType = ArticleSourceType.html


class ArticleUpdateRequest(BaseModel):
    slug: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    author: Optional[str] = None
    status: Optional[ArticleStatus] = None
    htmlBody: Optional[str] = None
    publishedAt: Optional[datetime] = None
    tags: Optional[List[str]] = None
    featuredImage: Optional[str] = None
    sourceType: Optional[ArticleSourceType] = None


class ArticleUploadPreviewResponse(BaseModel):
    htmlBody: str
    sourceType: ArticleSourceType


class AdminArticleDetail(ArticleDetail):
    htmlBody: Optional[str] = None
