import numpy as np
from dataclasses import dataclass

from domain.portfolio.portfolio import Portfolio
from domain.portfolio.tax_lot_ledger import TaxLotLedger
from models.rebalance_problem import RebalanceProblem

@dataclass(frozen=True)
class RebalanceContext:
    cursor: int
    signals: dict
    initial_weights: dict
    current_weights: np.ndarray
    investment_universe: list
    rebalance_problem: RebalanceProblem
    portfolio: Portfolio
    tax_lot_ledger: TaxLotLedger = None