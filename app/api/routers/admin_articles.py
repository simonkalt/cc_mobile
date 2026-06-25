"""Admin News article management routes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.auth import get_current_admin_user
from app.models.article import (
    AdminArticleDetail,
    ArticleCreateRequest,
    ArticleDetail,
    ArticleListResponse,
    ArticleSourceType,
    ArticleUpdateRequest,
    ArticleUploadPreviewResponse,
)
from app.services.article_service import (
    create_article,
    delete_article,
    get_article_by_id,
    list_articles,
    read_article_body_html,
    update_article,
)
from app.utils.article_html import (
    extract_body_from_html,
    pdf_bytes_to_html_body,
    plain_text_to_html_body,
)

router = APIRouter(prefix="/api/admin/articles", tags=["admin-articles"])


@router.get("", response_model=ArticleListResponse)
def admin_list_articles(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort: str = Query("publishedAt"),
    order: str = Query("desc"),
    status: Optional[str] = Query(None),
    _admin: dict = Depends(get_current_admin_user),
):
    status_filter = None
    if status:
        try:
            from app.models.article import ArticleStatus

            status_filter = ArticleStatus(status)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid status") from exc

    return list_articles(
        page=page,
        per_page=per_page,
        sort=sort,
        order=order,
        status=status_filter,
        include_all_statuses=status_filter is None,
    )


@router.get("/{article_id}", response_model=AdminArticleDetail)
def admin_get_article(
    article_id: str,
    _admin: dict = Depends(get_current_admin_user),
):
    detail = get_article_by_id(article_id)
    body = read_article_body_html(detail.htmlPath)
    return AdminArticleDetail(**detail.model_dump(), htmlBody=body)


@router.post("", response_model=ArticleDetail, status_code=status.HTTP_201_CREATED)
def admin_create_article(
    payload: ArticleCreateRequest,
    admin: dict = Depends(get_current_admin_user),
):
    return create_article(payload, created_by=admin.get("sub"))


@router.put("/{article_id}", response_model=ArticleDetail)
def admin_update_article(
    article_id: str,
    payload: ArticleUpdateRequest,
    _admin: dict = Depends(get_current_admin_user),
):
    return update_article(article_id, payload)


@router.delete("/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_article(
    article_id: str,
    hard: bool = Query(True),
    _admin: dict = Depends(get_current_admin_user),
):
    delete_article(article_id, hard_delete=hard)
    return None


@router.post("/upload-pdf", response_model=ArticleUploadPreviewResponse)
async def admin_upload_pdf_preview(
    file: UploadFile = File(...),
    _admin: dict = Depends(get_current_admin_user),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only PDF files are supported")
    data = await file.read()
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid PDF file")
    html_body = pdf_bytes_to_html_body(data)
    return ArticleUploadPreviewResponse(htmlBody=html_body, sourceType=ArticleSourceType.pdf)


@router.post("/upload-html", response_model=ArticleUploadPreviewResponse)
async def admin_upload_html_preview(
    file: UploadFile = File(...),
    _admin: dict = Depends(get_current_admin_user),
):
    if not file.filename or not file.filename.lower().endswith((".html", ".htm")):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only HTML files are supported")
    raw = (await file.read()).decode("utf-8", errors="replace")
    html_body = extract_body_from_html(raw)
    if not html_body.strip():
        html_body = plain_text_to_html_body(raw)
    return ArticleUploadPreviewResponse(htmlBody=html_body, sourceType=ArticleSourceType.html)
