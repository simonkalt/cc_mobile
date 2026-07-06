# Articles / News API

Marketing **News** articles: HTML files on disk under `articles/`, metadata in MongoDB collection `articles`, public listing at `/news`, RSS at `/news/rss.xml`, and admin CRUD at `/api/admin/articles`.

## MongoDB schema (`articles` collection)

| Field | Type | Notes |
|-------|------|-------|
| `_id` | ObjectId | Primary key |
| `slug` | string | Unique URL slug; file is `articles/{slug}.html` |
| `title` | string | Headline |
| `summary` | string | Listing card + RSS description |
| `author` | string | Display author |
| `publishedAt` | datetime | Nullable for drafts |
| `updatedAt` | datetime | Last modified |
| `status` | string | `draft`, `published`, or `archived` |
| `htmlPath` | string | Relative path, e.g. `articles/my-post.html` |
| `sourceType` | string | `html` or `pdf` |
| `tags` | string[] | Optional |
| `featuredImage` | string | Optional site path or URL for listing card + social preview |
| `createdBy` | string | Admin user id |

Indexes: unique on `slug`; compound on `status + publishedAt`.

## Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGODB_ARTICLES_COLLECTION` | `articles` | Collection name |
| `ARTICLES_DIR` | `{repo}/articles` | HTML storage directory |
| `PUBLIC_WEBSITE_URL` | `https://www.saimonsoft.com` | Absolute links in RSS |
| `NEWS_RSS_MAX_ITEMS` | `50` | Max items in RSS feed |

## Public endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/news` | News listing page (HTML) |
| GET | `/news/{slug}` | Published article page |
| GET | `/news/rss.xml` | RSS 2.0 feed (`Cache-Control: max-age=300`) |
| GET | `/api/articles` | Paginated published articles (JSON) |
| GET | `/api/articles/{slug}` | Published article metadata |

### `GET /api/articles`

Query params: `page`, `per_page`, `sort` (`publishedAt`, `updatedAt`, `title`, `author`), `order` (`asc`/`desc`).

Returns only `published` articles.

## Admin endpoints

All require admin JWT (`Authorization: Bearer …`) after login + 2FA via `/admin`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/articles` | List all statuses (optional `status` filter) |
| GET | `/api/admin/articles/{id}` | Metadata + `htmlBody` |
| POST | `/api/admin/articles` | Create article + write HTML file |
| PUT | `/api/admin/articles/{id}` | Update metadata and/or HTML body |
| DELETE | `/api/admin/articles/{id}` | Delete article (`?hard=true` default) |
| POST | `/api/admin/articles/upload-html` | Multipart `.html` → preview `htmlBody` |
| POST | `/api/admin/articles/upload-pdf` | Multipart PDF → converted HTML preview |

### Create / update body (JSON)

```json
{
  "slug": "my-article",
  "title": "My Article",
  "summary": "Short blurb",
  "author": "sAImon Software",
  "status": "published",
  "htmlBody": "<p>Article content HTML</p>",
  "tags": ["product"],
  "featuredImage": "/website/news/images/my-article/hero.png",
  "publishedAt": "2026-06-25T12:00:00Z",
  "sourceType": "html"
}
```

## RSS feed

- URL: `/news/rss.xml`
- Channel title: **sAImon Software News**
- Items include title, link, description, pubDate, guid, author, categories
- Optional `content:encoded` with article body HTML when file exists
- Autodiscovery on `/news`: `<link rel="alternate" type="application/rss+xml" …>`

## File layout

```
articles/{slug}.html          # Themed HTML article pages
website/news/index.html       # Dynamic listing shell
website/news/news.css         # News-specific styles
website/admin/*               # Articles tab in admin portal
app/models/article.py
app/services/article_service.py
app/api/routers/articles.py
app/api/routers/admin_articles.py
app/utils/article_html.py
app/utils/rss_feed.py
```

## Seeding

On first API access, if `articles/job-cover-letter-generator-ai.html` exists and no MongoDB doc is present, metadata is inserted automatically as a published article.
