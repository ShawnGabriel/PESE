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

IMPORTANT — ORG TYPE CROSSCHECK:
The "Reported type" above comes from an event contact list and may be inaccurate. Your research
should independently determine what this organization actually is. If your findings conflict with the
reported type, flag it clearly.

DEFAULT ASSUMPTIONS BY ORG TYPE:
- Organizations with Reported type = "Asset Manager" or "RIA/FIA" should be presumed to be GPs
  (managing assets for others) UNLESS you find specific evidence of external fund allocations
  (acting as an LP). Managing assets for others is GP behavior, not LP behavior.
- Organizations with Reported type = "Foundation", "Endowment", or "Pension" almost always have
  investment offices that allocate to external managers — focus on their INVESTMENT activities.

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
    "key_findings": "most important 2-3 findings for LP prospecting",
    "enriched_org_type": "the org type that best describes this entity based on your research. Use one of: Single Family Office, Multi-Family Office, Fund of Funds, Foundation, Endowment, Pension, Insurance, Asset Manager, RIA/FIA, HNWI, Private Capital Firm, GP/Service Provider, Mixed (LP+GP)",
    "org_type_matches_csv": true/false,
    "org_type_conflict_note": "explanation if the reported type appears incorrect based on your research, or empty string if no conflict"
}}

Be factual. If you cannot find reliable information for a field, use null and explain why in the evidence field. Do NOT guess or fabricate information."""


SCORING_PROMPT = """You are a scoring analyst for PaceZero Capital Partners, a sustainability-focused private credit firm based in Toronto currently fundraising for Fund II as an emerging manager.

PaceZero lends $3M–$20M to companies in Agriculture & Ecosystems, Energy Transition, and Health & Education via senior secured and subordinated structures. Existing LP: The Atmospheric Fund (Toronto climate investor). Track record: 12 deals including MyLand, SWTCH Energy, Alchemy CO2, Kanin Energy, COSM Medical, CheckSammy.

Given the enrichment data below, score this organization on three dimensions. Each dimension is broken into weighted sub-components. Score each sub-component individually (1–10), then calculate the dimension composite.

## Organization
Name: {org_name}
Reported type: {org_type}
Region: {region}

## Enrichment Data
{enrichment_json}

═══════════════════════════════════════════════════════════════
DIMENSION 1: SECTOR & MANDATE FIT
═══════════════════════════════════════════════════════════════
Question: Does this entity's investment mandate align with PaceZero's sustainability-focused private credit strategy?

COMPONENT A: LP Status (40% of D1)
Is this actually a capital allocator (LP) that places money with external fund managers?
  9–10 = Confirmed institutional LP. Clear evidence of allocations to external PE/credit/RE funds.
  7–8  = Very likely LP. Org type strongly implies external allocations (endowment, pension, FoF)
         even if specific commitments aren't public.
  5–6  = Mixed or ambiguous. May do both internal management and external allocations.
  3–4  = Primarily a GP, advisor, or asset manager but might have a small allocation arm.
  1–2  = Clearly NOT an LP. Originates loans, brokers deals, manages assets for others,
         or provides services. Score 1 for obvious non-LPs (e.g., CRE brokerages, lenders).

  DEFAULT: Organizations typed as "Asset Manager" or "RIA/FIA" should default to 1–3 unless
  there is specific evidence of external fund allocations (acting as an LP). Managing assets
  for others is GP behavior.

COMPONENT B: Private Credit Allocation (30% of D1)
Evidence of allocations to private credit, private debt, direct lending, or senior secured funds.
  9–10 = Documented allocations to private credit/debt funds specifically.
  7–8  = Allocates to alternatives broadly, credit allocation likely but not confirmed.
  5–6  = Invests in alternatives but no specific credit/debt evidence.
  3–4  = No alternatives program or only equity-focused.
  1–2  = No investment program or not an LP. Score 1 if not an LP.

COMPONENT C: Sustainability/Impact Mandate (30% of D1)
ESG, impact, sustainability, climate, or responsible investing in their INVESTMENT mandate.
  9–10 = Explicit impact/ESG investment policy with climate or sustainability focus.
         Invests specifically in climate mitigation, clean energy, or sustainable real assets.
  7–8  = Formal ESG/RI policy that governs investment decisions. May be a signatory to PRI,
         ICCR, or similar. Impact considerations are structural, not just screening.
  5–6  = Some ESG awareness (negative screens, ESG reporting) but not core to mandate.
  3–4  = No public sustainability mandate for investments. May have corporate sustainability
         but it doesn't drive capital allocation.
  1–2  = No sustainability connection or not an LP.

