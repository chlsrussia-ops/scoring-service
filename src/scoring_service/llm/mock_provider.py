"""Mock LLM provider — generates realistic summaries from input fields."""
from __future__ import annotations

import hashlib
import random

from scoring_service.llm.base import LlmProvider, LlmRequest, LlmResponse


# Deterministic seed from input for reproducible outputs
def _seed_from(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest()[:8], 16)


class MockLlmProvider(LlmProvider):
    provider_name = "mock"

    def is_available(self) -> bool:
        return True

    async def generate(self, request: LlmRequest) -> LlmResponse:
        rng = random.Random(_seed_from(request.prompt[:200]))

        # Parse context from prompt to generate relevant output
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
        # Extract topic-like keywords from prompt
        lines = prompt.split("\n")
        topic = "this topic"
        for line in lines:
            if "topic:" in line.lower() or "title:" in line.lower():
                topic = line.split(":", 1)[-1].strip()
                break

        momentum = rng.choice(["strong", "accelerating", "steady", "explosive"])
        timeframe = rng.choice(["the past 48 hours", "the last week", "recent days", "the past 72 hours"])
        impact = rng.choice(["high", "significant", "notable", "substantial"])

        return (
            f"## Trend Summary: {topic}\n\n"
            f"**What is happening:** This trend shows {momentum} momentum over {timeframe}, "
            f"driven by increased discussion volume and engagement across multiple sources. "
            f"The growth pattern indicates genuine audience interest rather than algorithmic amplification.\n\n"
            f"**Why it matters:** Content and marketing teams should pay attention because this topic "
            f"has {impact} potential for audience engagement. Early movers who create content around "
            f"this theme are likely to capture disproportionate attention.\n\n"
            f"**Confidence:** The signal is supported by {rng.randint(3, 12)} independent data points "
            f"across {rng.randint(2, 5)} sources, giving us {rng.choice([high, moderate-to-high, strong])} "
            f"confidence in the trend direction.\n\n"
            f"**Recommended action:** Consider fast-follow content creation targeting this theme. "
            f"Monitor for sustained growth over the next 24-48 hours before committing major resources."
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
            "The trend may be short-lived — avoid over-investing before confirmation.",
            "Competitors may already be covering this angle; differentiation is key.",
            "Audience sentiment appears mixed — monitor reactions closely after publishing.",
            "Volume is growing but engagement depth is uneven across platforms.",
        ]

        return (
            f"## Enhanced Recommendation: {title}\n\n"
            f"**Action plan:**\n"
            f"1. {rng.choice(actions)}\n"
            f"2. Set up monitoring alerts for related keywords and competitor activity.\n"
            f"3. Prepare 2-3 content variations to test which angle resonates best.\n\n"
            f"**Why now:** The current growth trajectory suggests a window of opportunity "
            f"in the next {rng.choice([24, 48, 72])} hours. Acting quickly positions "
            f"your brand as a thought leader on this emerging topic.\n\n"
            f"**Risk note:** {rng.choice(risks)}\n\n"
            f"**Expected impact:** Based on similar trends, well-timed content could generate "
            f"{rng.randint(2, 8)}x typical engagement rates."
        )

    def _gen_digest(self, prompt: str, rng: random.Random) -> str:
        return (
            f"## Executive Content Intelligence Briefing\n\n"
            f"**Period:** Last 24 hours\n\n"
            f"### Key Findings\n"
            f"- {rng.randint(3, 8)} new trends detected, {rng.randint(1, 3)} showing strong upward momentum\n"
            f"- Content opportunity score is {rng.choice([elevated, high, moderate])} across monitored categories\n"
            f"- {rng.randint(2, 5)} actionable recommendations generated for the content team\n\n"
            f"### Top Trends\n"
            f"1. **AI-powered content tools** — Growing {rng.randint(15, 60)}% in discussion volume\n"
            f"2. **Short-form video strategy** — Sustained interest with high engagement signals\n"
            f"3. **Creator economy shifts** — New platform dynamics creating content opportunities\n\n"
            f"### Recommendations\n"
            f"- Prioritize fast-follow content on the top trending topic\n"
            f"- Escalate emerging themes to the editorial calendar review\n"
            f"- Monitor volatile discussions for brand safety considerations\n\n"
            f"### Risks\n"
            f"- One topic shows potentially negative sentiment — requires monitoring\n"
            f"- Competitor activity detected on {rng.randint(1, 3)} trending themes\n"
        )

    def _gen_alert_explanation(self, prompt: str, rng: random.Random) -> str:
        lines = prompt.split("\n")
        title = "this alert"
        for line in lines:
            if "title:" in line.lower():
                title = line.split(":", 1)[-1].strip()
                break

        return (
            f"**Alert: {title}**\n\n"
            f"This alert was triggered because the trend exceeded the configured threshold "
            f"for {rng.choice([growth rate, engagement velocity, discussion volume, source coverage])}. "
            f"Specifically, the measured value reached {rng.randint(150, 400)}% of the baseline, "
            f"crossing the alert boundary.\n\n"
            f"The content team should review this signal and determine whether immediate action "
            f"(content creation, campaign adjustment, or editorial escalation) is warranted."
        )

    def _gen_generic(self, prompt: str, rng: random.Random) -> str:
        return (
            f"Based on the available data, this analysis identifies {rng.randint(2, 5)} key patterns "
            f"worth noting. The overall signal strength is {rng.choice([moderate, strong, notable])}, "
            f"suggesting the content/marketing team should monitor developments over the next "
            f"{rng.choice([24, 48, 72])} hours and prepare responsive content strategies."
        )
