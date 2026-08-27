from dataclasses import dataclass, field
from domain.portfolio.portfolio import Portfolio
from typing import Optional

@dataclass
class BacktestRun:
    portfolio: Portfolio
    fwd_history: Optional[dict] = field(default_factory=dict)
    scores_history: Optional[dict] = field(default_factory=dict)
    pairs_cache: Optional[list] = field(default_factory=list)