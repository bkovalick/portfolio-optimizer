import abc
from domain.strategies.fixed_weight_strategy import FixedWeightStrategy
from domain.strategies.equal_weight_strategy import EqualWeightStrategy
from domain.strategies.systematic_strategy import SystematicStrategy
from domain.strategies.pairs_trading_strategy import PairsTradingStrategy
from domain.optimizers.optimizer import Optimizer
from models.rebalance_problem import RebalanceProblem

class BaseStrategyFactory(abc.ABC):
    """Interface for optimizer factories."""
    @abc.abstractmethod
    def create_strategy(self, rebalance_problem: RebalanceProblem, optimizer: Optimizer):
        ...

class StrategyFactory(BaseStrategyFactory):

    _strategies = {
        "fwp_strategy": FixedWeightStrategy,
        "ewp_strategy": EqualWeightStrategy,
        "systematic_strategy": SystematicStrategy,
        "pairs_trading_strategy": PairsTradingStrategy
    }

    """Concrete implementation of a strategy factory."""
    @classmethod
    def create_strategy(cls, 
                        rebalance_problem: RebalanceProblem, 
                        optimizer: Optimizer=None):
        strategy = cls._strategies.get(rebalance_problem.strategy_type)
        if strategy:
            return strategy(rebalance_problem, optimizer)
        else:
            raise ValueError(f"Unknown strategy type: {rebalance_problem.strategy_type}")