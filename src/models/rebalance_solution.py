from dataclasses import dataclass
import pandas as pd

@dataclass(frozen=True)
class RebalanceSolution:
    target_weights: pd.Series          # ticker -> weight, for portfolio/reporting
    sell_allocations: dict[int, float]  # lot_id -> sell_fraction, for ledger
    realized_tax_cost: float            # realized, for diagnostics/objective tracking
    tracking_error: float               # realized, for diagnostics	