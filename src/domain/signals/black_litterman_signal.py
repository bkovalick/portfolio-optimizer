from domain.signals.risk_return_signals import RiskReturnSignals
from domain.signals.machine_learning_signals import MLPredictorSignalsState
from models.signals_config import SignalsConfig
from simulation.market_state import MarketState

from typing import Optional
import numpy as np
import pandas as pd

class BlackLittermanSignal(RiskReturnSignals):
    def __init__(self, 
                 market_state: MarketState, 
                 signals_config: SignalsConfig,
                 ml_state: Optional[MLPredictorSignalsState],
                 current_weights: np.ndarray):
        super().__init__(market_state, signals_config)
        self.ml_state = ml_state
        self.ml_signals_config = self.signals_config.ml_signals_config
        self.security_to_etf_map = self.market_state.security_to_etf_map
        self.investment_universe = self.market_state.investment_universe
        self.current_weights = current_weights
        self.use_ml = (
            self.ml_signals_config is not None
            and self.ml_signals_config.enabled
            and self.ml_state is not None
            and self.ml_state.scores is not None
        )         
        bl = getattr(self.signals_config, "black_litterman", None) or {}
        self.black_litterman = bl if bl else None
        self.tau = bl.get("tau", 0.05)
        self.delta = bl.get("delta", 2.5)
        self.view_direction = bl.get("view_direction", "momentum")

    def mean_returns(self) -> np.ndarray:
        """
        Returns the Black-Litterman posterior mean return vector. If no
        black_litterman config is present, falls back to the parent class (historical mean returns).
        """
        if self.black_litterman is None:
            return super().mean_returns()
        
        sigma = self.covariance_matrix()
        pi = self._compute_equilibrium_returns(sigma)
        P, Q, omega = self._build_views(sigma)
        if not np.any(P):
            return pi
        return self._compute_posterior(pi, sigma, P, Q, omega)
    
    def _compute_equilibrium_returns(self, sigma):
        """
        Computes the CAPM-implied equilibrium excess returns (pi) using reverse
        optimization: pi = delta * Sigma * w, where delta is the risk aversion
        coefficient and w is the current portfolio weight vector.
        """
        return self.delta * sigma @ self.current_weights

    def _build_views(self, sigma: np.ndarray):
        """
        Constructs the investor view matrices (P, Q, Omega) using a mean-reversion
        signal. Assets in the bottom quintile by recent returns are expected to
        outperform assets in the top quintile (losers beat winners). Returns:
          P     — (1 x N) pick matrix encoding the relative view.
          Q     — (1,) array of the expected return spread.
          Omega — (1 x 1) diagonal uncertainty matrix scaled by tau * P @ Sigma @ P'.
        """        
        ranked, expected_spread = self._get_ranked_scores()

        n = len(ranked)
        quintile = n // 5

        losers  = ranked <= quintile      # bottom 20%
        winners = ranked > n - quintile   # top 20%

        if self.security_to_etf_map is not None:
            P, Q = self._determine_etf_views(winners, losers, expected_spread)
        else:
            P = self._determine_view_direction(ranked, winners, losers)
            Q = np.array([expected_spread])

        omega_diag = np.diag(self.tau * P @ sigma @ P.T)
        omega = np.diag(np.maximum(omega_diag, 1e-8))
        return P, Q, omega

    def _compute_posterior(self, pi, sigma, P, Q, omega) -> np.ndarray:
        """
        Combines the equilibrium returns (pi) with the investor views (P, Q, Omega)
        using the Black-Litterman formula to produce a blended posterior mean vector:
          mu_BL = M @ (inv(tau*Sigma) @ pi + P' @ inv(Omega) @ Q)
        where M = inv(inv(tau*Sigma) + P' @ inv(Omega) @ P).
        """
        inv_tau = np.linalg.inv(self.tau * sigma)
        inv_omega = np.linalg.inv(omega)

        M = np.linalg.inv(
            inv_tau + P.T @ inv_omega @ P
        )
        return M @ (inv_tau @ pi + P.T @ inv_omega @ Q)
    
    def _get_ranked_scores(self):
        """
        Returns (ranked, expected_spread) used to construct the view matrix P.
        If ML scores are available and enabled, assets are ranked by model score
        and the ml_view_spread config value is used as the expected return spread.
        Otherwise falls back to ranking by short-term price returns over
        mean_reversion_window periods, using reversion_view as the spread.
        """
        if self.use_ml:
            scores = self.ml_state.scores

            if self.security_to_etf_map is not None:
                etf_scores = self._aggregate_to_etfs(scores)
                return etf_scores.rank(), self.black_litterman.get("ml_view_spread", 0.03)
            
            return scores.rank(), self.black_litterman.get("ml_view_spread", 0.03)

        window = getattr(self.signals_config, "mean_reversion_window", 4)
        short_returns = self.market_state.lookback_prices().pct_change(window, fill_method=None).iloc[-1]
        return short_returns.rank(), self.black_litterman.get("reversion_view", 0.03)
    
    def _aggregate_to_etfs(self, security_scores: pd.Series) -> pd.Series:
        """
        Aggregates security-level scores to ETF-level by averaging the scores of the constituent securities
        """
        etf_scores = {}
        for etf in self.investment_universe:
            constituents = [ s for s, mapped_etf in self.security_to_etf_map.items()
                            if mapped_etf == etf]
            if constituents and len(constituents) > 0:
                threshold = security_scores[constituents].quantile(0.80)
                top_n_scores = security_scores[constituents][security_scores[constituents] > threshold].mean()
                bottom_n_scores = security_scores[constituents][security_scores[constituents] <= threshold].mean()
                score = top_n_scores - bottom_n_scores
                if not pd.isna(score):
                    etf_scores[etf] = score

        return pd.Series(etf_scores)
    
    def _determine_view_direction(self, 
                                  ranked_scores: pd.Series, 
                                  winners: np.ndarray, 
                                  losers: np.ndarray) -> np.ndarray:
        """
        Builds the (1 x N) pick matrix P encoding a single long/short relative
        view based on the configured view_direction:
          "momentum"       — long winners, short losers (trend-following).
          "mean_reversion" — long losers, short winners (contrarian).
        Each leg is equally weighted and normalised so the row sums to zero.
        Defaults to mean_reversion if view_direction is unrecognised.
        """
        n_investment = len(self.investment_universe)
        P = np.zeros((1, n_investment))

        if winners.sum() == 0 or losers.sum() == 0:
            return P
        
        if self.security_to_etf_map is not None:
            pass
        for ticker in ranked_scores.index:
            idx = self.investment_universe.index(ticker)
            if losers.loc[ticker]:
                P[0, idx]  = -1 / losers.sum() if self.view_direction == "momentum" else 1 / losers.sum()
            elif winners.loc[ticker]:
                P[0, idx] =  1 / winners.sum() if self.view_direction == "momentum" else -1 / winners.sum()
        return P
    
    def _determine_etf_views(self,
                             winners: np.ndarray, 
                             losers: np.ndarray,
                             expected_spread: float):
        """
        When securities are mapped to ETFs, we construct views at the ETF level. 
        For a momentum view, we expect ETFs with a majority of winning constituents 
        to outperform those with a majority of losing constituents, and vice versa for mean reversion. 
        The view matrix P is constructed accordingly, with each selected ETF equally weighted within 
        the winners and losers groups.
        """
        n_investment = len(self.investment_universe)
        if winners.sum() == 0 or losers.sum() == 0:
            raise ValueError("Cannot determine views: \
                             no winners or no losers identified based on the ranking method.")
        
        true_winners = np.where(winners)[0]
        true_losers = np.where(losers)[0]

        views_P = []
        views_Q = []
        if self.view_direction == "momentum":
            for idx in true_losers:
                row = np.zeros(n_investment)
                row[idx] = -1
                views_P.append(row)
                views_Q.append(-expected_spread)
            for idx in true_winners:
                row = np.zeros(n_investment)
                row[idx] = 1
                views_P.append(row)
                views_Q.append(expected_spread)
        else:
            for idx in true_losers:
                row = np.zeros(n_investment)
                row[idx] = 1
                views_P.append(row)
                views_Q.append(expected_spread)
            for idx in true_winners:
                row = np.zeros(n_investment)
                row[idx] = -1
                views_P.append(row)
                views_Q.append(-expected_spread)

        return np.array(views_P) , np.array(views_Q)
