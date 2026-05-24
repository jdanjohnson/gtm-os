"""Brand configuration REST API — read/update brand primitives."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()
logger = logging.getLogger(__name__)

BRAND_YAML = "brand.yaml"
BRAND_MD = "BRAND.md"
TONE_YAML = "tone.yaml"


class BrandIdentity(BaseModel):
    company_name: str = ""
    tagline: str = ""
    website: str = ""
    product_description: str = ""
    social: dict[str, str] = {}
    icp: str = ""
    icp_negative: str = ""
    voice: list[str] = []
    avoid: list[str] = []
    prefer: list[str] = []
    email_max_sentences: int = 4
    email_max_words: int = 90


def _brand_dir(request: Request) -> Path:
    gtm = request.app.state.gtm
    return Path(gtm.config.primitives_dir) / "brand"


def _read_brand_yaml(brand_dir: Path) -> dict[str, Any]:
    path = brand_dir / BRAND_YAML
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _read_tone_yaml(brand_dir: Path) -> dict[str, Any]:
    path = brand_dir / TONE_YAML
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except yaml.YAMLError:
        return {}


def _read_brand_md(brand_dir: Path) -> str:
    path = brand_dir / BRAND_MD
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _assemble_response(brand_dir: Path) -> dict[str, Any]:
    """Read all brand files and assemble a structured response."""
    brand_yaml = _read_brand_yaml(brand_dir)
    tone = _read_tone_yaml(brand_dir)
    brand_md = _read_brand_md(brand_dir)

    return {
        "company_name": brand_yaml.get("company_name", ""),
        "tagline": brand_yaml.get("tagline", ""),
        "website": brand_yaml.get("website", ""),
        "product_description": brand_yaml.get("product_description", ""),
        "social": brand_yaml.get("social", {}),
        "icp": brand_yaml.get("icp", ""),
        "icp_negative": brand_yaml.get("icp_negative", ""),
        "voice": tone.get("voice", []),
        "avoid": tone.get("avoid", []),
        "prefer": tone.get("prefer", []),
        "email_max_sentences": (tone.get("length") or {}).get("email_max_sentences", 4),
        "email_max_words": (tone.get("length") or {}).get("email_max_words", 90),
        "brand_body": brand_md,
    }


@router.get("/brand")
async def get_brand(request: Request) -> dict[str, Any]:
    return _assemble_response(_brand_dir(request))


@router.put("/brand")
async def update_brand(request: Request, body: BrandIdentity) -> dict[str, Any]:
    brand_dir = _brand_dir(request)
    brand_dir.mkdir(parents=True, exist_ok=True)

    # Write brand.yaml (structured identity)
    brand_data: dict[str, Any] = {
        "company_name": body.company_name,
        "tagline": body.tagline,
        "website": body.website,
        "product_description": body.product_description,
        "social": body.social,
        "icp": body.icp,
        "icp_negative": body.icp_negative,
    }
    (brand_dir / BRAND_YAML).write_text(
        yaml.dump(brand_data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    # Update tone.yaml with voice/avoid/prefer + length
    tone = _read_tone_yaml(brand_dir)
    tone["voice"] = body.voice
    tone["avoid"] = body.avoid
    tone["prefer"] = body.prefer
    tone.setdefault("length", {})
    tone["length"]["email_max_sentences"] = body.email_max_sentences
    tone["length"]["email_max_words"] = body.email_max_words
    (brand_dir / TONE_YAML).write_text(
        yaml.dump(tone, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )

    # Regenerate BRAND.md from structured data
    md = _generate_brand_md(body)
    (brand_dir / BRAND_MD).write_text(md, encoding="utf-8")

    # Invalidate cached primitives so next agent call uses new brand
    gtm = request.app.state.gtm
    gtm.runner._primitives_cache = None

    logger.info("Brand config updated: %s", body.company_name or "(unnamed)")
    return _assemble_response(brand_dir)


def _generate_brand_md(b: BrandIdentity) -> str:
    """Generate BRAND.md from structured brand data."""
    name = b.company_name or "[Your Company]"
    tagline = b.tagline or "[Your tagline]"
    product = b.product_description or (
        "[Replace this — a single, plain sentence. No buzzwords.]"
    )
    icp = b.icp or (
        "- Real buyers with real budgets (VP-level and above for B2B; "
        "owners / GMs for local SMB).\n"
        "- People who have a specific pain you can name."
    )
    icp_neg = b.icp_negative or (
        "- Not: students, analysts, journalists, random newsletter subscribers."
    )

    voice_lines = ""
    if b.voice:
        voice_lines = "\n".join(f"- {v}" for v in b.voice)
    else:
        voice_lines = (
            "- Plain English. Cut every word that isn't earning its place.\n"
            "- Lead with the problem you solve, not the product you built.\n"
            "- Confident, not desperate. Warm, not corporate."
        )

    social_block = ""
    if b.social:
        social_lines = [f"- **{k.title()}:** {v}" for k, v in b.social.items() if v]
        if social_lines:
            social_block = (
                "\n## Where to find us\n\n"
                + "\n".join(social_lines)
                + "\n"
            )

    website_line = ""
    if b.website:
        website_line = f"\n**Website:** {b.website}\n"

    return f"""# Brand

> {tagline}

## Who you are

You are the go-to-market team for **{name}**. You build, ship, and learn fast.
You write the way you'd talk to a smart friend who has thirty seconds.
{website_line}
## What you sell, in one sentence

{product}

## Who you talk to

{icp}
{icp_neg}

## How you talk

{voice_lines}
{social_block}
## What you never do

- Don't fake personalization. ("Loved your recent post" when you haven't read it.)
- Don't ask for a "quick chat" without saying what's in it for them.
- Don't open with "Hope this finds you well."
- Don't claim AI in the cold email. (Claim outcomes, not technology.)
- Don't talk about yourself in the first sentence. Ever.
- Don't send anything you wouldn't be proud to see screenshotted.

## What "great" looks like

A great email gets a reply. A great call books a meeting. A great landing page gets one
ICP-fit signup per ten visits. A great experiment teaches you something concrete about
your buyer that survives in memory and shapes the next experiment.

If you can't picture the next conversation a piece of work would start, the work isn't
done.
"""
