import pandas as pd
import duckdb as db

class GatewayBase:
    
    def add_to_database(self):
        pass

class StrategyResultsDataGateway(GatewayBase):
    
    def __init__(self, config):
        pass

    def save_results(self):
        pass

class ExperimentMetaDataDataGateway(GatewayBase):
    def __init__(self, config):
        pass

    def save_results(self):
        pass