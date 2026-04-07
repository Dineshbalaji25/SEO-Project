"""
tasks.py — async pipeline

Step 1  Read image from Redis cache
Step 2  Call Claude Vision → SEO content
Step 3  Validate product exists on thotfy.com (search_product)
Step 4  Push SEO fields via update_product_seo
Step 5  Send confirmation email with preview + thotfy admin link
"""
from __future__ import annotations

import io
import logging

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string

from .services import (
    ClaudeServiceError,
    SEOContent,
    ThotfyAmbiguousProductError,
    ThotfyServiceError,
    generate_seo_content,
    update_product_seo,
)

logger = logging.getLogger(__name__)

IMAGE_KEY  = "seo_img_{task_id}"
TYPE_KEY   = "seo_img_type_{task_id}"
IMAGE_TTL  = 600  # 10 min


def cache_image(task_id: str, image_bytes: bytes, media_type: str):
    cache.set(IMAGE_KEY.format(task_id=task_id), image_bytes, timeout=IMAGE_TTL)
    cache.set(TYPE_KEY.format(task_id=task_id), media_type, timeout=IMAGE_TTL)


def _pop_image(task_id: str) -> tuple[bytes, str]:
    key = IMAGE_KEY.format(task_id=task_id)
    type_key = TYPE_KEY.format(task_id=task_id)
    
    logger.info("[%s] Attempting to retrieve image from Redis key: %s", task_id, key)
    data = cache.get(key)
    mime = cache.get(type_key, "image/jpeg")
    
    if data is None:
        # Check all keys to see if we have a mismatch
        logger.error("[%s] ERROR: Cache miss on %s. Data is None.", task_id, key)
        raise RuntimeError("Image expired from cache before task ran.")
        
    logger.info("[%s] Successfully retrieved image (%d bytes) from Redis.", task_id, len(data))
    
    cache.delete(key)
    cache.delete(type_key)
    return data, mime


@shared_task(
    bind=True,
    name="seo_tool.tasks.run_seo_pipeline",
    max_retries=2,
    default_retry_delay=20,
)
def run_seo_pipeline(
    self,
    task_id: str,
    partner_name: str,
    product_name: str,
    email: str,
) -> dict:
    """
    Full async SEO enrichment pipeline.

    task_id is the Celery task ID — used as the Redis image cache key
    so the view can store the image before the task runs.
    """
    logger.info(
        "[%s] Pipeline start — partner=%s product=%s",
        task_id, partner_name, product_name,
    )

    # ── 1. Retrieve image ─────────────────────────────────────────────────────
    try:
        image_bytes, media_type = _pop_image(task_id)
    except RuntimeError as e:
        _notify_failure(email, product_name, str(e))
        return {"status": "failed", "error": str(e)}

    # ── 2. Read SEO from cache (already generated in the view) ────────────────
    SEO_CACHE_KEY = "seo_result_{task_id}"
    seo_data = cache.get(SEO_CACHE_KEY.format(task_id=task_id))

    if not seo_data:
        # Fallback: re-generate if cache expired
        logger.warning("[%s] SEO cache record missing, falling back to Claude call", task_id)
        try:
            seo: SEOContent = generate_seo_content(
                image_file=io.BytesIO(image_bytes),
                product_name=product_name,
                image_media_type=media_type,
            )
            logger.info("[%s] SEO content generated (fallback). Title: %s", task_id, seo.seo_title)
        except ClaudeServiceError as e:
            _notify_failure(email, product_name, str(e))
            return {"status": "failed", "error": str(e)}
    else:
        seo = SEOContent(**seo_data)
        logger.info("[%s] SEO content loaded from cache. Title: %s", task_id, seo.seo_title)

    # ── 3 + 4. Update thotfy.com ──────────────────────────────────────────────
    try:
        product = update_product_seo(partner_name, product_name, seo)
        logger.info(
            "[%s] thotfy.com updated — product id=%d title=%s",
            task_id, product.id, product.title,
        )
    except ThotfyAmbiguousProductError as e:
        msg = (
            f"{e} The following products were found — "
            "please re-submit with a more specific product name:\n\n"
            + "\n".join(f"  • {p['title']}" for p in e.products)
        )
        _notify_failure(email, product_name, msg)
        return {"status": "failed", "error": msg}
    except ThotfyServiceError as e:
        _notify_failure(email, product_name, str(e))
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.exception("[%s] Unexpected error: %s", task_id, e)
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            _notify_failure(email, product_name, f"Unexpected error: {e}")
            return {"status": "failed", "error": str(e)}

    # ── 5. Success email ──────────────────────────────────────────────────────
    _notify_success(email, product_name, seo, product.admin_url)

    return {
        "status": "success",
        "product_id": product.id,
        "seo_title": seo.seo_title,
        "meta_description": seo.meta_description,
        "admin_url": product.admin_url,
    }


# ── Email helpers ─────────────────────────────────────────────────────────────

def _notify_success(email: str, product_name: str, seo: SEOContent, admin_url: str):
    subject = f"✅ SEO updated — {product_name}"
    body = render_to_string("seo_tool/email_success.txt", {
        "product_name": product_name,
        "seo_title": seo.seo_title,
        "seo_description": seo.seo_description,
        "meta_description": seo.meta_description,
        "admin_url": admin_url,
    })
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as e:
        logger.warning("Failed to send success email to %s: %s", email, e)


def _notify_failure(email: str, product_name: str, error: str):
    subject = f"❌ SEO update failed — {product_name}"
    body = render_to_string("seo_tool/email_failure.txt", {
        "product_name": product_name,
        "error_message": error,
    })
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
    except Exception as e:
        logger.warning("Failed to send failure email to %s: %s", email, e)
