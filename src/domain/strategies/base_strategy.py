import abc
import numpy as np
from models.rebalance_problem import RebalanceProblem
from domain.signals.signals import Signals
from domain.optimizers.optimizer import Optimizer

class StrategyInterface(abc.ABC):
    """Base interface for all portfolio strategies.
    """
    def __init__(self, rebalance_problem: RebalanceProblem, optimizer=None):
        self.rebalance_problem = rebalance_problem
        self.optimizer = optimizer or Optimizer()

    @abc.abstractmethod
    def rebalance(self, signals, current_weights):
        raise NotImplementedError("Derived classes must implement 'rebalance' method")
    
    def _apply_vol_targeting(self, 
                             risk_return_signals: Signals, 
                             optimized_weights: np.ndarray) -> np.ndarray:
        """ Scale non-cash weights so the portfolio hits vol_target.
        
            Computes the ratio of target vol to realized vol and scales all
            non-cash weights by that factor (capped at vol_max_leverage).
            Cash absorbs the residual to keep weights summing to 1.
        """        
        vol_target = getattr(self.rebalance_problem, "vol_target", None)
        vol_max_leverage = getattr(self.rebalance_problem, "vol_max_leverage", None)
        realized_vol = risk_return_signals.portfolio_vol(optimized_weights)
        scaling_factor = min(vol_target / realized_vol, vol_max_leverage) if realized_vol > 0 else 1.0

        adjusted_weights = optimized_weights.copy()
        adjusted_weights[:-1] = optimized_weights[:-1] * scaling_factor
        adjusted_weights[-1] = 1.0 - np.sum(adjusted_weights[:-1])
        return adjusted_weights