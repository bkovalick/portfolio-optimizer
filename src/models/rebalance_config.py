from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ConstraintsConfig:
    risk_aversion: float = 1.0
    turnover_limit: Optional[float] = None
    min_position_size: Optional[float] = None
    max_position_size: Optional[float] = None
    max_number_of_positions: Optional[int] = None
    asset_class_constraints: Optional[Dict[str, List[float]]] = None
    sector_constraints: Optional[Dict[str, List[float]]] = None
    max_return: float = 0.05
    concentration_strength: float = 1.0
    optimizer_vol_constraint: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "ConstraintsConfig":
        return cls(
            risk_aversion=d.get("risk_aversion", 1.0),
            turnover_limit=d.get("turnover_limit", None),
            min_position_size=d.get("min_position_size", None),
            max_position_size=d.get("max_position_size", None),
            max_number_of_positions=d.get("max_number_of_positions", None),
            asset_class_constraints=d.get("asset_class_constraints", None),
            sector_constraints=d.get("sector_constraints", None),
            max_return=d.get("max_return", 0.05),
            concentration_strength=d.get("concentration_strength", 1.0),
            optimizer_vol_constraint=d.get("optimizer_vol_constraint", None),
        )


@dataclass(frozen=True)
class StrategyRulesConfig:
    vol_target: Optional[float] = None
    vol_lookback_days: Optional[Any] = None
    vol_max_leverage: Optional[float] = None

    @classmethod
    def from_dict(cls, d: dict) -> "StrategyRulesConfig":
        return cls(
            vol_target=d.get("vol_target", None),
            vol_lookback_days=d.get("vol_lookback_days", None),
            vol_max_leverage=d.get("vol_max_leverage", None),
        )


@dataclass(frozen=True)
class RebalanceProblemConfig:
    strategy_type: str
    optimizer_type: str
    signal_source: str
    rebalance_frequency: Optional[str]
    apply_market_caps: bool
    apply_max_return_objective: bool
    apply_sharpe_objective: bool
    initial_weights: Optional[Any]
    starting_portfolio_value: float
    cash_infusion: float
    constraints: ConstraintsConfig
    strategy_rules: StrategyRulesConfig

    @classmethod
    def from_dict(cls, d: dict) -> "RebalanceProblemConfig":
        return cls(
            strategy_type=d.get("strategy_type"),
            optimizer_type=d.get("optimizer_type"),
            signal_source=d.get("signal_source", "risk_return"),
            rebalance_frequency=d.get("rebalance_frequency", None),
            apply_market_caps=d.get("apply_market_caps", False),
            apply_max_return_objective=d.get("apply_max_return_objective", False),
            apply_sharpe_objective=d.get("apply_sharpe_objective", False),
            initial_weights=d.get("initial_weights", None),
            starting_portfolio_value=d.get("starting_portfolio_value", 10000),
            cash_infusion=d.get("cash_infusion", 1000),
            constraints=ConstraintsConfig.from_dict(d.get("constraints", {})),
            strategy_rules=StrategyRulesConfig.from_dict(d.get("strategy_rules", {})),
        )
