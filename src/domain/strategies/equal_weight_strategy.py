from domain.strategies.base_strategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem
import numpy as np

class EqualWeightStrategy(StrategyInterface):
    """Equal weight strategy.

    Allocates 1/N weight to each asset regardless of signals or market
    conditions. Useful as a simple benchmark.
    """
    def __init__(self, rebalance_problem: RebalanceProblem, optimizer=None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, signals: dict, current_weights: np.ndarray) -> np.ndarray:
        """Return equal weights across all assets."""
        n = len(current_weights)
        return np.full(n, 1.0 / n)