"""Tests for marketing News articles API, RSS feed, and admin CRUD."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from bson import ObjectId
from fastapi.testclient import TestClient


def _sample_article_doc(
    *,
    slug: str = "sample-article",
    status: str = "published",
    title: str = "Sample Article",
):
    now = datetime.now(UTC)
    return {
        "_id": ObjectId(),
        "slug": slug,
        "title": title,
        "summary": "Sample summary",
        "author": "Test Author",
        "publishedAt": now,
        "updatedAt": now,
        "status": status,
        "htmlPath": f"articles/{slug}.html",
        "sourceType": "html",
        "tags": ["news"],
        "featuredImage": None,
        "createdBy": None,
    }


class TestArticlesFeature(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from main import app

        cls.client = TestClient(app)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        articles_dir = os.path.join(self.temp_dir.name, "articles")
        os.makedirs(articles_dir, exist_ok=True)
        html_path = os.path.join(articles_dir, "sample-article.html")
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(
                '<html><body><div class="news-article-body"><p>Hello world</p></div></body></html>'
            )

        self.doc_published = _sample_article_doc()
        self.doc_draft = _sample_article_doc(
            slug="draft-article", status="draft", title="Draft Article"
        )

        self.mock_coll = MagicMock()

        def _find_one(query):
            if query.get("slug") == "sample-article" and query.get("status") == "published":
                return self.doc_published
            if query.get("slug") == "sample-article":
                return self.doc_published
            if query.get("_id") == self.doc_published["_id"]:
                return self.doc_published
            if query.get("slug") == "draft-article":
                return self.doc_draft
            return None

        self.mock_coll.find_one.side_effect = _find_one

        published_cursor = MagicMock()
        published_cursor.sort.return_value = published_cursor
        published_cursor.skip.return_value = published_cursor
        published_cursor.limit.return_value = [self.doc_published]

        rss_cursor = MagicMock()
        rss_cursor.sort.return_value = rss_cursor
        rss_cursor.limit.return_value = [self.doc_published]

        def _find(query):
            cursor = MagicMock()
            if query.get("status") == "published":
                cursor.sort.return_value = cursor
                cursor.skip.return_value = cursor
                cursor.limit.return_value = [self.doc_published]
                return cursor
            cursor.sort.return_value = cursor
            cursor.skip.return_value = cursor
            cursor.limit.return_value = [self.doc_published, self.doc_draft]
            return cursor

        self.mock_coll.find.side_effect = _find

        def _count_documents(query):
            if query.get("status") == "published":
                return 1
            return 2

        self.mock_coll.count_documents.side_effect = _count_documents

        patcher_connected = patch("app.services.article_service.is_connected", return_value=True)
        patcher_connected.start()
        self.addCleanup(patcher_connected.stop)

        patcher_coll = patch(
            "app.services.article_service.get_articles_collection",
            return_value=self.mock_coll,
        )
        patcher_coll.start()
        self.addCleanup(patcher_coll.stop)

        patcher_dir = patch(
            "app.services.article_service.get_articles_dir",
            return_value=articles_dir,
        )
        patcher_dir.start()
        self.addCleanup(patcher_dir.stop)

        patcher_root = patch(
            "app.services.article_service.get_project_root",
            return_value=self.temp_dir.name,
        )
        patcher_root.start()
        self.addCleanup(patcher_root.stop)

        import app.api.routers.articles as articles_router

        articles_router._indexes_ready = True

    def test_public_list_returns_published_articles(self):
        resp = self.client.get("/api/articles")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["articles"]), 1)
        self.assertEqual(data["articles"][0]["slug"], "sample-article")

    def test_public_get_article_by_slug(self):
        resp = self.client.get("/api/articles/sample-article")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Sample Article")

    def test_news_page_served(self):
        resp = self.client.get("/news")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.headers.get("content-type", ""))
        self.assertIn("News", resp.text)

    def test_rss_feed_xml(self):
        resp = self.client.get("/news/rss.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/rss+xml", resp.headers.get("content-type", ""))
        self.assertIn("<rss", resp.text)
        self.assertIn("Sample Article", resp.text)
        self.assertIn("/news/sample-article", resp.text)
        self.assertIn("Sample summary", resp.text)

    def test_rss_respects_max_items(self):
        with patch("app.core.config.settings.NEWS_RSS_MAX_ITEMS", 1):
            resp = self.client.get("/news/rss.xml")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.text.count("<item>"), 1)

    def test_slugify_helper(self):
        from app.utils.article_html import slug_from_title

        self.assertEqual(
            slug_from_title("Job Cover Letter Generator - AI"),
            "job-cover-letter-generator-ai",
        )

    def test_wrap_article_html_contains_body(self):
        from app.utils.article_html import wrap_article_html

        html = wrap_article_html(
            title="Title",
            author="Author",
            body_html="<p>Body</p>",
            summary="Summary",
        )
        self.assertIn("news-article-body", html)
        self.assertIn("<p>Body</p>", html)
        self.assertIn("/website/site.css", html)
        self.assertIn("site-nav", html)
        self.assertIn("site-footer", html)


if __name__ == "__main__":
    unittest.main()