IMPORTANT for foundations/endowments/pensions: Look beyond their charitable MISSION to their
INVESTMENT policies. A cancer research foundation might have an impact-focused endowment —
or it might invest purely for returns. Score based on investment mandate evidence, not mission.

Calculate: D1 = (A × 0.40) + (B × 0.30) + (C × 0.30)

═══════════════════════════════════════════════════════════════
DIMENSION 3: HALO & STRATEGIC VALUE
═══════════════════════════════════════════════════════════════
Question: If PaceZero publicly names this organization as a Fund II LP, how much does
that announcement strengthen PaceZero's credibility and make future fundraising easier?

This is NOT about how much money they bring. A $500M foundation with a famous name
outscores a $5B pension that insists on anonymity.

CONTEXT: PaceZero is a Toronto-based firm whose LP base and deal flow span the US and
Canada. Their existing LP (The Atmospheric Fund) is a Toronto climate investor. Halo value
should be assessed primarily through the lens of SUSTAINABILITY/IMPACT INVESTING circles
in the US and Canada — this is the community where PaceZero's reputation matters most.

COMPONENT A: Brand Recognition (50% of D3)
How well-known is this organization PRIMARILY among sustainability/impact/climate investors,
and secondarily among private credit allocators and the broader institutional LP community?
Prioritize reputation within the impact/ESG investing community over generic institutional
brand recognition.
  9–10 = Globally iconic in sustainability/impact circles. Name recognition crosses
         geographies. Examples: Rockefeller Foundation, Ford Foundation, CPPIB.
  7–8  = Well-known within impact/ESG investing or climate finance circles specifically.
         Respected brand among sustainability-focused allocators.
         Examples: Schmidt Family Foundation, PBUCC, Heron Foundation.
  5–6  = Known within a niche (a city, a sector, a strategy type) but not broadly
         recognized in sustainability/impact circles.
  3–4  = Largely private or low-profile. Commitment wouldn't travel far in impact circles.
  1–2  = Anonymous, unknown, or explicitly privacy-seeking. No reputational lift.

COMPONENT B: Network Centrality (30% of D3)
Does this organization sit at the center of sustainability/impact investing networks
that PaceZero wants access to?
  - Membership in impact LP coalitions (GIIN, ICCR, PRI, Confluence Philanthropy,
    Ceres, Climate Action 100+, Net-Zero Asset Owner Alliance, etc.)
  - Co-investor relationships with other sustainability-focused allocators
  - Presence on climate/impact industry boards or advisory bodies
  - Ability to make warm introductions to other impact/ESG allocators in US/Canada

  9–10 = Anchor node in sustainability/impact networks PaceZero wants to access.
  7–8  = Active participant in 1–2 relevant impact/ESG networks. Known to make referrals.
  5–6  = Loosely affiliated. Some network presence but not a connector.
  3–4  = Isolated. No visible network memberships or co-investment history.
  1–2  = Actively private or siloed. No network signal found.

COMPONENT C: Signal Specificity (20% of D3)
Would this LP's commitment specifically validate PaceZero's thesis — sustainability +
private credit — rather than just "a fund got a commitment"?
The strongest signal is when a climate/sustainability-credentialed allocator endorses
a sustainability-focused credit strategy. Their domain expertise makes the endorsement
uniquely credible.
  9–10 = Direct endorsement of the specific thesis. A climate-focused or impact-first
         allocator choosing a sustainability-focused credit fund. Their expertise in
         climate/impact makes the signal uniquely credible to peer allocators.
  5–7  = General credibility. Commitment signals quality but not thesis-specific.
  1–4  = Commitment wouldn't be read as a specific endorsement of the strategy.

Calculate: D3 = (A × 0.50) + (B × 0.30) + (C × 0.20)

═══════════════════════════════════════════════════════════════
DIMENSION 4: EMERGING MANAGER FIT
═══════════════════════════════════════════════════════════════
Question: Does this LP have the structural willingness and practical ability to
commit capital to a Fund I or Fund II manager like PaceZero?

This is NOT about whether they like PaceZero specifically. It's about whether
their mandate, governance, and history allow them to back newer managers at all.

Key context: PaceZero's typical deal sizes are $3M–$20M, minimum meaningful LP
commitment is $1M–$5M, and they are fundraising for Fund II (no final close yet).

COMPONENT A: Structural Program (40% of D4)
Does this organization have a formal or stated program, policy, or mandate that
explicitly includes or encourages emerging manager allocations?
Look for: named "emerging manager program" or "first-time manager" language,
DEI-linked investment policies, board resolutions about manager diversity,
stated preference for backing managers at an early stage.
  9–10 = Explicit, named, active emerging manager program with documented commitments.
  7–8  = Stated preference or policy language without a formal named program.
  5–6  = Ambiguous — governance suggests flexibility but no explicit language found.
  3–4  = No evidence of structural openness; conservative mandate implied.
  1–2  = Explicit policy against unproven managers, or regulatory/fiduciary constraint
         that effectively prohibits it.

