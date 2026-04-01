"""Prompt templates for LLM generation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class PromptTemplate(BaseModel):
    name: str
    version: str = "v1"
    system: str = ""
    user_template: str = ""

    def render(self, **kwargs: Any) -> str:
        return self.user_template.format(**kwargs)


SYSTEM_CONTENT_INTEL = (
    "You are an expert content intelligence analyst working for a media/marketing team. "
    "Your role is to analyze trend data and provide clear, actionable insights. "
    "Be concise, specific, and focus on what the content team should do."
)


TREND_SUMMARY_V1 = PromptTemplate(
    name="trend_summary_v1",
    version="v1",
    system=SYSTEM_CONTENT_INTEL,
    user_template=(
        "Analyze this trend and provide a summary for the content/marketing team.\n\n"
        "trend_summary prompt template\n"
        "Topic: {topic}\n"
        "Category: {category}\n"
        "Score: {score}\n"
        "Confidence: {confidence}\n"
        "Direction: {direction}\n"
        "Growth rate: {growth_rate}%\n"
        "Event count: {event_count}\n"
        "Sources: {source}\n"
        "First seen: {first_seen}\n"
        "Last seen: {last_seen}\n\n"
        "Provide:\n"
        "1. A clear summary of what this trend is about\n"
        "2. Why it matters for content/marketing teams\n"
        "3. Confidence assessment\n"
        "4. Recommended action"
    ),
)

RECOMMENDATION_ENHANCEMENT_V1 = PromptTemplate(
    name="recommendation_enhancement_v1",
    version="v1",
    system=SYSTEM_CONTENT_INTEL,
    user_template=(
        "Enhance this recommendation for a content/marketing team.\n\n"
        "recommendation enhance prompt template\n"
        "Title: {title}\n"
        "Body: {body}\n"
        "Priority: {priority}\n"
        "Category: {category}\n"
        "Confidence: {confidence}\n"
        "Linked trend topic: {trend_topic}\n"
        "Trend score: {trend_score}\n\n"
        "Provide:\n"
        "1. Detailed action plan (2-3 steps)\n"
        "2. Why now (timing rationale)\n"
        "3. Risk assessment\n"
        "4. Expected impact"
    ),
)

EXECUTIVE_DIGEST_V1 = PromptTemplate(
    name="executive_digest_v1",
    version="v1",
    system=SYSTEM_CONTENT_INTEL,
    user_template=(
        "Generate an executive content intelligence briefing digest.\n\n"
        "digest briefing prompt template\n"
        "Period: {period}\n"
        "Total events: {total_events}\n"
        "Trends detected: {trends_count}\n"
        "Active recommendations: {recs_count}\n"
        "Alerts dispatched: {alerts_count}\n\n"
        "Top trends:\n{top_trends}\n\n"
        "Top recommendations:\n{top_recs}\n\n"
        "Provide a concise executive briefing covering:\n"
        "1. Key findings\n"
        "2. Top trends to watch\n"
        "3. Priority recommendations\n"
        "4. Key risks and considerations"
    ),
)

ALERT_EXPLANATION_V1 = PromptTemplate(
    name="alert_explanation_v1",
    version="v1",
    system=SYSTEM_CONTENT_INTEL,
    user_template=(
        "Explain this alert for the content/marketing team.\n\n"
        "alert explain prompt template\n"
        "Title: {title}\n"
        "Type: {alert_type}\n"
        "Severity: {severity}\n"
        "Body: {body}\n"
        "Linked trend: {trend_topic}\n\n"
        "Provide a brief, clear explanation of why this alert fired and what action the team should take."
    ),
)

TEMPLATES: dict[str, PromptTemplate] = {
    "trend_summary_v1": TREND_SUMMARY_V1,
    "recommendation_enhancement_v1": RECOMMENDATION_ENHANCEMENT_V1,
    "executive_digest_v1": EXECUTIVE_DIGEST_V1,
    "alert_explanation_v1": ALERT_EXPLANATION_V1,
}
