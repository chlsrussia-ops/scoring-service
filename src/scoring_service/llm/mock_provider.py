"""Mock LLM provider - generates realistic summaries from input fields."""
from __future__ import annotations

import hashlib
import random

from scoring_service.llm.base import LlmProvider, LlmRequest, LlmResponse


def _seed_from(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


class MockLlmProvider(LlmProvider):
    provider_name = "mock"

    def is_available(self) -> bool:
        return True

    async def generate(self, request: LlmRequest) -> LlmResponse:
        rng = random.Random(_seed_from(request.prompt[:200]))
        prompt_lower = request.prompt.lower()

        if "trend_summary" in prompt_lower or "trend analysis" in prompt_lower:
            text = self._gen_trend_summary(request.prompt, rng)
        elif "recommendation" in prompt_lower and "enhance" in prompt_lower:
            text = self._gen_recommendation(request.prompt, rng)
        elif "digest" in prompt_lower or "briefing" in prompt_lower:
            text = self._gen_digest(request.prompt, rng)
        elif "alert" in prompt_lower and "explain" in prompt_lower:
            text = self._gen_alert_explanation(request.prompt, rng)
        else:
            text = self._gen_generic(request.prompt, rng)

        return LlmResponse(
            text=text,
            tokens_used=len(text.split()) * 2,
            model="mock-v1",
            provider="mock",
        )

    def _gen_trend_summary(self, prompt: str, rng: random.Random) -> str:
        lines = prompt.split("\n")
        topic = "this topic"
        for line in lines:
            if "topic:" in line.lower() or "title:" in line.lower():
                topic = line.split(":", 1)[-1].strip()
                break

        momentum = rng.choice(["strong", "accelerating", "steady", "explosive"])
        timeframe = rng.choice(["the past 48 hours", "the last week", "recent days", "the past 72 hours"])
        impact = rng.choice(["high", "significant", "notable", "substantial"])
        data_points = str(rng.randint(3, 12))
        sources = str(rng.randint(2, 5))
        conf = rng.choice(["high", "moderate-to-high", "strong"])

        return (
            "## Trend Summary: " + topic + "\n\n"
            "**What is happening:** This trend shows " + momentum + " momentum over " + timeframe + ", "
            "driven by increased discussion volume and engagement across multiple sources. "
            "The growth pattern indicates genuine audience interest rather than algorithmic amplification.\n\n"
            "**Why it matters:** Content and marketing teams should pay attention because this topic "
            "has " + impact + " potential for audience engagement. Early movers who create content around "
            "this theme are likely to capture disproportionate attention.\n\n"
            "**Confidence:** The signal is supported by " + data_points + " independent data points "
            "across " + sources + " sources, giving us " + conf + " "
            "confidence in the trend direction.\n\n"
            "**Recommended action:** Consider fast-follow content creation targeting this theme. "
            "Monitor for sustained growth over the next 24-48 hours before committing major resources."
        )

    def _gen_recommendation(self, prompt: str, rng: random.Random) -> str:
        lines = prompt.split("\n")
        title = "this recommendation"
        for line in lines:
            if "title:" in line.lower():
                title = line.split(":", 1)[-1].strip()
                break

        actions = [
            "Publish a fast-follow article or social media series on this topic within the next 24 hours.",
            "Brief the editorial team and assign a dedicated writer to develop an in-depth piece.",
            "Create a short-form video or carousel post highlighting key angles of this trend.",
            "Schedule a content planning session to explore multiple angles and formats.",
            "Prepare a data-driven infographic summarizing the trend for social sharing.",
        ]
        risks = [
            "The trend may be short-lived - avoid over-investing before confirmation.",
            "Competitors may already be covering this angle; differentiation is key.",
            "Audience sentiment appears mixed - monitor reactions closely after publishing.",
            "Volume is growing but engagement depth is uneven across platforms.",
        ]
        hours = rng.choice(["24", "48", "72"])
        multiplier = str(rng.randint(2, 8))

        return (
            "## Enhanced Recommendation: " + title + "\n\n"
            "**Action plan:**\n"
            "1. " + rng.choice(actions) + "\n"
            "2. Set up monitoring alerts for related keywords and competitor activity.\n"
            "3. Prepare 2-3 content variations to test which angle resonates best.\n\n"
            "**Why now:** The current growth trajectory suggests a window of opportunity "
            "in the next " + hours + " hours. Acting quickly positions "
            "your brand as a thought leader on this emerging topic.\n\n"
            "**Risk note:** " + rng.choice(risks) + "\n\n"
            "**Expected impact:** Based on similar trends, well-timed content could generate "
            + multiplier + "x typical engagement rates."
        )

    def _gen_digest(self, prompt: str, rng: random.Random) -> str:
        new_trends = str(rng.randint(3, 8))
        strong = str(rng.randint(1, 3))
        level = rng.choice(["elevated", "high", "moderate"])
        recs = str(rng.randint(2, 5))
        pct = str(rng.randint(15, 60))
        competitor = str(rng.randint(1, 3))

        return (
            "## Executive Content Intelligence Briefing\n\n"
            "**Period:** Last 24 hours\n\n"
            "### Key Findings\n"
            "- " + new_trends + " new trends detected, " + strong + " showing strong upward momentum\n"
            "- Content opportunity score is " + level + " across monitored categories\n"
            "- " + recs + " actionable recommendations generated for the content team\n\n"
            "### Top Trends\n"
            "1. **AI-powered content tools** - Growing " + pct + "% in discussion volume\n"
            "2. **Short-form video strategy** - Sustained interest with high engagement signals\n"
            "3. **Creator economy shifts** - New platform dynamics creating content opportunities\n\n"
            "### Recommendations\n"
            "- Prioritize fast-follow content on the top trending topic\n"
            "- Escalate emerging themes to the editorial calendar review\n"
            "- Monitor volatile discussions for brand safety considerations\n\n"
            "### Risks\n"
            "- One topic shows potentially negative sentiment - requires monitoring\n"
            "- Competitor activity detected on " + competitor + " trending themes\n"
        )

    def _gen_alert_explanation(self, prompt: str, rng: random.Random) -> str:
        lines = prompt.split("\n")
        title = "this alert"
        for line in lines:
            if "title:" in line.lower():
                title = line.split(":", 1)[-1].strip()
                break

        metric = rng.choice(["growth rate", "engagement velocity", "discussion volume", "source coverage"])
        pct = str(rng.randint(150, 400))

        return (
            "**Alert: " + title + "**\n\n"
            "This alert was triggered because the trend exceeded the configured threshold "
            "for " + metric + ". "
            "Specifically, the measured value reached " + pct + "% of the baseline, "
            "crossing the alert boundary.\n\n"
            "The content team should review this signal and determine whether immediate action "
            "(content creation, campaign adjustment, or editorial escalation) is warranted."
        )

    def _gen_generic(self, prompt: str, rng: random.Random) -> str:
        patterns = str(rng.randint(2, 5))
        strength = rng.choice(["moderate", "strong", "notable"])
        hours = rng.choice(["24", "48", "72"])

        return (
            "Based on the available data, this analysis identifies " + patterns + " key patterns "
            "worth noting. The overall signal strength is " + strength + ", "
            "suggesting the content/marketing team should monitor developments over the next "
            + hours + " hours and prepare responsive content strategies."
        )
