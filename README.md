# AI SEO Generator for thotfy.com

A dual-project system that uses **OpenRouter-hosted multimodal models** to analyze product images and automatically generate/push SEO metadata (Title, Description, Meta Description) into your **Django Oscar-powered** e-commerce platform.

---

## 🏗 Project Structure

1.  **`ai_seo_tool/`**: A standalone Django service that partners/vendors use.
    *   Upload images & generate SEO content via OpenRouter-hosted vision-capable models.
    *   Push approved metadata to thotfy.com via private API.
    *   Async processing via Celery + Redis.
2.  **`thotfy_oscar_api/`**: A "drop-in" Django app (`catalogue_api`) for your main thotfy.com codebase.
    *   Provides secure endpoints for the AI tool to search products and update metadata.
    *   JWT-based authentication.

---

## ⚡️ Getting Started (Standalone AI Tool)

### 1. Prerequisites
*   Python 3.10+
*   Redis (Required for Celery and image caching)
*   OpenRouter API Key ([Generate one here](https://openrouter.ai/keys))

### 2. Local Setup
```bash
cd ai_seo_tool
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 3. Environment Config
Create an `.env` file inside `ai_seo_tool/` and fill in:
*   `OPENROUTER_API_KEY`: Your OpenRouter key (required).
*   `ANTHROPIC_API_KEY`: Optional fallback/legacy key (if used by custom changes).
*   `GEMINI_API_KEY`: Optional fallback/legacy key (if used by custom changes).
*   `THOTFY_BASE_URL`: URL of your main Oscar site (e.g., `https://thotfy.com`).
*   `THOTFY_SERVICE_USERNAME`: Service account username on thotfy.com.
*   `THOTFY_SERVICE_PASSWORD`: Service account password.

### 4. Run the Engine
You need two terminals:

**Terminal 1 (Django Server):**
```bash
python manage.py migrate
python manage.py runserver
```

**Terminal 2 (Celery Worker):**
```bash
celery -A config worker --loglevel=info
```

---

## 🔌 Integrating the API into thotfy.com

To allow the AI tool to "talk" to your Oscar site, add the `catalogue_api` app to your existing codebase:

1.  **Copy the app**: `cp -r thotfy_oscar_api/catalogue_api /your/thotfy/root/`
2.  **Update settings**:
    ```python
    INSTALLED_APPS += [
        "rest_framework",
        "rest_framework_simplejwt",
        "catalogue_api",
    ]
    ```
3.  **Add URLs**:
    ```python
    urlpatterns += [
        path("api/auth/", include("catalogue_api.auth_urls")),
        path("api/",      include("catalogue_api.urls")),
    ]
    ```

---

## 🔄 How it Works (Flow)

1.  **Image Analysis**: Partner uploads a product photo. The configured OpenRouter model analyzes materials, features, and use-case.
2.  **SEO Generation**: The model generates a strict JSON response containing SEO title, meta, descriptions, captions, and competitive analysis.
3.  **Review**: Partner reviews the AI content on a sleek dashboard.
4.  **Sync**: Partner enters their partner name and product name. The tool hits thotfy.com's API, finds the correct product, and updates it in the Oscar database.
5.  **Notify**: An automated email is sent to the partner with a link to their updated live product dashboard.

---

## 🛡 Security & Design
*   **No Image Storage**: Images are processed in memory and cached temporarily in Redis (TTL: 10m).
*   **Fuzzy Matching**: Matches products by partner name + title similarity to ensure updates hit the right target.
*   **Rate Limited**: Uses batch throttling and Celery concurrency controls to reduce API overages.

---

## 🧭 SEO Operations Hub (New)

The project now includes a unified **SEO Operations Hub** blueprint layer inside `ai_seo_tool`:

- `GET /hub/` — dashboard view of platform goal, modules, strategies, workflow, phases, architecture, and KPIs.
- `GET /api/hub/overview/` — machine-readable JSON for the same hub overview.

This keeps `ai_seo_tool` as the orchestration core while exposing planned modules for:
- Keyword research
- On-page auditing
- Technical SEO
- Content optimization
- Competitor intelligence
- Rank tracking
- Backlink monitoring
- Local SEO
- Analytics and attribution

---

Developed for **thotfy** e-commerce. License: Private.
