"""OpenAI-based AI provider for enrichment (web search) and scoring."""
import json
import logging

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from pese.config import OPENAI_API_KEY, ENRICHMENT_MODEL, SCORING_MODEL
from pese.cost_tracker import CostTracker
from pese.exceptions import EnrichmentError, ProviderError, ScoringError
from pese.models import EnrichmentResult, ScoringResult
from pese.providers.base import AIProvider

logger = logging.getLogger(__name__)


ENRICHMENT_PROMPT = """You are a research analyst specializing in institutional capital allocators (Limited Partners / LPs) for private credit fundraising.

Research the following organization and provide a structured analysis. Focus on INVESTMENT-RELATED information, not just mission/program descriptions.

Organization: {org_name}
Reported type: {org_type}
Region: {region}

Investigate and report on ALL of the following:

1. **Organization Overview**: What does this organization do? Is it a capital allocator (LP) that invests in funds managed by external GPs, or is it a GP/service provider/lender/broker that manages money or provides services?

2. **LP Status**: Does this entity allocate capital to external fund managers? Evidence of fund commitments, fund-of-funds activity, or allocations to private equity/credit/debt/real assets managers.
   - CRITICAL: Organizations that originate loans, broker deals, advise on transactions, or manage assets for others are GPs or service providers, NOT LPs. They should NOT be classified as LPs.
   - EXCEPTION: Some entities (e.g., family offices) both manage internal capital AND allocate to external managers. If there is evidence of external fund allocations, treat as LP.

3. **Private Credit / Debt Allocation**: Any evidence of allocations to private credit, private debt, direct lending, or senior secured lending funds.

4. **Sustainability / Impact Mandate**: Any ESG, impact investing, sustainability, climate, or responsible investing mandate, policy, or track record. For foundations/endowments/pensions, look beyond their charitable mission to their INVESTMENT policies.

5. **AUM (Assets Under Management)**: Total assets, investment portfolio size, or endowment size in USD. Be specific if possible.

6. **Brand Recognition**: How well-known is this organization in the institutional investor / LP community? Global brand vs. regional vs. niche vs. unknown.

7. **Emerging Manager Programs**: Any evidence of programs, mandates, or track record of investing with first-time, emerging, or Fund I/II managers. Also consider structural factors: smaller allocators (SFOs, smaller foundations) are often more open to emerging managers.

Respond in JSON format:
{{
    "overview": "2-3 sentence description",
    "is_lp": true/false/null,
    "lp_evidence": "specific evidence or lack thereof",
    "has_credit_allocation": true/false/null,
    "credit_evidence": "specific evidence",
    "has_sustainability_mandate": true/false/null,
    "sustainability_evidence": "specific evidence",
    "aum_millions": number or null,
    "aum_source": "where this figure comes from",
    "brand_recognition": "global/national/regional/niche/unknown",
    "brand_details": "brief explanation",
    "has_emerging_manager_program": true/false/null,
    "emerging_manager_evidence": "specific evidence",
    "confidence": "high/medium/low",
    "key_findings": "most important 2-3 findings for LP prospecting"
}}

Be factual. If you cannot find reliable information for a field, use null and explain why in the evidence field. Do NOT guess or fabricate information."""


SCORING_PROMPT = """You are a scoring engine for an LP prospect pipeline at PaceZero Capital Partners, a sustainability-focused private credit firm (Fund II, emerging manager).

Given the enrichment data below, produce scores (1–10) for three dimensions with brief reasoning.

## PaceZero Context
- Strategy: Private credit / direct lending (NOT equity, NOT venture)
- Fund status: Fundraising for Fund II (emerging manager)
- Themes: Agriculture & Ecosystems, Energy Transition, Health & Education
- Typical deals: $3M–$20M senior secured and subordinated
- Existing LP: The Atmospheric Fund (Toronto climate investor)

## Organization
Name: {org_name}
Reported type: {org_type}
Region: {region}

## Enrichment Data
{enrichment_json}

---

## DIMENSION 1: Sector & Mandate Fit (score 1–10)
Does this entity's investment mandate align with PaceZero's sustainability-focused private credit strategy?

RUBRIC:
- 9–10: Confirmed LP with BOTH private credit/debt fund allocations AND an explicit sustainability/impact/ESG mandate. Strong evidence of both.
- 7–8: Confirmed LP with one of the two (credit allocation OR sustainability mandate) plus some evidence of the other, or strong evidence of one with the other likely.
- 5–6: Likely an LP (allocates to external managers) but limited evidence of credit allocations or sustainability mandate specifically. OR has both mandates but only indirect evidence.
- 3–4: Possibly an LP but unclear mandate alignment. May allocate externally but no clear credit or impact focus. OR a mixed entity (part GP, part allocator).
- 1–2: NOT an LP — this is a GP, service provider, lender, broker, or asset manager that manages money for others rather than allocating to external funds. Score 1 for clear non-LPs.

CRITICAL: An organization that originates loans, brokers deals, or manages assets for others is a GP or service provider, NOT an LP. Score 1–2.

## DIMENSION 3: Halo & Strategic Value (score 1–10)
Would winning this LP send a strong signal that attracts other LPs to PaceZero?

RUBRIC:
- 9–10: Globally recognized institution whose commitment would be widely noted in impact/credit circles. Major brand (e.g., Rockefeller Foundation, Ford Foundation, major pension).
- 7–8: Well-known in institutional/impact investing. National brand recognition. Their commitment would be noticed by peer allocators.
- 5–6: Recognized in their segment (e.g., well-known family office, regional foundation). Moderate signaling value.
- 3–4: Limited public profile. Their commitment wouldn't significantly influence other LPs.
- 1–2: Unknown or negative signaling (e.g., controversial entity, or a non-LP whose name on the cap table would confuse rather than attract).

## DIMENSION 4: Emerging Manager Fit (score 1–10)
Does the LP show structural appetite for backing a Fund I/Fund II or otherwise emerging manager?

RUBRIC:
- 9–10: Has an explicit emerging manager program, documented commitments to first/second-time funds, or a public mandate to support diverse/emerging managers.
- 7–8: Structural openness to emerging managers (smaller allocator size, flexible mandate, history of early-stage fund commitments) plus some evidence of actual emerging manager backing.
- 5–6: Structural factors suggest possible openness (e.g., family office flexibility, smaller institution) but no direct evidence of emerging manager commitments.
- 3–4: Large institution with rigid allocation processes, or no evidence of emerging manager interest. Typically only invests in established managers.
- 1–2: Explicitly avoids emerging managers, has very high minimum track-record requirements, or is not an LP at all.

KEY RULES:
- Smaller allocators (SFOs, smaller foundations <$500M) often have MORE flexibility for emerging managers.
- Large pensions/insurers typically require 3+ fund track records.
- Faith-based, impact-first, and mission-driven allocators are often more open to emerging managers with aligned strategies.
- If the entity is not an LP (Dimension 1 score 1–2), Dimension 4 should also score 1–2.

---

Respond in JSON:
{{
    "sector_fit_score": <1-10>,
    "sector_fit_reasoning": "<2-3 sentences>",
    "halo_score": <1-10>,
    "halo_reasoning": "<2-3 sentences>",
    "emerging_manager_score": <1-10>,
    "emerging_manager_reasoning": "<2-3 sentences>"
}}

Use the full 1–10 range. Be precise and evidence-based. If evidence is insufficient, score conservatively (4–5) and note the uncertainty."""


