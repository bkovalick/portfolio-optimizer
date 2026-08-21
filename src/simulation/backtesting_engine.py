import abc
import logging
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


logger = logging.getLogger(__name__)

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
        logger.info(
            "Starting backtest for %s assets at rebalance frequency %s",
            len(rebalance_problem.investment_universe),
            rebalance_problem.rebalance_frequency,
        )
        print("Starting backtest for %s assets at rebalance frequency %s" % (
            len(rebalance_problem.investment_universe),
            rebalance_problem.rebalance_frequency,
        ))
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
                logger.info("Processing backtest year %s", current_year)
                print("Processing backtest year %s" % current_year)

            current_returns = self.market_state.investment_returns.iloc[cursor]

            prev_weights = self.portfolio.drift(prev_weights, current_returns, cursor)
            if cursor < self.market_state.lookback_window:
                continue

            self.signals_factory.update(cursor, self.market_state.current_date())

            if not self._is_rebalance_step(cursor):
                continue

            signals = self.signals_factory.build_signals()
            logger.debug("Rebalance step reached at %s (cursor=%s)", date, cursor)

            target_weights = self.strategy.rebalance(signals, prev_weights)
            self.portfolio.apply(target_weights, prev_weights, cursor)
            prev_weights = target_weights

        logger.info("Backtest completed in %.2f seconds", time.time() - start_time)
        print("Backtest completed in %.2f seconds" % (time.time() - start_time))
        return self._build_backtest_run()

    def _is_rebalance_step(self, step):
        return step % self.rebalance_every == 0
    
    def _get_steps(self, freq_param):
        key = (self.market_state.market_frequency, freq_param)
        return FREQ_TO_STEPS.get(key, 1)
    
    def _build_backtest_run(self) -> BacktestRun:
        diagnostics = self.strategy.get_diagnostics() if hasattr(self.strategy, "get_diagnostics") else {}

        if hasattr(self.signals_factory, "get_diagnostics"):
            diagnostics.update(self.signals_factory.get_diagnostics())

        return BacktestRun(
            portfolio=self.portfolio,
            **diagnostics
        )    
