import numpy as np
import pandas as pd

from domain.strategies.base_strategy import BaseStrategy
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

class FixedWeightStrategy(BaseStrategy):
    """Fixed weight strategy.

    Always returns the initial_weights defined in the rebalance problem,
    drifting back to the target allocation on every rebalance date.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer: Optimizer = None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        """Calculate rebalance weights"""
        tickers = rebalance_context.investment_universe
        target_weights = np.array([
            rebalance_context.initial_weights.get(ticker, 0.0)
            for ticker in tickers
        ])
        return RebalanceSolution(
            target_weights=pd.Series(target_weights, index=tickers),
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )