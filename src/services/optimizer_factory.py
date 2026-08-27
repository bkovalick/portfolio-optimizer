import logging

from domain.optimizers.optimizer import Optimizer
from domain.optimizers.base_optimizer import BaseOptimizer
from domain.signals.signals import Signals
from models.rebalance_context import RebalanceContext
from models.rebalance_solution import RebalanceSolution

logger = logging.getLogger(__name__)

class FixedWeightOptimizer(BaseOptimizer):
    def __init__(self):
        super().__init__()

    def optimize(self, 
                 rebalance_context: RebalanceContext,
                 active_signal: Signals = None) -> RebalanceSolution:
        return RebalanceSolution(
            target_weights=rebalance_context.current_weights,
            sell_allocations={},
            realized_tax_cost=0.0,
            tracking_error=0.0
        )

class OptimizerFactory:

    _optimizers = {
        "portfolio_optimizer": Optimizer,
        "fwp_optimizer": FixedWeightOptimizer
    }

    """Concrete implementation of a optimizer factory."""
    @classmethod
    def create_optimizer(cls, optimizer_type):
        logger.info("Creating optimizer for type %s", optimizer_type)
        optimizer = cls._optimizers.get(optimizer_type)
        if optimizer_type == "None":
            logger.debug("Using fixed-weight optimizer for type None")
            return FixedWeightOptimizer()

        if optimizer:
            logger.debug("Instantiated optimizer class %s", optimizer.__name__)
            return optimizer()
        else:
            logger.warning("Unknown optimizer type requested: %s", optimizer_type)
            raise ValueError(f"Unknown optimizer type: {optimizer_type}")