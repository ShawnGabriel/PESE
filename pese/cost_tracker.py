from dataclasses import dataclass, field

from pese.config import TOKEN_COSTS


@dataclass
class CostTracker:
    """Tracks API token usage and estimated costs across a pipeline run."""
    calls: list[dict] = field(default_factory=list)

    def record(self, model: str, input_tokens: int, output_tokens: int, purpose: str = ""):
        costs = TOKEN_COSTS.get(model, TOKEN_COSTS["gpt-4o-mini"])
        cost_usd = (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000
        self.calls.append({
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
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
    def total_calls(self) -> int:
        return len(self.calls)

    def summary(self) -> dict:
        return {
            "total_calls": self.total_calls,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "cost_per_org": round(self.total_cost / max(1, self.total_calls) * 2, 4),
        }

    def projected_cost(self, num_orgs: int) -> float:
        """Estimate cost for a larger run based on observed per-org cost."""
        if self.total_calls == 0:
            return 0.0
        cost_per_call = self.total_cost / self.total_calls
        calls_per_org = 2  # enrichment + scoring
        return round(cost_per_call * calls_per_org * num_orgs, 4)
