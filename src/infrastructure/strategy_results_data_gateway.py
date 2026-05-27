import pandas as pd
import duckdb as db

class GatewayBase:
    def __init__(self, database_name):
        self.conn = db.connect(database_name)

    def add_to_database(self):
        pass

    def get_from_db(self):
        pass

class StrategyResultsDataGateway(GatewayBase):
    
    def __init__(self, config):
        super().__init__(config["database_name"])

    def save_results(self):
        pass

class ExperimentMetaDataDataGateway(GatewayBase):
    def __init__(self, config):
        super().__init__(config["database_name"])

    def save_results(self):
        pass