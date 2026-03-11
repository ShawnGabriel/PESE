from dataclasses import dataclass, field

from pese.config import TOKEN_COSTS, WEB_SEARCH_COST_PER_CALL, WEB_SEARCH_CONTENT_TOKENS_PER_CALL


@dataclass
class CostTracker:
    """Tracks API token usage and estimated costs across a pipeline run.

    Accounts for three cost components:
      1. Input/output tokens at model rates
      2. Web search tool call fees ($0.01 per web_search_call)
      3. Web search content tokens (fixed 8k block per call for gpt-4o-mini)
    """
    calls: list[dict] = field(default_factory=list)

    def record(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        purpose: str = "",
        web_search_calls: int = 0,
    ):
        costs = TOKEN_COSTS.get(model, TOKEN_COSTS["gpt-4o-mini"])

        token_cost = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000

        search_call_cost = web_search_calls * WEB_SEARCH_COST_PER_CALL
        search_token_cost = (
            web_search_calls * WEB_SEARCH_CONTENT_TOKENS_PER_CALL * costs["input"]
        ) / 1_000_000

        cost_usd = token_cost + search_call_cost + search_token_cost

        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "web_search_calls": web_search_calls,
            "cost_usd": cost_usd,
            "purpose": purpose,
        })
        return cost_usd

    @property
    def total_cost(self) -> float:
        return sum(c["cost_usd"] for c in self.calls)

    @property
    def total_input_tokens(self) -> int:
        return sum(c["input_tokens"] for c in self.calls)

    @property
    def total_output_tokens(self) -> int:
        return sum(c["output_tokens"] for c in self.calls)

    @property
    def total_web_search_calls(self) -> int:
        return sum(c.get("web_search_calls", 0) for c in self.calls)

    @property
    def total_calls(self) -> int:
        return len(self.calls)

    def summary(self) -> dict:
        num_orgs = max(1, self.total_calls // 2)
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_web_search_calls": self.total_web_search_calls,
            "total_cost_usd": round(self.total_cost, 4),
            "cost_per_org": round(self.total_cost / num_orgs, 4),
        }

    def projected_cost(self, num_orgs: int) -> float:
        """Estimate cost for a larger run based on observed per-org cost."""
        if self.total_calls == 0:
            return 0.0
        actual_orgs = max(1, self.total_calls // 2)
        cost_per_org = self.total_cost / actual_orgs
        return round(cost_per_org * num_orgs, 4)
