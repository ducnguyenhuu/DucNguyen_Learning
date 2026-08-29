"""
Stock Forecaster Module
Provides time-series forecasting for stock prices using technical analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import yfinance as yf
from sklearn.linear_model import LinearRegression
import warnings
warnings.filterwarnings('ignore')

# Handle both direct execution and package execution
try:
    from stocktrader.data_manager import DataManager
except ImportError:
    from data_manager import DataManager


class StockForecaster:
    """
    Simple and effective stock price forecasting using technical analysis
    """
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        
        # Forecasting parameters
        self.forecast_methods = {
            'moving_average': {'weight': 0.3, 'period': 20},
            'exponential_smoothing': {'weight': 0.25, 'alpha': 0.3},
            'linear_regression': {'weight': 0.25, 'lookback': 30},
            'momentum': {'weight': 0.2, 'period': 14}
        }
    
    def calculate_moving_average_forecast(self, data: pd.DataFrame, days: int = 7) -> List[float]:
        """
        Calculate moving average based forecast
        
        Args:
            data: Historical stock data
            days: Number of days to forecast
            
        Returns:
            List of forecasted prices
        """
        try:
            # Calculate different period moving averages
            short_ma = data['Close'].rolling(window=5).mean().iloc[-1]
            medium_ma = data['Close'].rolling(window=10).mean().iloc[-1]
            long_ma = data['Close'].rolling(window=20).mean().iloc[-1]
            
            # Weighted average of different MAs
            forecast_base = (short_ma * 0.5 + medium_ma * 0.3 + long_ma * 0.2)
            
            # Calculate trend
            recent_trend = (data['Close'].iloc[-1] / data['Close'].iloc[-5] - 1) if len(data) >= 5 else 0
            
            forecasts = []
            for day in range(1, days + 1):
                # Apply trend with decay
                trend_factor = recent_trend * (0.95 ** day)
                forecast = forecast_base * (1 + trend_factor)
                forecasts.append(forecast)
            
            return forecasts
            
        except Exception as e:
            # Fallback to current price
            current_price = data['Close'].iloc[-1]
            return [current_price] * days
    
    def calculate_exponential_smoothing_forecast(self, data: pd.DataFrame, days: int = 7) -> List[float]:
        """
        Exponential smoothing forecast
        
        Args:
            data: Historical stock data
            days: Number of days to forecast
            
        Returns:
            List of forecasted prices
        """
        try:
            prices = data['Close'].values
            alpha = self.forecast_methods['exponential_smoothing']['alpha']
            
            # Simple exponential smoothing
            smoothed = [prices[0]]
            for price in prices[1:]:
                smoothed.append(alpha * price + (1 - alpha) * smoothed[-1])
            
            # Forecast
            last_smoothed = smoothed[-1]
            trend = (prices[-1] - prices[-5]) / 5 if len(prices) >= 5 else 0
            
            forecasts = []
            for day in range(1, days + 1):
                forecast = last_smoothed + trend * day * 0.5  # Dampened trend
                forecasts.append(forecast)
            
            return forecasts
            
        except Exception:
            current_price = data['Close'].iloc[-1]
            return [current_price] * days
    
    def calculate_linear_regression_forecast(self, data: pd.DataFrame, days: int = 7) -> List[float]:
        """
        Linear regression forecast
        
        Args:
            data: Historical stock data
            days: Number of days to forecast
            
        Returns:
            List of forecasted prices
        """
        try:
            lookback = min(self.forecast_methods['linear_regression']['lookback'], len(data))
            recent_data = data.tail(lookback)
            
            # Prepare data for regression
            X = np.arange(len(recent_data)).reshape(-1, 1)
            y = recent_data['Close'].values
            
            # Fit model
            model = LinearRegression()
            model.fit(X, y)
            
            # Generate forecasts
            forecasts = []
            for day in range(1, days + 1):
                future_x = np.array([[len(recent_data) + day - 1]])
                forecast = model.predict(future_x)[0]
                forecasts.append(forecast)
            
            return forecasts
            
        except Exception:
            current_price = data['Close'].iloc[-1]
            return [current_price] * days
    
    def calculate_momentum_forecast(self, data: pd.DataFrame, days: int = 7) -> List[float]:
        """
        Momentum-based forecast
        
        Args:
            data: Historical stock data
            days: Number of days to forecast
            
        Returns:
            List of forecasted prices
        """
        try:
            period = self.forecast_methods['momentum']['period']
            
            # Calculate momentum indicators
            recent_prices = data['Close'].tail(period)
            momentum = (recent_prices.iloc[-1] / recent_prices.iloc[0] - 1) / period
            
            # RSI for momentum strength
            rsi = self.calculate_rsi(data['Close']).iloc[-1]
            
            # Adjust momentum based on RSI
            if rsi > 70:  # Overbought
                momentum *= 0.5
            elif rsi < 30:  # Oversold
                momentum *= 1.5
            
            # Generate forecasts
            current_price = data['Close'].iloc[-1]
            forecasts = []
            
            for day in range(1, days + 1):
                # Apply momentum with decay
                daily_momentum = momentum * (0.9 ** day)
                forecast = current_price * (1 + daily_momentum * day)
                forecasts.append(forecast)
            
            return forecasts
            
        except Exception:
            current_price = data['Close'].iloc[-1]
            return [current_price] * days
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def get_market_volatility(self, data: pd.DataFrame) -> float:
        """Calculate recent market volatility"""
        try:
            returns = data['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # Annualized volatility
            return volatility
        except:
            return 0.2  # Default moderate volatility
    
    def calculate_confidence_score(self, data: pd.DataFrame, forecasts_dict: Dict) -> float:
        """
        Calculate confidence score for the forecast
        
        Args:
            data: Historical stock data
            forecasts_dict: Dictionary of different method forecasts
            
        Returns:
            Confidence score (0-100)
        """
        try:
            base_confidence = 50.0
            
            # 1. Data quality factor
            data_length_factor = min(len(data) / 60, 1.0) * 20
            base_confidence += data_length_factor
            
            # 2. Volatility penalty
            volatility = self.get_market_volatility(data)
            volatility_penalty = min(volatility * 50, 25)
            base_confidence -= volatility_penalty
            
            # 3. Forecast agreement
            if len(forecasts_dict) > 1:
                final_forecasts = [forecasts[-1] for forecasts in forecasts_dict.values()]
                std_dev = np.std(final_forecasts)
                mean_forecast = np.mean(final_forecasts)
                
                if mean_forecast > 0:
                    cv = std_dev / mean_forecast
                    agreement_bonus = max(0, 20 * (1 - cv * 5))
                    base_confidence += agreement_bonus
            
            # 4. Volume confirmation
            if len(data) >= 10:
                recent_volume = data['Volume'].tail(5).mean()
                avg_volume = data['Volume'].mean()
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                if 0.8 <= volume_ratio <= 1.5:
                    base_confidence += 5
                elif volume_ratio > 2:
                    base_confidence += 10
            
            # 5. Trend consistency
            short_trend = (data['Close'].iloc[-1] / data['Close'].iloc[-5] - 1) if len(data) >= 5 else 0
            medium_trend = (data['Close'].iloc[-1] / data['Close'].iloc[-10] - 1) if len(data) >= 10 else 0
            
            if abs(short_trend - medium_trend) < 0.02:  # Consistent trends
                base_confidence += 10
            
            return max(20, min(90, base_confidence))
            
        except Exception:
            return 50.0  # Default moderate confidence
    
    def forecast_stock_price(self, symbol: str, days: int = 7) -> Optional[Dict]:
        """
        Generate comprehensive stock price forecast
        
        Args:
            symbol: Stock ticker symbol
            days: Number of trading days to forecast
            
        Returns:
            Forecast results dictionary
        """
        try:
            # Get historical data
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            
            if hist.empty or len(hist) < 20:
                print(f"Insufficient data for {symbol}")
                return None
            
            current_price = hist['Close'].iloc[-1]
            
            # Generate forecasts using different methods
            forecasts_dict = {}
            
            # Moving Average
            forecasts_dict['moving_average'] = self.calculate_moving_average_forecast(hist, days)
            
            # Exponential Smoothing
            forecasts_dict['exponential_smoothing'] = self.calculate_exponential_smoothing_forecast(hist, days)
            
            # Linear Regression
            forecasts_dict['linear_regression'] = self.calculate_linear_regression_forecast(hist, days)
            
            # Momentum
            forecasts_dict['momentum'] = self.calculate_momentum_forecast(hist, days)
            
            # Combine forecasts using weighted average
            combined_forecasts = []
            for day_idx in range(days):
                weighted_sum = 0
                total_weight = 0
                
                for method, forecasts in forecasts_dict.items():
                    if day_idx < len(forecasts):
                        weight = self.forecast_methods[method]['weight']
                        weighted_sum += forecasts[day_idx] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    combined_forecasts.append(weighted_sum / total_weight)
                else:
                    combined_forecasts.append(current_price)
            
            # Calculate confidence
            confidence = self.calculate_confidence_score(hist, forecasts_dict)
            
            # Determine trend direction
            final_price = combined_forecasts[-1]
            total_change = ((final_price - current_price) / current_price) * 100
            
            if total_change > 2:
                trend = "BULLISH"
            elif total_change < -2:
                trend = "BEARISH"
            else:
                trend = "NEUTRAL"
            
            # Generate trading dates
            trading_dates = []
            current_date = datetime.now().date()
            days_added = 0
            
            while days_added < days:
                current_date += timedelta(days=1)
                if current_date.weekday() < 5:  # Weekdays only
                    trading_dates.append(current_date.strftime('%Y-%m-%d'))
                    days_added += 1
            
            # Format predictions
            predictions = []
            for i, (date, price) in enumerate(zip(trading_dates, combined_forecasts)):
                predictions.append({
                    'date': date,
                    'price': round(price, 2),
                    'day': i + 1
                })
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'predictions': predictions,
                'trend_direction': trend,
                'confidence': round(confidence, 1),
                'total_change_percent': round(total_change, 2),
                'forecast_methods': list(forecasts_dict.keys()),
                'individual_forecasts': {
                    method: [round(p, 2) for p in forecasts] 
                    for method, forecasts in forecasts_dict.items()
                },
                'volatility': round(self.get_market_volatility(hist), 3),
                'data_points': len(hist),
                'forecast_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error forecasting {symbol}: {e}")
            return None
    
    def get_technical_indicators(self, symbol: str) -> Optional[Dict]:
        """
        Get current technical indicators for a stock
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Technical indicators dictionary
        """
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            
            if hist.empty:
                return None
            
            current_price = hist['Close'].iloc[-1]
            
            # Moving averages
            ma_5 = hist['Close'].rolling(window=5).mean().iloc[-1]
            ma_10 = hist['Close'].rolling(window=10).mean().iloc[-1]
            ma_20 = hist['Close'].rolling(window=20).mean().iloc[-1]
            ma_50 = hist['Close'].rolling(window=50).mean().iloc[-1] if len(hist) >= 50 else ma_20
            
            # RSI
            rsi = self.calculate_rsi(hist['Close']).iloc[-1]
            
            # Volatility
            volatility = self.get_market_volatility(hist)
            
            # Volume analysis
            current_volume = hist['Volume'].iloc[-1]
            avg_volume = hist['Volume'].mean()
            volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
            
            # Price momentum
            momentum_5 = (current_price / hist['Close'].iloc[-6] - 1) * 100 if len(hist) >= 6 else 0
            momentum_20 = (current_price / hist['Close'].iloc[-21] - 1) * 100 if len(hist) >= 21 else 0
            
            return {
                'symbol': symbol,
                'current_price': round(current_price, 2),
                'moving_averages': {
                    'ma_5': round(ma_5, 2),
                    'ma_10': round(ma_10, 2),
                    'ma_20': round(ma_20, 2),
                    'ma_50': round(ma_50, 2)
                },
                'rsi': round(rsi, 1),
                'volatility': round(volatility, 3),
                'volume': {
                    'current': int(current_volume),
                    'average': int(avg_volume),
                    'ratio': round(volume_ratio, 2)
                },
                'momentum': {
                    '5_day': round(momentum_5, 2),
                    '20_day': round(momentum_20, 2)
                },
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
        except Exception as e:
            print(f"Error getting technical indicators for {symbol}: {e}")
            return None
