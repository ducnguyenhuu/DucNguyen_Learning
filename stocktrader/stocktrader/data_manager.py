"""
Data Manager Module
Handles Yahoo Finance data fetching and validation
Pure stateless operation with no local storage
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
import time
import os
import json


class DataManager:
    """Manages stock data fetching from Yahoo Finance - Pure stateless operation"""
    
    def __init__(self):
        # Load configuration from CSV files
        self.config_dir = os.path.join(os.path.dirname(__file__), 'config')
        self.popular_symbols = self._load_popular_symbols()
        self.sector_mapping = self._load_sector_mapping()
    
    def _load_popular_symbols(self) -> List[str]:
        """Load popular symbols from JSON configuration file"""
        try:
            json_path = os.path.join(self.config_dir, 'popular_symbols.json')
            with open(json_path, 'r') as f:
                data = json.load(f)
            return [item['symbol'] for item in data['popular_symbols']]
        except Exception as e:
            print(f"Warning: Could not load popular symbols from JSON: {e}")
            # Fallback to hardcoded list
            return [
                'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'NFLX',
                'JPM', 'BAC', 'JNJ', 'PFE', 'PG', 'KO', 'XOM', 'CVX'
            ]
    
    def _load_sector_mapping(self) -> Dict[str, List[str]]:
        """Load sector mapping from JSON configuration file"""
        try:
            json_path = os.path.join(self.config_dir, 'sector_mapping.json')
            with open(json_path, 'r') as f:
                data = json.load(f)
            
            mapping = {}
            for sector_key, sector_data in data['sector_mapping'].items():
                mapping[sector_key] = sector_data['symbols']
            
            return mapping
        except Exception as e:
            print(f"Warning: Could not load sector mapping from JSON: {e}")
            # Fallback to minimal mapping
            return {
                'technology': ['AAPL', 'MSFT', 'GOOGL'],
                'finance': ['JPM', 'BAC', 'WFC'],
                'healthcare': ['JNJ', 'PFE', 'UNH'],
                'consumer': ['PG', 'KO', 'WMT'],
                'energy': ['XOM', 'CVX', 'COP']
            }
    
    def get_stock_info(self, symbol: str) -> Dict:
        """
        Get basic stock information and current metrics
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with stock information
        """
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # Get current price data
            hist = stock.history(period="1d")
            current_price = hist['Close'].iloc[-1] if not hist.empty else None
            
            return {
                'symbol': symbol.upper(),
                'name': info.get('longName', symbol),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('forwardPE', info.get('trailingPE')),
                'price': current_price,
                'dividend_yield': info.get('dividendYield', 0) * 100 if info.get('dividendYield') else 0,
                'roe': info.get('returnOnEquity', 0) * 100 if info.get('returnOnEquity') else 0,
                'debt_to_equity': info.get('debtToEquity', 0),
                'revenue_growth': info.get('revenueGrowth', 0) * 100 if info.get('revenueGrowth') else 0,
                'profit_margin': info.get('profitMargins', 0) * 100 if info.get('profitMargins') else 0,
                'beta': info.get('beta', 1.0)
            }
            
        except Exception as e:
            print(f"Warning: Could not fetch data for {symbol}: {e}")
            return {
                'symbol': symbol.upper(),
                'name': symbol,
                'sector': 'Unknown',
                'industry': 'Unknown',
                'market_cap': 0,
                'pe_ratio': None,
                'price': None,
                'dividend_yield': 0,
                'roe': 0,
                'debt_to_equity': 0,
                'revenue_growth': 0,
                'profit_margin': 0,
                'beta': 1.0
            }
    
    def get_historical_data(self, symbol: str, period: str = "1y") -> pd.DataFrame:
        """
        Get historical price data for a stock
        
        Args:
            symbol: Stock ticker symbol
            period: Time period (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
            
        Returns:
            DataFrame with historical price data
        """
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period=period)
            
            if data.empty:
                print(f"Warning: No historical data found for {symbol}")
                return pd.DataFrame()
            
            # Clean data
            data = data.dropna()
            
            return data
            
        except Exception as e:
            print(f"Error fetching historical data for {symbol}: {e}")
            return pd.DataFrame()
    
    def get_multiple_stocks_info(self, symbols: List[str]) -> List[Dict]:
        """
        Get information for multiple stocks efficiently
        
        Args:
            symbols: List of stock ticker symbols
            
        Returns:
            List of stock information dictionaries
        """
        stocks_info = []
        
        print(f"Fetching data for {len(symbols)} stocks...")
        
        for i, symbol in enumerate(symbols):
            if i > 0 and i % 10 == 0:
                print(f"Progress: {i}/{len(symbols)} stocks processed")
                time.sleep(1)  # Rate limiting
            
            info = self.get_stock_info(symbol)
            if info['price'] is not None:  # Only include stocks with valid price data
                stocks_info.append(info)
        
        print(f"Successfully fetched data for {len(stocks_info)}/{len(symbols)} stocks")
        return stocks_info
    
    def get_market_sector_symbols(self, sector: Optional[str] = None) -> List[str]:
        """
        Get stock symbols filtered by sector
        
        Args:
            sector: Sector name to filter by
            
        Returns:
            List of stock symbols
        """
        if sector is None:
            return self.popular_symbols
        
        # Use sector mapping loaded from CSV
        return self.sector_mapping.get(sector.lower(), self.popular_symbols)
    
    def validate_symbol(self, symbol: str) -> bool:
        """
        Validate if a stock symbol exists and has data
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            True if symbol is valid, False otherwise
        """
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1d")
            return not hist.empty
        except:
            return False
    
    def get_current_price(self, symbol: str) -> Optional[float]:
        """
        Get the current/latest price for a stock
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Current price or None if unavailable
        """
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="1d")
            
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
            return None
            
        except Exception:
            return None
    
    def get_company_name(self, symbol: str) -> str:
        """
        Get company name for a stock symbol
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Company name or symbol if name not available
        """
        try:
            stock = yf.Ticker(symbol)
            info = stock.info
            return info.get('longName', info.get('shortName', symbol))
        except Exception:
            return symbol
