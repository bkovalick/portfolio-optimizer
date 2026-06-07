from dataclasses import dataclass

@dataclass
class PairsTradingConfig:
    pairs_lookback_horizon : int
    cointegration_threshold: int
    pairs_entry : int
    pairs_exit : int

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            pairs_lookback_horizon = d.get("pairs_lookback_horizon", 20),
            cointegration_threshold = d.get("cointegration_threshold", 0.70),
            pairs_entry = d.get("pairs_entry", 2),
            pairs_exit = d.get("pairs_exit", 3.5)
        )