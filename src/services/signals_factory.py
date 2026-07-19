from typing import Any, Dict
import pandas as pd
from datetime import datetime

from domain.signals.risk_return_signals import RiskReturnSignals 
from domain.signals.moving_average_signals import MovingAverageSignals
from domain.signals.volatility_forecasting_signals import VolatilityForecastingSignals
from domain.signals.mean_reversion_signals import MeanReversionSignals
from domain.signals.momentum_signals import MomentumSignals
from domain.signals.black_litterman_signal import BlackLittermanSignal
from domain.signals.pairs_trading_signal import PairsTradingSignal
from domain.machine_learning.cross_sectional_model import CrossSectionalModel 
from domain.machine_learning.feature_builder import FeatureBuilder
from domain.signals.machine_learning_signals import MLPredictorSignal, MLPredictorSignalsState
from domain.signals.signals import Signals
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

class SignalFactory:
    def __init__(self, 
                 signals_config: SignalsConfig,
                 market_state: MarketState,
                 benchmark: pd.Series):
        self._signals_config = signals_config
        self._market_state = market_state
        self._benchmark = benchmark
        self._ml_signals_config = signals_config.ml_signals_config if signals_config is not None else None
        self._signals: Dict[str, Signals] = {}

        if signals_config is None:
            return

        if self._ml_signals_config is not None:
            self._feature_builder = FeatureBuilder(
                self._market_state,
                self._benchmark,
                self._market_state.market_frequency,
                self._ml_signals_config.features
            )
            self._feature_builder.precompute(self._ml_signals_config.horizon)
            self._cs_model = CrossSectionalModel(self._ml_signals_config)
            self._ml_signals_state = MLPredictorSignalsState(
                self._ml_signals_config,
                self._feature_builder,
                self._cs_model
            )
            self._signals["ml_cross_sectional"] = MLPredictorSignal(
                self._market_state, 
                self._signals_config, 
                self._ml_signals_config, 
                self._ml_signals_state
            )

        self._signals["risk_return"] = RiskReturnSignals(market_state, self._signals_config)
        self._signals["mean_reversion"] = MeanReversionSignals(market_state, self._signals_config)
        self._signals["moving_average"] = MovingAverageSignals(market_state, self._signals_config)
        self._signals["volatility_forecast"] = VolatilityForecastingSignals(market_state, self._signals_config)
        self._signals["momentum"] = MomentumSignals(market_state, self._signals_config)
        self._signals["black_litterman"] = BlackLittermanSignal(
            market_state, signals_config,
            self._signals_config and self._ml_signals_config and self._ml_signals_state,
        )

        if signals_config.pairs_trading is not None:
            self._signals["pairs_trading"] = PairsTradingSignal(
                market_state, signals_config.pairs_trading
            )

    def update(self, 
               cursor: int, 
               as_of_date: datetime) -> None:
        """Update the signals state based on the current market state."""
        for signal in self._signals.values():
            if hasattr(signal, "update"):
                signal.update(cursor, as_of_date)

    def get_diagnostics(self) -> Dict[str, Any]:
        """Get diagnostics information from all signals."""
        diagnostics: Dict[str, Any] = {}
        for signal in self._signals.values():
            if hasattr(signal, "get_diagnostics"):
                diagnostics.update(signal.get_diagnostics())
        return diagnostics

    def build_signals(self) -> Dict[str, Any]:
        return self._signals