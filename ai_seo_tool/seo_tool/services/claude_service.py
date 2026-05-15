"""
services/claude_service.py  —  OpenRouter (Gemini) → structured SEO content
(Kept the name 'claude_service' to avoid breaking imports elsewhere)
"""
from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import BinaryIO

from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)

SEO_SYSTEM_PROMPT = """\
You are a senior e-commerce SEO strategist and Social Media Manager. Analyze the product image and name to generate comprehensive SEO and marketing content.

Analyse the image for: materials, features, target audience, and unique selling points.

Respond with ONLY a valid JSON object:
{
  "seo_title": "...",
  "slug": "...",
  "meta_title": "...",
  "meta_description": "...",
  "seo_description": "...",
  "captions": ["caption 1", "caption 2", "caption 3", "caption 4", "caption 5"],
  "keyword_analysis": "...",
  "competitor_analysis": "..."
}

CRITICAL RULES:
• seo_title: 50–70 chars. Keyword-rich.
• slug: URL-friendly version (kebab-case).
• meta_title: High-CTR search title (under 60 chars).
• meta_description: Action-oriented summary for search results (under 160 chars).
• seo_description: Engaging product description highlighting benefits and features (approx 75-100 words). MUST NOT BE EMPTY. Do not output excessively long text.
• captions: 5 distinct creative social media post ideas with emojis.
• keyword_analysis: List 5-7 high-traffic keywords and why they matter.
• competitor_analysis: Identify 2 similar product categories and 1 way to beat them visually/copy-wise.
"""


@dataclass
class SEOContent:
    seo_title: str
    slug: str
    meta_title: str
    meta_description: str
    seo_description: str
    captions: list[str]
    keyword_analysis: str
    competitor_analysis: str

    def to_dict(self) -> dict:
        return {
            "seo_title": self.seo_title,
            "slug": self.slug,
            "meta_title": self.meta_title,
            "meta_description": self.meta_description,
            "seo_description": self.seo_description,
            "captions": self.captions,
            "keyword_analysis": self.keyword_analysis,
            "competitor_analysis": self.competitor_analysis,
        }


class ClaudeServiceError(Exception):
    """Aliased error to match legacy naming."""
    pass


def generate_seo_content(
    image_file: BinaryIO,
    product_name: str,
    image_media_type: str = "image/jpeg",
    model_index: int = 0,
    batch_size: int = 1,
) -> SEOContent:
    """
    Send the product image + name to OpenRouter.
    Returns a validated SEOContent dataclass.
    """
    if not settings.OPENROUTER_API_KEY:
        raise ClaudeServiceError(
            "OPENROUTER_API_KEY is not set. Add it to your .env file."
        )

    # OpenRouter uses OpenAI-compatible API
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )

    if batch_size == 1:
        MODELS = ["google/gemini-2.5-flash"]
    else:
        MODELS = [
            "qwen/qwen3.6-plus:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
        ]

    base_index = model_index if batch_size > 1 else 0
    image_b64 = base64.standard_b64encode(image_file.read()).decode()
    last_error = None

    for attempt in range(len(MODELS)):
        current_index = (base_index + attempt) % len(MODELS)
        model_name = MODELS[current_index]
        logger.info("Attempting SEO generation with model: %s", model_name)

        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"{SEO_SYSTEM_PROMPT}\n\nProduct name: {product_name}\n\nAnalyse the image and generate the SEO and marketing fields. Return ONLY raw JSON, starting with {{ and ending with }}. Do not output any thinking or markdown blocks."
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{image_media_type};base64,{image_b64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=2500
            )

            if not response or not response.choices[0].message.content:
                raise ClaudeServiceError("OpenRouter returned no content.")

            raw = response.choices[0].message.content.strip()
            return _parse_and_validate(raw)

        except Exception as e:
            if _is_non_retryable_auth_error(e):
                logger.error("OpenRouter authentication failed: %s", e)
                raise ClaudeServiceError(
                    "Cloud analysis failed: OpenRouter authentication error (401). "
                    "Verify OPENROUTER_API_KEY and that the OpenRouter account/user exists."
                ) from e
            logger.warning("Model %s failed: %s", model_name, e)
            last_error = e
            continue

    logger.error("All OpenRouter models failed. Last error: %s", last_error)
    raise ClaudeServiceError(f"Cloud analysis failed after trying all models. Last error: {last_error}")


# ── helpers ───────────────────────────────────────────────────────────────────

def _parse_and_validate(raw: str) -> SEOContent:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        raise ClaudeServiceError(f"No JSON found in response.")
    
    json_str = match.group()
    
    # Fix trailing commas common in LLM outputs
    json_str = re.sub(r',\s*([\]}])', r'\1', json_str)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ClaudeServiceError(f"Malformed JSON from AI. Raw snippet: {json_str[:300]}") from e

    REQUIRED = ("seo_title", "slug", "meta_title", "meta_description", 
                "seo_description", "captions", "keyword_analysis", "competitor_analysis")
    
    for field in REQUIRED:
        if field not in data:
            data[field] = "" if field != "captions" else []

    return SEOContent(
        seo_title=str(data["seo_title"]).strip(),
        slug=str(data["slug"]).strip(),
        meta_title=str(data["meta_title"]).strip(),
        meta_description=str(data["meta_description"]).strip(),
        seo_description=str(data["seo_description"]).strip(),
        captions=data["captions"],
        keyword_analysis=str(data["keyword_analysis"]).strip(),
        competitor_analysis=str(data["competitor_analysis"]).strip(),
    )


def _is_non_retryable_auth_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 401:
        return True

    message = str(exc).lower()
    return "error code: 401" in message or "user not found" in message
