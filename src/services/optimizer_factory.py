import numpy as np
from domain.optimizers.optimizer import Optimizer
from domain.optimizers.base_optimizer import BaseOptimizer
from models.rebalance_problem import RebalanceProblem

class FixedWeightOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, 
                 rebalance_problem: RebalanceProblem, 
                 current_weights: np.ndarray = None):
        return current_weights

class OptimizerFactory:

    _optimizers = {
        "portfolio_optimizer": Optimizer,
        "fwp_optimizer": FixedWeightOptimizer
    }

    """Concrete implementation of a optimizer factory."""
    @classmethod
    def create_optimizer(cls, optimizer_type):
        optimizer = cls._optimizers.get(optimizer_type)
        if optimizer == "None":
            return FixedWeightOptimizer()

        if optimizer:
            return optimizer()
        else:
            raise ValueError(f"Unknown optimizer type: {optimizer_type}")