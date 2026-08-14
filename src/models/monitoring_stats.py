from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import pandas as pd
import numpy as np

def _sanitize_value(v):
    if isinstance(v, (float, np.floating)) and not np.isfinite(v):
        return None
    return v

def _sanitize_dict(d):
    return {k: _sanitize_value(v) for k, v in d.items()}

def _sanitize_list(values):
    return [_sanitize_value(v) for v in values]

@dataclass(frozen=True)
class MonitoringStats:
    ic_statistics: Optional[Dict[str, Any]] = None
    ic_summary: Optional[Dict[str, Any]] = None
    regression_summary: Optional[Dict[str, Any]] = None

    def to_dict(self):
        result = {}
        if self.ic_statistics is not None:
            result["ic_statistics"] = {
                k: self._serialize(v)
                for k, v in self.ic_statistics.items()
            }
        if self.ic_summary is not None:
            result["ic_summary"] = _sanitize_dict(self.ic_summary)
        if self.regression_summary is not None:
            result["regression_summary"] = self.regression_summary
        return result
    
    def _serialize(self, obj):
        if isinstance(obj, pd.Series):
            values = obj.values.tolist()
            return {
                "index": obj.index.astype(str).tolist(),
                "values": _sanitize_list(values)
            }
        if isinstance(obj, pd.DataFrame):
            values = obj.values.tolist()
            sanitized = [ _sanitize_list(row) for row in values ]            
            return {
                "index": obj.index.astype(str).tolist(),
                "columns": obj.columns.tolist(),
                "values": sanitized
            }
        return obj    