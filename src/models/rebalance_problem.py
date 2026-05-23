
class RebalanceProblem:    
    """
    Pure data container for a prepared rebalance problem.
    Attributes are accessed via properties.
    """

    def __init__(self, prepared_data: dict):
        self._data = dict(prepared_data)

    def to_dict(self):
        return dict(self._data)
        
    @property
    def n_assets(self) -> int:
        return self._data.get("n_assets", 5)
    
    @property
    def optimizer_type(self) -> str:
        return self._data.get("optimizer_type", "fwp_optimizer")
    
    @property
    def strategy_type(self) -> str:
        return self._data.get("strategy_type", "fwp_strategy")
    
    @property
    def apply_max_return_objective(self) -> bool:
        return self._data.get("apply_max_return_objective", False)
    
    @property
    def apply_sharpe_objective(self) -> bool:
        return self._data.get("apply_sharpe_objective", False)

    @property
    def initial_weights(self) -> dict:
        return self._data.get("initial_weights", {})

    @property
    def cash_allocation(self) -> float:
        return self._data.get("cash_allocation")
    
    @property
    def rebalance_frequency(self) -> str:
        return self._data.get("rebalance_frequency", "weekly")
    
    @property
    def risk_aversion(self) -> int:
        return self._data.get("risk_aversion", 0)

    @property
    def turnover_limit(self) -> float:
        return self._data.get("turnover_limit", 0.0)
    
    @property
    def min_position_size(self) -> float:
        return self._data.get("min_position_size", None) 
        
    @property
    def max_position_size(self) -> float:
        return self._data.get("max_position_size", None) 

    @property
    def max_number_of_positions(self) -> int:
        return self._data.get("max_number_of_positions", None)
    
    @property
    def asset_class_constraints(self) -> int:
        return self._data.get("asset_class_constraints", None)
    
    @property
    def sector_constraints(self) -> int:
        return self._data.get("sector_constraints", None)
    
    @property
    def max_return(self) -> float:
        return self._data.get("max_return", 0.05)
    
    @property
    def concentration_strength(self) -> int:
        return self._data.get("concentration_strength", 1)
    
    @property
    def asset_class_map(self) -> dict:
        return self._data.get("asset_class_map", {})
    
    @property
    def sector_map(self) -> dict:
        return self._data.get("sector_map", {})

    @property
    def security_to_etf_map(self) -> dict:
        return self._data.get("security_to_etf_map", {})
    
    @property
    def signal_universe(self) -> list:
        return self._data.get("signal_universe") or self.investment_universe
    
    @property
    def investment_universe(self) -> list:
        return self._data.get("investment_universe", ["AAPL"])
    
    @property
    def optimizer_vol_constraint(self) -> float:
        return self._data.get("optimizer_vol_constraint", None)
    
    @property
    def vol_target(self) -> float:
        return self._data.get("vol_target", None)
    
    @property
    def vol_lookback_days(self) -> float:
        return self._data.get("vol_lookback_days", None)
    
    @property
    def vol_max_leverage(self) -> float:
        return self._data.get("vol_max_leverage", None)
    
    @property
    def signal_source(self) -> str:
        return self._data.get("signal_source", "risk_return")
    
    @property
    def transaction_cost(self) -> float:
        return self._data.get("transaction_cost", 0.0)
    
    @property
    def starting_portfolio_value(self) -> float:
        return self._data.get("starting_portfolio_value", 10000)
    
    @property
    def cash_infusion(self) -> float:
        return self._data.get("cash_infusion", 1000)