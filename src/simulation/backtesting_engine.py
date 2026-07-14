import abc
import time
import numpy as np
import pandas as pd

from domain.portfolio.iportfolio import PortfolioInterface
from domain.strategies.base_strategy import BaseStrategy
from models.rebalance_problem import RebalanceProblem
from models.backtest_run import BacktestRun
from simulation.market_state import MarketState
from services.signals_factory import SignalFactory
from utils.rebalance_steps import FREQ_TO_STEPS

class BacktestingEngineInterface(abc.ABC):
    """Interface for backtesting engines."""
    @abc.abstractmethod
    def run_backtest(self, rebalance_problem: RebalanceProblem):
        raise NotImplementedError("Must implement run_backtest in derived classes.")

class BacktestingEngine(BacktestingEngineInterface):
    """Concrete implementation of a backtesting engine."""
    def __init__(self, 
                 portfolio: PortfolioInterface, 
                 strategy: BaseStrategy,
                 market_state: MarketState,
                 signal_factory: SignalFactory,
                 benchmark: pd.Series):
        self.portfolio = portfolio
        self.strategy = strategy
        self.market_state = market_state
        self.benchmark = benchmark
        self.signals_factory = signal_factory

    def run_backtest(self, rebalance_problem: RebalanceProblem):
        """Run backtest on the given rebalance problem."""
        print("Running backtest...")
        start_time = time.time()
        self.rebalance_every = self._get_steps(rebalance_problem.rebalance_frequency)
        tickers = rebalance_problem.investment_universe
        initial_weights = np.array([
            rebalance_problem.initial_weights.get(ticker, 0.0) 
            for ticker in tickers
        ])
        self.portfolio.initialize(
            self.market_state.investment_prices.index, 
            self.market_state.investment_prices.columns, 
            initial_weights
        )
        
        prev_weights = np.array(initial_weights)
        current_year = None
        while self.market_state.has_next():
            self.market_state.advance()

            cursor = self.market_state.cursor
            
            date = self.market_state.current_date()
            if date.year != current_year:
                current_year = date.year
                print(f"Processing {current_year}...")

            current_returns = self.market_state.investment_returns.iloc[cursor]

            prev_weights = self.portfolio.drift(prev_weights, current_returns, cursor)
            if cursor < self.market_state.lookback_window:
                continue

            self.signals_factory.update(cursor, self.market_state.current_date())

            if not self._is_rebalance_step(cursor):
                continue

            signals = self.signals_factory.build_signals(self.market_state, prev_weights)

            target_weights = self.strategy.rebalance(signals, prev_weights)
            self.portfolio.apply(target_weights, prev_weights, cursor)
            prev_weights = target_weights

        print(f"Backtest duration: {time.time() - start_time} seconds")
        return self._build_backtest_run(rebalance_problem)

    def _is_rebalance_step(self, step):
        return step % self.rebalance_every == 0
    
    def _get_steps(self, freq_param):
        key = (self.market_state.market_frequency, freq_param)
        return FREQ_TO_STEPS.get(key, 1)

    # place a get diagnostic method in the base of the strategy classes. Override where necessary    
    def _build_backtest_run(self, rebalance_problem: RebalanceProblem) -> BacktestRun:
        if hasattr(self.strategy, "pairs_cache") and rebalance_problem.monitoring_type == "pairs":
            pairs_cache = self.strategy.pairs_cache
            return BacktestRun(
                portfolio=self.portfolio,
                pairs_cache=pairs_cache
            )

        ml_signals_state = getattr(self, "ml_signals_state", None)
        scores_history = ml_signals_state.scores_history if ml_signals_state is not None else None
        fwd_returns_history = ml_signals_state.fwd_returns_history if ml_signals_state is not None else None
        return BacktestRun(
            portfolio=self.portfolio,
            fwd_history=fwd_returns_history,
            scores_history=scores_history
        )
