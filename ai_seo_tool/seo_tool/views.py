"""
views.py  —  Two-step UX

Step A — GET  /           Show the upload form (image only at this stage)
         POST /           Receive image → call Claude → return SEO preview as JSON
                          The image is cached in Redis keyed by a session token.
                          No thotfy write yet.

Step B — POST /submit/    Receive partner name + product name + email
                          + the session token that points to the cached image + SEO content.
                          Kick off the Celery task. Redirect to /status/<task_id>/

Step C — GET  /status/<task_id>/
         Returns JSON for the frontend poller:
         { status, seo_title, meta_description, admin_url, error }
"""
from __future__ import annotations

import base64
import io
import logging
import uuid

from django.core.cache import cache
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_GET

from .services import ClaudeServiceError, generate_seo_content
from .tasks import cache_image, run_seo_pipeline

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg":  "image/jpeg",
    "image/png":  "image/png",
    "image/webp": "image/webp",
}

SEO_CACHE_KEY  = "seo_result_{token}"
SEO_CACHE_TTL  = 60 * 30   # 30 min — user can take their time reviewing


class GenerateView(View):
    """
    GET  / → render upload page
    POST / → receive image, call Claude, return SEO preview JSON
    """

    def get(self, request):
        return render(request, "seo_tool/index.html")

    def post(self, request):
        # ── Validate image ────────────────────────────────────────────────────
        image_file = request.FILES.get("product_image")
        if not image_file:
            return JsonResponse({"error": "No image uploaded."}, status=400)

        media_type = ALLOWED_TYPES.get(
            getattr(image_file, "content_type", "").lower()
        )
        if not media_type:
            return JsonResponse(
                {"error": "Unsupported format. Upload JPG, PNG or WebP."},
                status=400,
            )

        if image_file.size > 8 * 1024 * 1024:
            return JsonResponse({"error": "Image too large. Max 8 MB."}, status=400)

        product_name_hint = request.POST.get("product_name_hint", "").strip()

        # ── Call Claude Vision ────────────────────────────────────────────────
        image_bytes = image_file.read()

        try:
            seo = generate_seo_content(
                image_file=io.BytesIO(image_bytes),
                product_name=product_name_hint or "this product",
                image_media_type=media_type,
            )
        except ClaudeServiceError as e:
            logger.error("Claude error during generate: %s", e)
            return JsonResponse({"error": str(e)}, status=502)

        # ── Cache image + SEO for the submit step ─────────────────────────────
        token = uuid.uuid4().hex
        cache_image(token, image_bytes, media_type)
        cache.set(
            SEO_CACHE_KEY.format(token=token),
            seo.to_dict(),
            timeout=SEO_CACHE_TTL,
        )

        return JsonResponse({
            "token": token,
            "seo_title":        seo.seo_title,
            "seo_description":  seo.seo_description,
            "meta_description": seo.meta_description,
        })


class SubmitView(View):
    """
    POST /submit/

    Receives:
      token        — session token linking to cached image + SEO
      partner_name — partner's registered name on thotfy.com
      product_name — product to update
      email        — for notifications

    Queues the Celery pipeline, returns { task_id }.
    """

    def post(self, request):
        token        = request.POST.get("token", "").strip()
        partner_name = request.POST.get("partner_name", "").strip()
        product_name = request.POST.get("product_name", "").strip()
        email        = request.POST.get("email", "").strip()

        # ── Basic validation ──────────────────────────────────────────────────
        errors = {}
        if not token:
            errors["token"] = "Session expired. Please re-upload your image."
        if not partner_name:
            errors["partner_name"] = "Partner name is required."
        if not product_name:
            errors["product_name"] = "Product name is required."
        if not email or "@" not in email:
            errors["email"] = "A valid email address is required."
        if errors:
            return JsonResponse({"errors": errors}, status=400)

        # ── Verify cached image still exists ─────────────────────────────────
        seo_data = cache.get(SEO_CACHE_KEY.format(token=token))
        if not seo_data:
            return JsonResponse(
                {"errors": {"token": "Session expired — please re-upload your image."}},
                status=400,
            )

        # ── Queue pipeline — use token as the image cache key ─────────────────
        task = run_seo_pipeline.apply_async(
            args=[token, partner_name, product_name, email],
            task_id=token,   # reuse token as task id so the image is already keyed correctly
        )

        logger.info(
            "Pipeline queued — task=%s partner=%s product=%s email=%s",
            task.id, partner_name, product_name, email,
        )

        return JsonResponse({"task_id": task.id})


class StatusView(View):
    """
    GET /status/<task_id>/

    Returns current Celery task state + result fields once done.
    Polled every 3 s by the frontend.
    """

    def get(self, request, task_id: str):
        from celery.result import AsyncResult
        result = AsyncResult(task_id)

        state = result.state   # PENDING / STARTED / SUCCESS / FAILURE / RETRY

        if state == "SUCCESS":
            data = result.result or {}
            return JsonResponse({
                "status": data.get("status", "success"),
                "seo_title":        data.get("seo_title", ""),
                "meta_description": data.get("meta_description", ""),
                "admin_url":        data.get("admin_url", ""),
            })

        if state == "FAILURE":
            return JsonResponse({
                "status": "failed",
                "error": str(result.result),
            })

        # PENDING / STARTED / RETRY → still processing
        return JsonResponse({"status": "processing"})
