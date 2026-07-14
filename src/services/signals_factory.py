import numpy as np
import pandas as pd
from datetime import datetime
from typing import Any, Dict, Optional

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

        self.feature_builder: Optional[FeatureBuilder] = None
        self._cs_model: Optional[CrossSectionalModel] = None
        self._ml_signals_state: Optional[MLPredictorSignalsState] = None
        self._ml_signals: Optional[MLPredictorSignal] = None

        if self._ml_signals_config is not None:
            self.feature_builder = FeatureBuilder(
                self._market_state,
                self._benchmark,
                self._market_state.market_frequency,
                self._ml_signals_config.features
            )
            self.feature_builder.precompute(self._ml_signals_config.horizon)
            self._cs_model = CrossSectionalModel(self._ml_signals_config)
            self._ml_signals_state = MLPredictorSignalsState(
                self._ml_signals_config,
                self.feature_builder,
                self._cs_model
            )
            self._ml_signals = MLPredictorSignal(
                self._market_state, 
                self._signals_config, 
                self._ml_signals_config, 
                self._ml_signals_state
            )

    def update(self, 
               cursor: int, 
               as_of_date: datetime) -> None:
        if self._ml_signals_config is not None:
            ml_warmup = self._ml_signals_config.training_window + self._ml_signals_config.horizon
            if cursor >= ml_warmup:
                self._ml_signals_state.update(cursor, as_of_date)

    def build_signals(self, 
                      market_state: MarketState, 
                      current_weights: np.ndarray) -> Dict[str, Any]:
        if self._signals_config is None:
            return {}
        
        ml_state = self._ml_signals_state
        pairs_signal = PairsTradingSignal(market_state, self._signals_config.pairs_trading) \
            if self._signals_config.pairs_trading is not None else None

        return {
            "risk_return": RiskReturnSignals(market_state, self._signals_config),
            "mean_reversion": MeanReversionSignals(market_state, self._signals_config),
            "moving_average": MovingAverageSignals(market_state, self._signals_config),
            "volatility_forecast": VolatilityForecastingSignals(market_state, self._signals_config),
            "momentum": MomentumSignals(market_state, self._signals_config),
            "black_litterman": BlackLittermanSignal(market_state, self._signals_config, ml_state, current_weights),
            "ml_cross_sectional": self._ml_signals if self._ml_signals_config is not None else None,
            "pairs_trading": pairs_signal
        }