import abc
import time
import numpy as np
import pandas as pd

from domain.portfolio.iportfolio import PortfolioInterface
from domain.strategies.istrategy import StrategyInterface
from domain.signals.risk_return_signals import RiskReturnSignals 
from domain.signals.moving_average_signals import MovingAverageSignals
from domain.signals.volatility_forecasting_signals import VolatilityForecastingSignals
from domain.signals.mean_reversion_signals import MeanReversionSignals
from domain.signals.momentum_signals import MomentumSignals
from domain.signals.black_litterman_signal import BlackLittermanSignal
from domain.machine_learning.cross_sectional_model import CrossSectionalModel 
from domain.machine_learning.feature_builder import FeatureBuilder
from domain.signals.machine_learning_signals import MLPredictorSignal, MLPredictorSignalsState
from models.rebalance_problem import RebalanceProblem
from models.signals_config import SignalsConfig
from models.backtest_run import BacktestRun
from simulation.market_state import MarketState
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
                 strategy: StrategyInterface,
                 market_state: MarketState,
                 signals_config: SignalsConfig,
                 benchmark: pd.Series):
        self.portfolio = portfolio
        self.strategy = strategy
        self.market_state = market_state
        self.signals_config = signals_config
        self.benchmark = benchmark
        self.ml_signals_config = signals_config.ml_signals_config if signals_config is not None else None
        if self.ml_signals_config is not None:
            self.feature_builder = FeatureBuilder(
                self.market_state,
                self.benchmark,
                self.market_state.market_frequency,
                self.ml_signals_config.features
            )
            self.feature_builder.precompute(self.ml_signals_config.horizon)
            self.cs_model = CrossSectionalModel(self.ml_signals_config)
            self.ml_signals_state = MLPredictorSignalsState(
                self.ml_signals_config,
                self.feature_builder,
                self.cs_model
            )
            self.ml_signals = MLPredictorSignal(
                self.market_state, 
                self.signals_config, 
                self.ml_signals_config, 
                self.ml_signals_state
            )

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
            self.market_state.prices.index, 
            self.market_state.prices.columns, 
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

            current_returns = self.market_state.returns.iloc[cursor]

            prev_weights = self.portfolio.drift(prev_weights, current_returns, cursor)
            if cursor < self.market_state.lookback_window:
                continue

            if self.ml_signals_config is not None:
                ml_warmup = self.ml_signals_config.training_window + self.ml_signals_config.horizon
                if cursor >= ml_warmup:
                    self.ml_signals_state.update(cursor, self.market_state.current_date())

            if not self._is_rebalance_step(cursor):
                continue

            signals = self._build_signals(self.market_state, self.signals_config, prev_weights)
            target_weights = self.strategy.rebalance(signals, prev_weights)
            self.portfolio.apply(target_weights, prev_weights, cursor)
            prev_weights = target_weights

        print(f"Backtest duration: {time.time() - start_time} seconds")
        return BacktestRun(
            portfolio=self.portfolio,
            scores_history=self.ml_signals_state.scores_history if self.ml_signals_config is not None else {},
            fwd_returns_history=self.ml_signals_state.fwd_returns_history if self.ml_signals_config is not None else {}
        )

    def _is_rebalance_step(self, step):
        return step % self.rebalance_every == 0
    
    def _get_steps(self, freq_param):
        key = (self.market_state.market_frequency, freq_param)
        return FREQ_TO_STEPS.get(key, 1)
    
    def _build_signals(self, 
                       market_state: MarketState, 
                       signals_config: SignalsConfig, 
                       current_weights: np.ndarray) -> dict:
        if self.signals_config is None:
            return {}
        
        ml_state = getattr(self, "ml_signals_state", None)
        return {
            "risk_return": RiskReturnSignals(market_state, signals_config),
            "mean_reversion": MeanReversionSignals(market_state, signals_config),
            "moving_average": MovingAverageSignals(market_state, signals_config),
            "volatility_forecast": VolatilityForecastingSignals(market_state, signals_config),
            "momentum": MomentumSignals(market_state, signals_config),
            "black_litterman": BlackLittermanSignal(market_state, signals_config, ml_state, current_weights),
            "ml_cross_sectional": self.ml_signals if self.ml_signals_config is not None else None
        } 