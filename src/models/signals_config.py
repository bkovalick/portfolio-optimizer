from dataclasses import dataclass
from typing import Dict, Any, Optional
from models.machine_learning_config import MachineLearningConfig
from models.pairs_trading_config import PairsTradingConfig

@dataclass(frozen=True)
class SignalsConfig:
    apply_winsorizing: bool
    windsor_percentiles: Dict
    mean_reversion_window: int
    momentum_skip_periods: int
    black_litterman: Optional[Dict[str, Any]]
    ml_signals_config: Optional[MachineLearningConfig]
    pairs_trading: Optional[PairsTradingConfig]
    
    @classmethod
    def from_dict(cls, d: dict, market_frequency: str = "d"):
        ml_config = d.get("ml_signals_config", None)
        return cls(
            apply_winsorizing = d.get("apply_winsorizing", True),
            windsor_percentiles = d.get(
                "windsor_percentiles",
                {"lower": 0.05, "upper": 0.95}
            ),
            mean_reversion_window = d.get("mean_reversion_window", 4),
            momentum_skip_periods = d.get("momentum_skip_periods", 4),
            black_litterman = d.get("black_litterman", None),
            ml_signals_config = MachineLearningConfig.from_dict(ml_config, market_frequency) if ml_config is not None else None,
            pairs_trading = PairsTradingConfig.from_dict(d.get("pairs_trading", {})) if d.get("pairs_trading", None) is not None else None
        )