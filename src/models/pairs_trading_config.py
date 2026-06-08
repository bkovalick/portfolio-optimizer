from dataclasses import dataclass

@dataclass
class PairsTradingConfig:
    pairs_lookback_horizon: int
    cointegration_threshold: int
    correlation_filter: int
    pairs_entry: int
    pairs_exit: int
    pairs_stop_loss: int

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            pairs_lookback_horizon = d.get("pairs_lookback_horizon", 50),
            cointegration_threshold = d.get("cointegration_threshold", 0.05),
            correlation_filter = d.get("correlation_filter", 0.70),
            pairs_entry = d.get("pairs_entry", 2),
            pairs_exit = d.get("pairs_exit", 0.5),
            pairs_stop_loss = d.get("pairs_stop_loss", 3.5)
        )