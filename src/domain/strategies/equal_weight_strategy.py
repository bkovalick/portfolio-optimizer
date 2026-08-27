import numpy as np
import pandas as pd

from domain.strategies.base_strategy import BaseStrategy
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

class EqualWeightStrategy(BaseStrategy):
    """Equal weight strategy.

    Allocates 1/N weight to each asset regardless of signals or market
    conditions. Useful as a simple benchmark.
    """
    def __init__(self, 
                 rebalance_problem: RebalanceProblem, 
                 optimizer: Optimizer = None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, rebalance_context: RebalanceContext) -> RebalanceSolution:
        """Return equal weights across all assets."""
        n = len(rebalance_context.current_weights)
        equal_weights = np.full(n, 1.0 / n)
        return RebalanceSolution(
            target_weights=pd.Series(equal_weights, index=rebalance_context.investment_universe),
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )