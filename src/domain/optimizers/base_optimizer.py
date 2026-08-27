import abc

from models.rebalance_context import RebalanceContext
from domain.signals.signals import Signals

class BaseOptimizer(abc.ABC):
    @abc.abstractmethod
    def optimize(self, rebalance_context: RebalanceContext, active_signal: Signals = None):
        ...