from domain.strategies.base_strategy import StrategyInterface
from models.rebalance_problem import RebalanceProblem
import numpy as np

class FixedWeightStrategy(StrategyInterface):
    """Fixed weight strategy.

    Always returns the initial_weights defined in the rebalance problem,
    drifting back to the target allocation on every rebalance date.
    """
    def __init__(self, rebalance_problem: RebalanceProblem, optimizer=None):
        super().__init__(rebalance_problem, optimizer)

    def rebalance(self, signals: dict, current_weights: np.ndarray) -> np.ndarray:
        """Calculate rebalance weights"""
        tickers = self.rebalance_problem.investment_universe
        return np.array([
            self.rebalance_problem.initial_weights.get(ticker, 0.0) 
            for ticker in tickers
        ])