from dataclasses import dataclass, field
from domain.portfolio.iportfolio import PortfolioInterface
from typing import Optional

@dataclass
class BacktestRun:
    portfolio: PortfolioInterface
    fwd_history: Optional[dict] = field(default_factory=dict)
    scores_history: Optional[dict] = field(default_factory=dict)
    pairs_cache: Optional[list] = field(default_factory=list)