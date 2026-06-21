import pandas as pd
import numpy as np
from domain.portfolio.iportfolio import PortfolioInterface

class Portfolio(PortfolioInterface):
    """Portfolio class that houses weights, returns, and turnover calculations."""

    def __init__(self):
        self.weights = None
        self.returns = None
        self.turnover = None

    def initialize(self, dates, tickers: np.ndarray, initial_weights: np.ndarray):
        """Initialize portfolio with rebalance problem and price data."""
        if len(initial_weights) == 0:
            raise ValueError("price_data is empty—cannot initialize portfolio weights.")

        self.weights = pd.DataFrame(0, dtype=float, index=dates, columns=tickers)
        self.weights.iloc[0] = initial_weights
        self.returns = pd.Series(0, dtype=float, index=dates)
        self.turnover = pd.Series(0, dtype=float, index=dates)
    
    def apply(self, target_weights: np.ndarray, prev_weights: np.ndarray, cursor: int) -> None:
        """ Updates weights and turnover """
        turnover = np.sum(np.abs(target_weights - prev_weights)) / 2
        self.weights.iloc[cursor] = target_weights
        self.turnover.iloc[cursor] = turnover

    def drift(self, prev_weights: np.ndarray, asset_returns: np.ndarray, cursor: int) -> np.ndarray:
        """ Updates weights and returns """
        portfolio_return = np.sum(prev_weights * asset_returns)
        new_weights = prev_weights * (1 + asset_returns)
        
        if np.any(new_weights < 0):
            gross = np.sum(np.abs(new_weights))
            if gross > 0:
                new_weights /= gross
        else:
            new_weights /= new_weights.sum()

        self.weights.iloc[cursor] = new_weights
        self.returns.iloc[cursor] = portfolio_return
        return np.array(new_weights)