COMPONENT B: Behavioral Track Record (40% of D4)
Has this organization actually committed to Fund I or Fund II managers in the past,
regardless of whether they have a formal program?
Look for: public announcements of commitments to first-time or emerging managers,
portfolio disclosures with short-track-record funds, CIO quotes about backing new
managers, presence in emerging manager coalitions (ILPA EM working group, etc.).
  9–10 = Multiple documented commitments to Fund I/II managers, publicly verifiable.
  7–8  = At least one documented emerging manager commitment, or strong circumstantial
         evidence (e.g., CIO quoted as champion of new managers).
  5–6  = Suggestive but unconfirmed. Org type and size suggest it's possible.
  3–4  = No evidence of emerging manager backing; portfolio skews to established names.
  1–2  = Evidence of actively avoiding emerging managers or explicit statements
         about requiring established track records.

COMPONENT C: Check Size Fit (20% of D4)
Can this LP write a check that is meaningful to PaceZero ($1M–$5M minimum)
without it being either too small to matter to them or too large for PaceZero?
  9–10 = AUM and org type suggest $1M–$10M checks are routine and practical.
         Typical for: smaller SFOs, boutique MFOs, smaller foundations.
  7–8  = Check size fit is plausible but requires some flexibility on their end.
  5–6  = Uncertain — insufficient AUM data, or org type is ambiguous.
  3–4  = Org likely requires minimum checks larger than PaceZero's fund can absorb,
         OR org is so small that a meaningful check would be impractical.
  1–2  = Structural mismatch. Large pension/insurance requiring $25M+ minimums,
         or HNWI whose typical ticket is well below $500K.

CRITICAL RULES — apply before finalizing:
  1. A Fund of Funds is NOT automatically high on emerging manager fit — many FoFs
     only back established managers. Look for explicit evidence.
  2. Large pensions (AUM > $10B) default to 3–4 on Component A unless there is
     explicit evidence of an emerging manager program.
  3. SFOs and smaller foundations default to 5–6 on Component A in the absence
     of information, because governance is flexible enough to allow it.
  4. If AUM data is unavailable, score Component C at 5 and flag LOW CONFIDENCE.
  5. If D1 scores 1–2 (not an LP), D4 must also score 1–2.

Calculate: D4 = (A × 0.40) + (B × 0.40) + (C × 0.20)

═══════════════════════════════════════════════════════════════
SCORING INSTRUCTIONS
═══════════════════════════════════════════════════════════════
1. Score each sub-component (1–10) with evidence-based reasoning.
2. Calculate each dimension composite using the weights above.
3. Round composites to one decimal place.
4. If insufficient public info for a sub-component, assign 3 and flag LOW confidence.
5. Use the FULL 1–10 range. Do NOT cluster everything at 4–6.

OUTPUT FORMAT (strict JSON):
{{
    "d1_a_lp_status": <1-10>,
    "d1_a_reasoning": "<2-3 sentences>",
    "d1_b_credit": <1-10>,
    "d1_b_reasoning": "<2-3 sentences>",
    "d1_c_sustainability": <1-10>,
    "d1_c_reasoning": "<2-3 sentences>",
    "sector_fit_score": <weighted D1 composite>,
    "sector_fit_reasoning": "<1 sentence overall summary>",
    "d1_confidence": "HIGH | MEDIUM | LOW",

    "d3_a_brand": <1-10>,
    "d3_a_reasoning": "<2-3 sentences>",
    "d3_b_network": <1-10>,
    "d3_b_reasoning": "<2-3 sentences>",
    "d3_c_specificity": <1-10>,
    "d3_c_reasoning": "<2-3 sentences>",
    "halo_score": <weighted D3 composite>,
    "halo_reasoning": "<1 sentence overall summary>",
    "d3_confidence": "HIGH | MEDIUM | LOW",

    "d4_a_structural": <1-10>,
    "d4_a_reasoning": "<2-3 sentences>",
    "d4_b_track_record": <1-10>,
    "d4_b_reasoning": "<2-3 sentences>",
    "d4_c_checksize": <1-10>,
    "d4_c_reasoning": "<2-3 sentences>",
    "emerging_manager_score": <weighted D4 composite>,
    "emerging_manager_reasoning": "<1 sentence overall summary>",
    "d4_confidence": "HIGH | MEDIUM | LOW",
    "d4_red_flags": ["<any disqualifying signals, e.g. explicit no-emerging-manager policy>"],

    "confidence_note": "<what key information was missing, if any>"
}}"""


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
