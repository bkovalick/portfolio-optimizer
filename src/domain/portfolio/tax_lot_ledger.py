import pandas as pd
import numpy as np

from domain.portfolio.portfolio import Portfolio
from simulation.market_state import MarketState
from models.rebalance_solution import RebalanceSolution

class TaxLotLedger:
    def __init__(self):
        self._short_term_tax_rate = 0.37
        self._long_term_tax_rate = 0.20
        self._base_nav = 1_000_000_000
        self._last_rebalance_date = None
        self._last_rebalance_weights = None
        self._tax_lots = pd.DataFrame(
            columns=[
                "AcquisitionDate",
                "Ticker",
                "DaysHeld",
                "Term",
                "TaxRate",
                "CurrentPrice",
                "AcquisitionPrice",
                "Shares",
                "CurrentValue",
                "GainPerShare",
                "TotalCostBasis",
                "TotalGain",
                "TaxCost",
            ]
        )        

    def update_ledger(self,
               market_state: MarketState,
               portfolio: Portfolio,
               rebalance_solution: RebalanceSolution,
               cursor: int) -> None:
        """Updates the tax lot ledger given the current portfolio state."""
        rebalance_date = portfolio.weights.index[cursor]
        if self._last_rebalance_date is not None and rebalance_date <= self._last_rebalance_date:
            raise ValueError(
                f"Rebalance date {rebalance_date} is not after the last rebalance date {self._last_rebalance_date}."
            )

        self._process_rebalance(
            market_state=market_state,
            portfolio=portfolio,
            lot_sell_allocations=rebalance_solution.sell_allocations,
            cursor=cursor
        )
        self._last_rebalance_weights = portfolio.weights.iloc[cursor].copy()
        self._last_rebalance_date = rebalance_date

    def _process_rebalance(self,
                           market_state: MarketState,
                           portfolio: Portfolio,
                           lot_sell_allocations: dict,
                           cursor: int) -> None:
        """Processes a rebalance and returns the updated tax lot information."""
        rebalance_date=portfolio.weights.index[cursor]
        current_prices=market_state.investment_prices.iloc[cursor]
        self._update_current_prices(rebalance_date, current_prices)
        self._process_sell_lots(lot_sell_allocations)
        self._process_buy_lots(
            portfolio,
            cursor,
            rebalance_date,
            current_prices,
        )
        self._update_current_prices(rebalance_date, current_prices)

    def _update_current_prices(self, rebalance_date: pd.Timestamp, current_prices: pd.Series) -> None:
        """Updates the current prices and calculates gains, tax costs, and other relevant metrics for each tax lot."""
        if self._tax_lots.empty:
            return

        self._tax_lots["CurrentPrice"] = self._tax_lots["Ticker"].map(current_prices)
        self._tax_lots["DaysHeld"] = (rebalance_date - self._tax_lots["AcquisitionDate"]).dt.days
        self._tax_lots["Term"] = np.where(self._tax_lots["DaysHeld"] >= 365, "long", "short")
        self._tax_lots["TaxRate"] = np.where(self._tax_lots["Term"].eq("long"), 
                                             self._long_term_tax_rate, self._short_term_tax_rate)        
        self._tax_lots["CurrentValue"] = self._tax_lots["CurrentPrice"] * self._tax_lots["Shares"]
        self._tax_lots["GainPerShare"] = self._tax_lots["CurrentPrice"] - self._tax_lots["AcquisitionPrice"]
        self._tax_lots["TotalCostBasis"] = self._tax_lots["AcquisitionPrice"] * self._tax_lots["Shares"]
        self._tax_lots["TotalGain"] = self._tax_lots["GainPerShare"] * self._tax_lots["Shares"]
        self._tax_lots["TaxCost"] = (self._tax_lots["TotalGain"].clip(lower=0) * self._tax_lots["TaxRate"])

    def _process_sell_lots(self, lot_sell_allocations: dict[int, float]) -> None:
        """Processes a sell transaction and returns the updated tax lot information."""
        for lot_id, sell_fraction in lot_sell_allocations.items():
            if lot_id not in self._tax_lots.index:
                raise ValueError(f"Unknown tax lot id: {lot_id}")

            if not 0 <= sell_fraction <= 1:
                raise ValueError(
                    f"Sell fraction for lot {lot_id} must be between 0 and 1."
                )

            shares_sold = self._tax_lots.at[lot_id, "Shares"] * sell_fraction
            self._tax_lots.at[lot_id, "Shares"] -= shares_sold

        self._tax_lots = self._tax_lots.loc[
            self._tax_lots["Shares"] > 1e-8
        ].copy()

    def _process_buy_lots(self,
                          portfolio: Portfolio,
                          cursor: int,
                          acquisition_date: pd.Timestamp,
                          current_prices: pd.Series) -> None:
        """Create new lots for inferred purchases at this rebalance."""
        new_lots = {}
        total_portfolio_value = self._base_nav
        previous_weights = self._last_rebalance_weights if self._last_rebalance_weights is not None \
            else pd.Series(0, index=portfolio.weights.columns)
        current_weights = portfolio.weights.iloc[cursor]

        for ticker in current_weights.index:
            if ticker.upper() == "CASH":
                continue

            delta_weight = current_weights[ticker] - previous_weights[ticker]
            current_price = current_prices[ticker]
            if current_price is None or pd.isna(current_price) or current_price <= 0:
                continue

            if delta_weight > 0:
                shares = (delta_weight * total_portfolio_value) / current_price
                new_lots[(acquisition_date, ticker)] = self._process_buy_lot(shares, current_price)

        new_tax_lots_df = pd.DataFrame.from_dict(new_lots, orient="index")
        new_tax_lots_df.index.names = ["AcquisitionDate", "Ticker"]
        new_tax_lots_df = new_tax_lots_df.reset_index()
        self._tax_lots = pd.concat([self._tax_lots, new_tax_lots_df], ignore_index=True)
                
    def _process_buy_lot(self, shares: float, current_price: float) -> pd.DataFrame:
        """Processes a single buy transaction and returns the new tax lot information."""
        current_price = current_price
        acq_price = current_price
        current_value = current_price * shares
        days_held = 0
        term = "short"
        tax_rate = self._short_term_tax_rate
        gain_per_share = current_price - acq_price
        total_cost_basis = acq_price * shares
        total_gain = gain_per_share * shares
        tax_cost = total_gain * tax_rate

        return {
            "DaysHeld": days_held,
            "Term": term,
            "TaxRate": tax_rate,
            "CurrentPrice": current_price,
            "AcquisitionPrice": acq_price,
            "Shares": shares,
            "CurrentValue": current_value,
            "GainPerShare": gain_per_share,
            "TotalCostBasis": total_cost_basis,
            "TotalGain": total_gain,
            "TaxCost": tax_cost
        }
        
    @property
    def tax_lots(self) -> pd.DataFrame:
        """Returns the tax lot ledger as a DataFrame."""
        return self._tax_lots.copy()