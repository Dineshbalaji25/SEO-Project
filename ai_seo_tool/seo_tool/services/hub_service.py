from __future__ import annotations

from dataclasses import asdict, dataclass

STATUS_PLANNED = "planned"
STATUS_AVAILABLE = "available"
STATUS_MVP = "mvp"


@dataclass(frozen=True)
class HubModule:
    key: str
    name: str
    status: str
    description: str


def get_hub_overview() -> dict:
    return {
        "platform_goal": (
            "Build a single SEO Operations Hub where analysts can research, optimize, "
            "publish, and measure product SEO without switching tools."
        ),
        "core_modules": [asdict(module) for module in _core_modules()],
        "marketing_strategies": _marketing_strategies(),
        "daily_workflow": _daily_workflow(),
        "implementation_phases": _implementation_phases(),
        "architecture": _architecture_direction(),
        "success_metrics": _success_metrics(),
    }


def _core_modules() -> tuple[HubModule, ...]:
    return (
        HubModule("keyword_research", "Keyword Research", STATUS_PLANNED, "Keyword ideas, search intent grouping, and difficulty/volume tracking."),
        HubModule("on_page_auditor", "On-Page SEO Auditor", STATUS_PLANNED, "Title/meta/H1/content checks, schema validation, and image ALT audits."),
        HubModule("technical_seo", "Technical SEO", STATUS_PLANNED, "Crawl health, indexability, sitemap/robots validation, and Core Web Vitals."),
        HubModule("content_optimization", "Content Optimization", STATUS_AVAILABLE, "AI-assisted title/meta/product copy generation and export."),
        HubModule("competitor_intelligence", "Competitor Intelligence", STATUS_PLANNED, "Keyword gaps, SERP snapshots, and pricing/content comparison."),
        HubModule("rank_tracking", "Rank Tracking", STATUS_PLANNED, "Daily position tracking by keyword, device, and location."),
        HubModule("backlink_monitoring", "Backlink Monitoring", STATUS_PLANNED, "New/lost backlinks and toxic link alerting."),
        HubModule("local_seo", "Local SEO", STATUS_PLANNED, "GBP consistency, citations, and review monitoring for local campaigns."),
        HubModule("analytics_attribution", "Analytics & Attribution", STATUS_MVP, "Traffic, conversions, and channel impact dashboards."),
    )


def _marketing_strategies() -> list[str]:
    return [
        "Product-led SEO for transactional category and product intent.",
        "Topic-cluster strategy with pillar + supporting pages.",
        "Programmatic SEO for long-tail product and use-case variants.",
        "CRO + SEO alignment to improve CTR and on-page conversion.",
        "Retention loops with remarketing and SEO content journeys.",
        "Authority building with digital PR, backlinks, and partner co-marketing.",
        "Continuous A/B testing for titles, snippets, CTAs, and schema.",
    ]


def _daily_workflow() -> list[dict]:
    return [
        {"time": "morning", "focus": "Monitor rank drops, crawl errors, and indexation issues."},
        {"time": "midday", "focus": "Prioritize opportunities by volume, competition, and conversion intent."},
        {"time": "execution", "focus": "Bulk update metadata/content and queue technical fixes."},
        {"time": "reporting", "focus": "Compare day/week/month performance and annotate changes."},
        {"time": "alerts", "focus": "Track sudden traffic loss, deindexing, and speed regressions."},
    ]


def _implementation_phases() -> list[dict]:
    return [
        {"phase": "Phase 1 (MVP)", "scope": "Unify AI SEO generation + product sync + basic analytics dashboard."},
        {"phase": "Phase 2", "scope": "Add keyword module, on-page audit, rank tracking, and competitor tracking."},
        {"phase": "Phase 3", "scope": "Add technical crawler, backlink module, and automated recommendations."},
        {"phase": "Phase 4", "scope": "Add workflow automation, approvals, SLA alerts, and executive reporting."},
    ]


def _architecture_direction() -> list[str]:
    return [
        "Keep ai_seo_tool as the orchestration layer.",
        "Expose modular services for keyword, audit, rank, competitor, and reporting features.",
        "Use Celery for scheduled crawl, ranking, alerting, and reporting jobs.",
        "Support role-oriented dashboards for analyst, manager, and admin.",
        "Integrate connectors for GA4, GSC, ads, and ecommerce data.",
    ]


def _success_metrics() -> list[str]:
    return [
        "Organic sessions growth.",
        "Non-brand keyword growth.",
        "Product-page conversion rate from organic traffic.",
        "Time-to-fix SEO issues.",
        "Share of voice vs competitors.",
    ]
