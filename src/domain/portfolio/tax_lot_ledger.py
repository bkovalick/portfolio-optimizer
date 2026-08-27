import pandas as pd

from domain.portfolio.portfolio import Portfolio
from simulation.market_state import MarketState
from models.rebalance_solution import RebalanceSolution

class TaxLotLedger:
    def __init__(self):
        self._tax_lots = []
        self._short_term_tax_rate = 0.37
        self._long_term_tax_rate = 0.20
        self._base_nav = 1_000_000_000
        self._last_rebalance_date = None

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

        self._tax_lots.append(
            self._process_rebalance(
                market_state=market_state,
                portfolio=portfolio,
                lot_sell_allocations=rebalance_solution.sell_allocations,
                cursor=cursor
            )
        )
        self._last_rebalance_date = rebalance_date

    def _process_rebalance(self,
                       market_state: MarketState,
                       portfolio: Portfolio,
                       lot_sell_allocations: dict,
                       cursor: int) -> pd.DataFrame:
        """Processes a rebalance and returns the updated tax lot information."""
        new_lots = {}
        prices = market_state.investment_prices
        total_portfolio_value = self._base_nav
        previous_weights = portfolio.weights.iloc[cursor - 1] if cursor > 0 else pd.Series(0, index=portfolio.weights.columns)
        current_weights = portfolio.weights.iloc[cursor]

        for ticker in current_weights.index:
            if ticker == "CASH":
                continue

            acquisition_date = prices.iloc[cursor].name
            # previous_snapshot = (
            #     self._tax_lots[-1]
            #     if self._tax_lots
            #     else pd.DataFrame()
            # )
            # existing_lot = previous_snapshot.loc[previous_snapshot["Ticker"].eq(ticker)]
            delta_weight = current_weights[ticker] - previous_weights[ticker]
            current_price = prices.loc[acquisition_date, ticker]

            if pd.isna(current_price):
                current_price = 1.0

            if delta_weight > 0:
                shares = (delta_weight * total_portfolio_value) / current_price
                new_lots[(acquisition_date, ticker)] = self._process_buy_lots(shares, current_price)
            elif delta_weight <= 0:
                pass
                # self._process_sell_lots(existing_lot, pd.DataFrame())

        tax_lots_df = pd.DataFrame.from_dict(new_lots, orient="index")
        tax_lots_df.index.names = ["RebalanceDate", "Ticker"]
        return tax_lots_df.reset_index()

    def _process_sell_lots(self, existing_lot: pd.DataFrame, new_lot: pd.DataFrame) -> pd.DataFrame:
        """Processes a sell transaction and returns the updated tax lot information."""
        if existing_lot.empty:
            return new_lot
        else:
            return pd.concat([existing_lot, new_lot], axis=0)

    def _process_buy_lots(self, 
                       shares: float, 
                       current_price: float) -> pd.DataFrame:
        """Processes a buy transaction and returns the tax lot information."""
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
            "days_held": days_held,
            "term": term,
            "tax_rate": tax_rate,
            "current_price": current_price,
            "acquisition_price": acq_price,
            "shares": shares,
            "current_value": current_value,
            "gain_per_share": gain_per_share,
            "total_cost_basis": total_cost_basis,
            "total_gain": total_gain,
            "tax_cost": tax_cost
        }
        
    @property
    def tax_lots(self) -> pd.DataFrame:
        """Returns the tax lot ledger as a DataFrame."""
        if not self._tax_lots:
            raise ValueError("Tax lot ledger is empty—cannot return tax lots.")
        return pd.concat(self._tax_lots, axis=0)