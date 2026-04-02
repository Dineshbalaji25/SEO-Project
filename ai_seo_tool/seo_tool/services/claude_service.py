"""
services/claude_service.py  —  Claude Vision → structured SEO content
"""
from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from typing import BinaryIO

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

SEO_SYSTEM_PROMPT = """\
You are a senior e-commerce SEO copywriter. You will be given a product image and a product name.

Analyse the image carefully — identify the product type, materials, key features, colours,
and any visible use-case signals — then generate three SEO fields.

Respond with ONLY a valid JSON object. No markdown, no explanation, nothing else:

{
  "seo_title": "...",
  "seo_description": "...",
  "meta_description": "..."
}

RULES:
• seo_title        50–70 chars. Primary keyword near the start. No ALL CAPS.
• seo_description  150–300 words. Plain text (no HTML). Lead with the strongest benefit.
                   Weave in 2–3 secondary keywords naturally. End with a soft CTA.
• meta_description 140–155 chars max. One complete sentence. Primary keyword once.
                   Benefit + feature + implicit action.
"""


@dataclass
class SEOContent:
    seo_title: str
    seo_description: str
    meta_description: str

    def to_dict(self) -> dict:
        return {
            "seo_title": self.seo_title,
            "seo_description": self.seo_description,
            "meta_description": self.meta_description,
        }


class ClaudeServiceError(Exception):
    pass


def generate_seo_content(
    image_file: BinaryIO,
    product_name: str,
    image_media_type: str = "image/jpeg",
) -> SEOContent:
    """
    Send the product image + name to Claude Vision.
    Returns a validated SEOContent dataclass.
    """
    image_b64 = base64.standard_b64encode(image_file.read()).decode()
    client = anthropic.Anthropic(
        api_key=settings.ANTHROPIC_API_KEY,
        timeout=180.0,  # 3 min timeout for large image uploads
    )
    
    try:
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1024,
            system=SEO_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"Product name: {product_name}\n\n"
                            "Analyse the image and generate the SEO fields. "
                            "Return ONLY the JSON object."
                        ),
                    },
                ],
            }],
        )
    except anthropic.APIConnectionError as e:
        logger.exception("Claude connection error: %s", e)
        raise ClaudeServiceError(f"Could not reach Anthropic API: {e}") from e
    except anthropic.RateLimitError as e:
        raise ClaudeServiceError("Anthropic rate limit hit — please retry shortly.") from e
    except anthropic.APIStatusError as e:
        raise ClaudeServiceError(f"Anthropic API error {e.status_code}: {e.message}") from e

    raw = _extract_text(response)
    logger.debug("Claude raw response: %.400s", raw)
    return _parse_and_validate(raw)


# ── helpers ───────────────────────────────────────────────────────────────────

def _extract_text(response) -> str:
    for block in response.content:
        if block.type == "text":
            return block.text.strip()
    raise ClaudeServiceError("Claude returned no text block.")


def _parse_and_validate(raw: str) -> SEOContent:
    clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    if not match:
        raise ClaudeServiceError(f"No JSON found in Claude response: {raw[:300]}")
    try:
        data = json.loads(match.group())
    except json.JSONDecodeError as e:
        raise ClaudeServiceError(f"Malformed JSON from Claude: {e}") from e

    for field in ("seo_title", "seo_description", "meta_description"):
        if field not in data:
            raise ClaudeServiceError(f"Claude JSON missing field: {field}")

    title = data["seo_title"].strip()
    meta = data["meta_description"].strip()

    if len(title) > 70:
        title = title[:70].rsplit(" ", 1)[0]
    if len(meta) > 160:
        meta = meta[:157].rsplit(" ", 1)[0] + "..."

    return SEOContent(
        seo_title=title,
        seo_description=data["seo_description"].strip(),
        meta_description=meta,
    )