class OpenAIProvider(AIProvider):
    """AI provider using OpenAI's Responses API (web search) and Chat Completions."""

    def __init__(self, api_key: str | None = None):
        key = api_key or OPENAI_API_KEY
        if not key:
            raise ProviderError("openai", "OPENAI_API_KEY is not set. Add it to .env")
        self._client = OpenAI(api_key=key)

    @property
    def name(self) -> str:
        return "openai"

    def enrich(
        self,
        org_name: str,
        org_type: str,
        region: str,
        cost_tracker: CostTracker | None = None,
    ) -> EnrichmentResult:
        prompt = ENRICHMENT_PROMPT.format(
            org_name=org_name,
            org_type=org_type or "Unknown",
            region=region or "Unknown",
        )

        try:
            data = self._call_with_web_search(prompt, org_name, cost_tracker, purpose="enrichment")
        except Exception as e:
            try:
                data = self._call_chat(prompt, cost_tracker, purpose=f"enrichment_fallback:{org_name}")
            except Exception as fallback_err:
                raise EnrichmentError(org_name, str(fallback_err)) from fallback_err

        return EnrichmentResult.from_dict(data)

    def score(
        self,
        org_name: str,
        org_type: str,
        region: str,
        enrichment: EnrichmentResult,
        cost_tracker: CostTracker | None = None,
    ) -> ScoringResult:
        prompt = SCORING_PROMPT.format(
            org_name=org_name,
            org_type=org_type or "Unknown",
            region=region or "Unknown",
            enrichment_json=json.dumps(enrichment.to_dict(), indent=2),
        )

        try:
            data = self._call_chat(prompt, cost_tracker, purpose=f"scoring:{org_name}")
        except Exception as e:
            raise ScoringError(org_name, str(e)) from e

        return ScoringResult.from_dict(data)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _call_with_web_search(
        self,
        prompt: str,
        org_name: str,
        cost_tracker: CostTracker | None,
        purpose: str = "",
    ) -> dict:
        response = self._client.responses.create(
            model=ENRICHMENT_MODEL,
            tools=[{"type": "web_search"}],
            input=prompt,
        )

        result_text = ""
        for item in response.output:
            if hasattr(item, "content"):
                for block in item.content:
                    if hasattr(block, "text"):
                        result_text = block.text

        if cost_tracker and hasattr(response, "usage") and response.usage:
            cost_tracker.record(
                model=ENRICHMENT_MODEL,
                input_tokens=getattr(response.usage, "input_tokens", 0),
                output_tokens=getattr(response.usage, "output_tokens", 0),
                purpose=f"{purpose}:{org_name}",
            )

        return self._parse_json(result_text, org_name)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def _call_chat(
        self,
        prompt: str,
        cost_tracker: CostTracker | None,
        purpose: str = "",
    ) -> dict:
        response = self._client.chat.completions.create(
            model=SCORING_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content or "{}"

        if cost_tracker and response.usage:
            cost_tracker.record(
                model=SCORING_MODEL,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                purpose=purpose,
            )

        return self._parse_json(result_text, purpose)

    @staticmethod
    def _parse_json(text: str, context: str) -> dict:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except json.JSONDecodeError:
            logger.error(f"Failed to parse JSON response for {context}")

        return {"overview": text[:500] if text else "No data retrieved", "confidence": "low"}
