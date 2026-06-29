import yfinance as yf
import pandas as pd
from models.market_config import MarketStoreConfig

class MarketDataGateway:
    """ Data gateway for fetching market data using yfinance """
    @staticmethod
    def get_price_data(market_store_config: MarketStoreConfig):
        tickers = market_store_config.tickers
        benchmark_ticker = market_store_config.benchmark
        if benchmark_ticker not in tickers:
            tickers.append(benchmark_ticker)
        data_source = market_store_config.data_source
        start_date = market_store_config.start_date
        end_date = market_store_config.end_date
        
        for source, content in data_source.items():
            if source == "yfinance":
                return MarketDataGateway.get_price_data_y_finance(tickers, start_date, end_date)
            elif source == "csv":
                return MarketDataGateway.get_price_data_csv(content)
            else:
                raise ValueError(f"Unknown source type: {data_source}")

    @staticmethod
    def get_sector_data(tickers: list) -> dict:
        sectors = {}
        for ticker in tickers:
            try:
                ticker_data = yf.Ticker(ticker).info
                sectors[ticker] = ticker_data.get("sector")
            except Exception as e:
                print(f"Could not fetch market cap data for {ticker}: {e}")
                sectors[ticker] = 0
                continue

        return sectors
    
    @staticmethod
    def get_market_caps(tickers: list) -> dict:
        market_caps = {}
        for ticker in tickers:
            try:
                ticker_data = yf.Ticker(ticker).info
                market_caps[ticker] = ticker_data.get("marketCap")
            except Exception as e:
                print(f"Could not fetch market cap data for {ticker}: {e}")
                market_caps[ticker] = 0
                continue

        return market_caps
    
    @staticmethod
    def get_etf_market_caps(tickers: list) -> dict:
        market_caps = {}
        for ticker in tickers:
            try:
                ticker_data = yf.Ticker(ticker).info
                market_caps[ticker] = ticker_data.get("totalAssets", None)
            except Exception as e:
                print(f"Could not fetch market cap data for {ticker}: {e}")
                market_caps[ticker] = 0
                continue

        return market_caps        

    @staticmethod
    def get_price_data_y_finance(tickers, start_date, end_date):
        data = yf.download(tickers, start=start_date, end=end_date)
        return data.xs('Close', axis=1, level=0)        

    @staticmethod
    def get_price_data_csv(csv_file):
        return pd.read_csv(csv_file)

class MarketDataStore:
    """ Environment to interact with market data gateway """
    def __init__(self, 
                 market_store_config: MarketStoreConfig):
        """ Initialize with market data gateway and parameters """
        self.transaction_cost = market_store_config.transaction_cost
        self.apply_market_caps = market_store_config.apply_market_caps
        self._prices = MarketDataGateway.get_price_data(market_store_config)
        self._prices = self._prices.sort_index()
        self._prices = self._prices.dropna(how='all')

        if len(self._prices) == 0:
            raise ValueError("Market Data Store not created properly, please check inputs.")
        
        self._prices = self._prices.bfill().ffill()
        if "CASH" not in self._prices.columns:
            daily_rate = market_store_config.risk_free_rate / 252
            n = len(self._prices)
            self._prices["CASH"] = (1 + daily_rate) ** pd.Series(range(n), index=self._prices.index)

    @property
    def prices(self) -> pd.DataFrame:
        return self._prices
    
    @property
    def market_caps(self) -> pd.Series:
        if not self.apply_market_caps:
            return pd.Series(dtype=float)
        if self._market_caps is None:
            self._market_caps = MarketDataGateway.get_market_caps(self.prices.columns.tolist())
            if "CASH" not in self._market_caps:
                self._market_caps["CASH"] = 0        
        return pd.Series(self._market_caps).fillna(0)
    
    @property
    def etf_market_caps(self) -> pd.Series:
        if not self.apply_market_caps:
            return pd.Series(dtype=float)
        if self._etf_market_caps is None:
            self._etf_market_caps = MarketDataGateway.get_etf_market_caps(self.prices.columns.tolist())
        return pd.Series(self._etf_market_caps).fillna(0)
    
    @property
    def sectors(self) -> pd.Series:
        if self._sectors is None:
            self._sectors = MarketDataGateway.get_sector_data(self.prices.columns.tolist())
        return pd.Series(self._sectors).fillna("Unknown")        