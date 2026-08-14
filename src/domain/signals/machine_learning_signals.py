import logging
from datetime import datetime

import numpy as np
import pandas as pd

from domain.signals.risk_return_signals import RiskReturnSignals
from domain.machine_learning.return_predictor import ReturnPredictor
from domain.machine_learning.feature_builder import FeatureBuilder
from models.signals_config import SignalsConfig
from models.machine_learning_config import MachineLearningConfig
from simulation.market_state import MarketState


logger = logging.getLogger(__name__)

class MLPredictorSignalsState:
    """
       Holds the state of the machine learning predictor signals, including cached scores, 
       training history, and forward returns.
    """
    def __init__(self, 
                 ml_config: MachineLearningConfig, 
                 feature_builder: FeatureBuilder, 
                 model: ReturnPredictor):
        self.ml_config = ml_config
        self.feature_builder = feature_builder
        self.model = model
        self.cadence = ml_config.rebal_cadence
        self.cached_scores = None
        self.last_trained = None
        self.training_window = ml_config.training_window
        self.horizon = ml_config.horizon
        self.sample_stride = ml_config.sample_stride
        self.scores_history = {}
        self.fwd_returns_history = {}
        self.coef_history = {}

    def update(self, cursor: int, as_of_date: datetime):
        """
        Retrains the model on a rolling window of historical features and forward returns,
        then generates and caches predicted scores for the current date. Retraining is
        skipped if the configured cadence has not elapsed since the last training run.
        """
        if not self._should_retrain(cursor):
            return 

        logger.info("Retraining ML predictor at %s (cursor=%s)", as_of_date, cursor)
        
        train_end = cursor - self.horizon
        train_start = train_end - self.training_window
        if train_start < 0 or train_end <= 0:
            logger.warning(
                "Skipping ML retrain at %s due to insufficient history (train_start=%s, train_end=%s)",
                as_of_date,
                train_start,
                train_end,
            )
            return

        dates = self.feature_builder.prices.index
        train_dates = dates[train_start:train_end:self.sample_stride]

        X_list, y_list = [], []
        for date in train_dates:
            X_t = self.feature_builder.build(date)
            y_t = self.feature_builder.build_forward_returns(date, self.horizon)
            if X_t.empty or y_t.empty:
                continue
            X_list.append(X_t)
            y_list.append(y_t)

        if not X_list:
            logger.warning("Skipping ML retrain at %s because no training samples were built", as_of_date)
            return

        X_train = pd.concat(X_list)
        y_train = pd.concat(y_list)

        self.model.fit(X_train, y_train)
        self._coefficient_history(X_train, as_of_date)
        X_now = self.feature_builder.build(as_of_date)
        if X_now.empty:
            logger.warning("Skipping ML score generation at %s because current features are empty", as_of_date)
            return

        scores = self.model.predict(X_now)
        self.cached_scores = pd.Series(scores, index=X_now.index)
        self.scores_history[as_of_date] = self.cached_scores.copy()
        logger.info("Cached ML scores for %s assets at %s", len(self.cached_scores), as_of_date)

        for pred_date, pred_scores in list(self.scores_history.items()):
            if pred_date in self.fwd_returns_history:
                continue
            pred_idx = dates.get_loc(pred_date)
            if pred_idx + self.horizon <= cursor:
                fwd = self.feature_builder.build_forward_returns(pred_date, self.horizon)
                if not fwd.empty:
                    self.fwd_returns_history[pred_date] = fwd.copy()

        self.last_trained = cursor

    def _should_retrain(self, cursor: int) -> bool:
        if self.last_trained is None:
            return True
        return (cursor - self.last_trained) >= self.cadence
    
    def _coefficient_history(self, X_train: pd.DataFrame, as_of_date: datetime):
        if hasattr(self.model.model, 'coef_'):
            self.coef_history[as_of_date] = pd.Series(
                self.model.model.coef_,
                index=X_train.columns
            )
            logger.debug("Stored ML coefficients for %s features at %s", len(X_train.columns), as_of_date)
    
    @property
    def scores(self) -> pd.Series:
        if self.cached_scores is None:
            return None

        all_tickers = self.feature_builder.prices.columns
        return self.cached_scores.reindex(all_tickers)

class MLPredictorSignal(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_cfg: SignalsConfig,
                 ml_config: MachineLearningConfig,
                 predictor_state: MLPredictorSignalsState):
        super().__init__(market_state, signals_cfg)

        self._ml_config = ml_config
        self._predictor_state = predictor_state

    @property
    def _warmup(self) -> int:
        return self._ml_config.training_window + self._ml_config.horizon
    
    def update(self, cursor: int, as_of_date: datetime):
        if cursor >= self._warmup:
            self._predictor_state.update(cursor, as_of_date)

    def get_diagnostics(self):
        return {
            "scores_history": self._predictor_state.scores_history,
            "fwd_history": self._predictor_state.fwd_returns_history,
        }
                
    def mean_returns(self):
        if not self._ml_config.enabled:
            return super().mean_returns()
        if self._predictor_state.scores is None:
            return super().mean_returns()
        universe = self.market_state.investment_universe
        scores = self._predictor_state.scores.reindex(universe).to_numpy(dtype=float)
        if np.isnan(scores).any():
            logger.warning("ML scores contained %s NaNs; falling back for missing values", np.isnan(scores).sum())
            fallback = super().mean_returns()
            nan_mask = np.isnan(scores)
            scores[nan_mask] = fallback[nan_mask]
        return scores
