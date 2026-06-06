import abc

class BaseOptimizer(abc.ABC):
    @abc.abstractmethod
    def optimize(self, rebalance_problem, current_weights=None):
        ...