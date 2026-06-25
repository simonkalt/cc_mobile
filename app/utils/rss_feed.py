"""RSS 2.0 feed generation for marketing News articles."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from email.utils import format_datetime
from typing import Iterable, Optional

from app.models.article import ArticleDetail
from app.services.article_service import read_article_body_html


def _format_pub_date(value: Optional[datetime]) -> str:
    if value is None:
        value = datetime.now(UTC)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return format_datetime(value, usegmt=True)


def build_rss_xml(
    articles: Iterable[ArticleDetail],
    *,
    base_url: str,
    channel_title: str = "sAImon Software News",
    channel_description: str = (
        "Product news and updates from sAImon Software, including Career Helper: "
        "AI Job Cover Letter Generator."
    ),
    include_full_content: bool = True,
) -> bytes:
    base = base_url.rstrip("/")
    channel_link = f"{base}/news"

    rss = ET.Element("rss", {"version": "2.0"})
    rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")

    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = channel_title
    ET.SubElement(channel, "link").text = channel_link
    ET.SubElement(channel, "description").text = channel_description
    ET.SubElement(channel, "language").text = "en-us"

    article_list = list(articles)
    if article_list:
        latest = article_list[0].publishedAt or article_list[0].updatedAt
        if latest:
            ET.SubElement(channel, "lastBuildDate").text = _format_pub_date(latest)

    for article in article_list:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = article.title
        link = f"{base}/news/{article.slug}"
        ET.SubElement(item, "link").text = link
        ET.SubElement(item, "description").text = article.summary
        ET.SubElement(item, "pubDate").text = _format_pub_date(article.publishedAt)
        guid = ET.SubElement(item, "guid", {"isPermaLink": "true"})
        guid.text = link
        if article.author:
            ET.SubElement(item, "author").text = article.author
        for tag in article.tags or []:
            ET.SubElement(item, "category").text = tag

        if include_full_content:
            body = read_article_body_html(article.htmlPath)
            if body:
                encoded = ET.SubElement(
                    item,
                    "{http://purl.org/rss/1.0/modules/content/}encoded",
                )
                encoded.text = body

    xml_bytes = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    return xml_bytes
