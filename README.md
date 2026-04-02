# AI SEO Generator for thotfy.com

A dual-project system that uses **Claude 3.5 Sonnet Vision** to analyze product images and automatically generate/push SEO metadata (Title, Description, Meta Description) into your **Django Oscar-powered** e-commerce platform.

---

## 🏗 Project Structure

1.  **`ai_seo_tool/`**: A standalone Django service that partners/vendors use.
    *   Upload images & generate SEO content via Claude Vision.
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
*   Anthropic API Key ([Generate one here](https://console.anthropic.com/))

### 2. Local Setup
```bash
cd ai_seo_tool
python -m venv env
source env/bin/activate
pip install -r requirements.txt
```

### 3. Environment Config
Rename `.env.example` to `.env` (or use the one I created) and fill in:
*   `ANTHROPIC_API_KEY`: Your Claude key.
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

1.  **Image Analysis**: Partner uploads a product photo. Claude Vision analyzes materials, features, and use-case.
2.  **SEO Generation**: Claude generates a strict JSON response containing a 60-char title, 200-word description, and 155-char meta-tag.
3.  **Review**: Partner reviews the AI content on a sleek dashboard.
4.  **Sync**: Partner enters their partner name and product name. The tool hits thotfy.com's API, finds the correct product, and updates it in the Oscar database.
5.  **Notify**: An automated email is sent to the partner with a link to their updated live product dashboard.

---

## 🛡 Security & Design
*   **No Image Storage**: Images are processed in memory and cached temporarily in Redis (TTL: 10m).
*   **Fuzzy Matching**: Matches products by partner name + title similarity to ensure updates hit the right target.
*   **Rate Limited**: Enforces Anthropic's rate limits and Celery concurrency to prevent API overages.

---

Developed for **thotfy** e-commerce. License: Private.
