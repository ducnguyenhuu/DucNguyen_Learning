"""
Enhanced Ensemble Forecaster with Multiple Models
Implements high-impact accuracy improvements
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import yfinance as yf
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
import warnings
warnings.filterwarnings('ignore')

# Handle both direct execution and package execution
try:
    from stocktrader.data_manager import DataManager
except ImportError:
    from data_manager import DataManager


class EnsembleForecaster:
    """
    Advanced ensemble forecaster combining multiple models for higher accuracy
    """
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        
        # Import sentiment analyzer
        try:
            from stocktrader.sentiment_analyzer import SentimentAnalyzer
        except ImportError:
            from sentiment_analyzer import SentimentAnalyzer
        
        self.sentiment_analyzer = SentimentAnalyzer()
        
        # Model ensemble configuration with dynamic weights
        self.models = {
            'linear_regression': {
                'model': LinearRegression(),
                'weight': 0.25,
                'accuracy': 0.65,
                'last_updated': datetime.now()
            },
            'moving_average': {
                'model': None,  # Custom implementation
                'weight': 0.25,
                'accuracy': 0.62,
                'last_updated': datetime.now()
            },
            'exponential_smoothing': {
                'model': None,  # Custom implementation
                'weight': 0.20,
                'accuracy': 0.68,
                'last_updated': datetime.now()
            },
            'random_forest': {
                'model': RandomForestRegressor(n_estimators=50, random_state=42),
                'weight': 0.15,
                'accuracy': 0.71,
                'last_updated': datetime.now()
            },
            'momentum_model': {
                'model': None,  # Custom implementation
                'weight': 0.15,
                'accuracy': 0.69,
                'last_updated': datetime.now()
            }
        }
        
        # Historical accuracy tracking
        self.historical_accuracy = {}
        
        # Market regime detection
        self.market_regimes = {
            'BULL': {'threshold': 0.02, 'model_preference': ['momentum_model', 'linear_regression']},
            'BEAR': {'threshold': -0.02, 'model_preference': ['exponential_smoothing', 'moving_average']},
            'SIDEWAYS': {'threshold': 0.005, 'model_preference': ['random_forest', 'exponential_smoothing']}
        }
    
    def detect_market_regime(self, symbol: str) -> str:
        """
        Detect current market regime for the stock
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Market regime: BULL, BEAR, or SIDEWAYS
        """
        try:
            # Get recent price data
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            
            if hist.empty:
                return 'SIDEWAYS'  # Default
            
            # Calculate recent performance
            recent_return = (hist['Close'].iloc[-1] / hist['Close'].iloc[-20] - 1) if len(hist) >= 20 else 0
            
            # Classify regime
            if recent_return > self.market_regimes['BULL']['threshold']:
                return 'BULL'
            elif recent_return < self.market_regimes['BEAR']['threshold']:
                return 'BEAR'
            else:
                return 'SIDEWAYS'
                
        except Exception:
            return 'SIDEWAYS'
    
    def adjust_model_weights_by_regime(self, regime: str, sentiment_data: Optional[Dict] = None) -> None:
        """
        Adjust model weights based on market regime and sentiment
        
        Args:
            regime: Current market regime
            sentiment_data: Optional sentiment analysis data
        """
        if regime in self.market_regimes:
            preferred_models = self.market_regimes[regime]['model_preference']
            
            # Boost weights for preferred models
            boost_factor = 1.2
            total_weight = 0
            
            for model_name in self.models:
                if model_name in preferred_models:
                    self.models[model_name]['weight'] *= boost_factor
                total_weight += self.models[model_name]['weight']
            
            # NEW: Additional sentiment-based weight adjustments
            if sentiment_data:
                sentiment_score = sentiment_data.get('sentiment_score', 0)
                sentiment_strength = sentiment_data.get('sentiment_strength', 0)
                
                # Strong sentiment adjustments
                if abs(sentiment_score) > 2 and sentiment_strength > 1:
                    if sentiment_score > 0:  # Positive sentiment
                        # Boost momentum and trend-following models
                        self.models['momentum_model']['weight'] *= 1.3
                        self.models['moving_average']['weight'] *= 1.2
                        # Reduce contrarian models
                        self.models['exponential_smoothing']['weight'] *= 0.9
                    else:  # Negative sentiment
                        # Boost defensive and adaptive models
                        self.models['exponential_smoothing']['weight'] *= 1.3
                        self.models['random_forest']['weight'] *= 1.2
                        # Reduce momentum models
                        self.models['momentum_model']['weight'] *= 0.8
                
                # Recalculate total weight after sentiment adjustments
                total_weight = sum(model['weight'] for model in self.models.values())
            
            # Normalize weights to sum to 1.0
            for model_name in self.models:
                self.models[model_name]['weight'] /= total_weight
    
    def prepare_features(self, data: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare features for machine learning models
        
        Args:
            data: Historical price data
            
        Returns:
            Features and target arrays
        """
        # Technical indicators as features
        data['SMA_5'] = data['Close'].rolling(window=5).mean()
        data['SMA_10'] = data['Close'].rolling(window=10).mean()
        data['SMA_20'] = data['Close'].rolling(window=20).mean()
        data['RSI'] = self.calculate_rsi(data['Close'])
        data['Volume_MA'] = data['Volume'].rolling(window=10).mean()
        data['Price_Change'] = data['Close'].pct_change()
        data['Volume_Change'] = data['Volume'].pct_change()
        
        # Lag features
        for lag in [1, 2, 3, 5]:
            data[f'Close_lag_{lag}'] = data['Close'].shift(lag)
            data[f'Volume_lag_{lag}'] = data['Volume'].shift(lag)
        
        # Select features
        feature_columns = [
            'SMA_5', 'SMA_10', 'SMA_20', 'RSI', 'Volume_MA',
            'Price_Change', 'Volume_Change',
            'Close_lag_1', 'Close_lag_2', 'Close_lag_3', 'Close_lag_5',
            'Volume_lag_1', 'Volume_lag_2', 'Volume_lag_3', 'Volume_lag_5'
        ]
        
        # Remove NaN values
        data_clean = data.dropna()
        
        if len(data_clean) < 20:
            raise ValueError("Insufficient data for feature preparation")
        
        X = data_clean[feature_columns].values
        y = data_clean['Close'].values
        
        return X, y
    
    def calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI indicator"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def linear_regression_forecast(self, data: pd.DataFrame, days: int) -> List[float]:
        """Linear regression forecasting"""
        try:
            X, y = self.prepare_features(data)
            
            # Train model
            model = self.models['linear_regression']['model']
            model.fit(X, y)
            
            # Generate predictions
            predictions = []
            last_features = X[-1].reshape(1, -1)
            
            for _ in range(days):
                pred = model.predict(last_features)[0]
                predictions.append(pred)
                
                # Update features for next prediction (simplified)
                last_features[0][-1] = pred  # Update last close price
            
            return predictions
            
        except Exception as e:
            # Fallback to simple trend
            return [data['Close'].iloc[-1] * (1 + 0.001)] * days
    
    def moving_average_forecast(self, data: pd.DataFrame, days: int) -> List[float]:
        """Enhanced moving average forecasting"""
        try:
            # Multiple timeframe moving averages
            sma_5 = data['Close'].rolling(window=5).mean().iloc[-1]
            sma_10 = data['Close'].rolling(window=10).mean().iloc[-1]
            sma_20 = data['Close'].rolling(window=20).mean().iloc[-1]
            
            # Weighted combination
            ma_prediction = (sma_5 * 0.5 + sma_10 * 0.3 + sma_20 * 0.2)
            
            # Trend adjustment
            recent_trend = (data['Close'].iloc[-1] / data['Close'].iloc[-5] - 1) if len(data) >= 5 else 0
            
            predictions = []
            current_price = data['Close'].iloc[-1]
            
            for day in range(days):
                # Gradual convergence to MA with trend decay
                trend_factor = recent_trend * (0.9 ** day)  # Exponential decay
                ma_factor = 0.1 * day / days  # Gradual convergence to MA
                
                pred = current_price * (1 + trend_factor) + ma_prediction * ma_factor
                predictions.append(pred)
                current_price = pred
            
            return predictions
            
        except Exception:
            return [data['Close'].iloc[-1]] * days
    
    def exponential_smoothing_forecast(self, data: pd.DataFrame, days: int) -> List[float]:
        """Exponential smoothing forecasting"""
        try:
            prices = data['Close'].values
            
            # Calculate smoothing parameters
            alpha = 0.3  # Level smoothing
            beta = 0.2   # Trend smoothing
            
            # Initialize
            level = prices[0]
            trend = prices[1] - prices[0] if len(prices) > 1 else 0
            
            # Update level and trend
            for price in prices[1:]:
                new_level = alpha * price + (1 - alpha) * (level + trend)
                new_trend = beta * (new_level - level) + (1 - beta) * trend
                level, trend = new_level, new_trend
            
            # Generate forecasts
            predictions = []
            for day in range(1, days + 1):
                forecast = level + day * trend
                predictions.append(forecast)
            
            return predictions
            
        except Exception:
            return [data['Close'].iloc[-1]] * days
    
    def random_forest_forecast(self, data: pd.DataFrame, days: int) -> List[float]:
        """Random Forest forecasting"""
        try:
            X, y = self.prepare_features(data)
            
            # Train model
            model = self.models['random_forest']['model']
            model.fit(X, y)
            
            # Generate predictions
            predictions = []
            last_features = X[-1].reshape(1, -1)
            
            for _ in range(days):
                pred = model.predict(last_features)[0]
                predictions.append(pred)
                
                # Update features for next prediction
                last_features[0][-1] = pred
            
            return predictions
            
        except Exception as e:
            return [data['Close'].iloc[-1]] * days
    
    def apply_sentiment_bias_to_predictions(self, predictions: List[float], sentiment_data: Dict, 
                                           current_price: float, days: int) -> List[float]:
        """
        Apply sentiment bias to ensemble predictions
        
        Args:
            predictions: Base ensemble predictions
            sentiment_data: Sentiment analysis data
            current_price: Current stock price
            days: Number of forecast days
            
        Returns:
            Sentiment-adjusted predictions
        """
        try:
            sentiment_score = sentiment_data.get('sentiment_score', 0)
            sentiment_strength = sentiment_data.get('sentiment_strength', 0)
            article_count = sentiment_data.get('article_count', 0)
            
            # Calculate sentiment momentum effect
            # Scale based on sentiment strength and article reliability
            base_sentiment_effect = sentiment_score * sentiment_strength * 0.003  # Max 3% daily effect
            
            # Article count reliability factor (more articles = more reliable sentiment)
            reliability_factor = min(article_count / 5, 1.0)  # Cap at 5 articles for full reliability
            sentiment_momentum = base_sentiment_effect * reliability_factor
            
            # Apply diminishing effect over time
            adjusted_predictions = []
            for day, prediction in enumerate(predictions):
                # Sentiment effect decays exponentially over time
                decay_factor = 0.85 ** day  # Faster decay than market regime
                daily_sentiment_effect = sentiment_momentum * decay_factor
                
                # Apply the sentiment bias
                adjusted_price = prediction * (1 + daily_sentiment_effect)
                
                # Ensure prediction doesn't deviate too far from technical analysis
                max_deviation = 0.05  # 5% max deviation from technical prediction
                deviation = abs(adjusted_price - prediction) / prediction
                if deviation > max_deviation:
                    # Scale back the adjustment if it's too extreme
                    direction = 1 if adjusted_price > prediction else -1
                    adjusted_price = prediction * (1 + direction * max_deviation)
                
                adjusted_predictions.append(adjusted_price)
            
            return adjusted_predictions
            
        except Exception as e:
            print(f"Error applying sentiment bias: {e}")
            return predictions  # Return original predictions if error
    
    def momentum_model_forecast(self, data: pd.DataFrame, days: int) -> List[float]:
        """Momentum-based forecasting"""
        try:
            # Calculate various momentum indicators
            rsi = self.calculate_rsi(data['Close']).iloc[-1]
            
            # Price momentum (different timeframes)
            mom_5 = (data['Close'].iloc[-1] / data['Close'].iloc[-6] - 1) if len(data) >= 6 else 0
            mom_10 = (data['Close'].iloc[-1] / data['Close'].iloc[-11] - 1) if len(data) >= 11 else 0
            
            # Volume momentum
            vol_ratio = (data['Volume'].iloc[-5:].mean() / data['Volume'].iloc[-20:-5].mean()) if len(data) >= 20 else 1
            
            # Momentum score
            momentum_score = (mom_5 * 0.4 + mom_10 * 0.3) * (vol_ratio * 0.3)
            
            # RSI adjustment
            if rsi > 70:
                momentum_score *= 0.5  # Reduce momentum in overbought
            elif rsi < 30:
                momentum_score *= 1.5  # Increase momentum in oversold
            
            # Generate predictions
            predictions = []
            current_price = data['Close'].iloc[-1]
            
            for day in range(days):
                # Momentum decay over time
                decay_factor = 0.9 ** day
                daily_return = momentum_score * decay_factor / days
                
                pred = current_price * (1 + daily_return)
                predictions.append(pred)
                current_price = pred
            
            return predictions
            
        except Exception:
            return [data['Close'].iloc[-1]] * days
    
    def calculate_dynamic_confidence(self, symbol: str, predictions_dict: Dict[str, List[float]], 
                                   data: pd.DataFrame, sentiment_data: Optional[Dict] = None) -> float:
        """
        Calculate dynamic confidence score based on multiple factors including sentiment
        
        Args:
            symbol: Stock symbol
            predictions_dict: Dictionary of model predictions
            data: Historical data
            sentiment_data: Optional sentiment analysis data
            
        Returns:
            Confidence score (0-100)
        """
        try:
            base_confidence = 50.0
            
            # 1. Model agreement factor
            all_predictions = list(predictions_dict.values())
            if len(all_predictions) > 1:
                # Calculate variance between models
                final_predictions = [pred[-1] for pred in all_predictions]
                std_dev = np.std(final_predictions)
                mean_pred = np.mean(final_predictions)
                cv = std_dev / mean_pred if mean_pred != 0 else 1
                
                # Lower coefficient of variation = higher confidence
                agreement_factor = max(0, 30 * (1 - cv * 10))
                base_confidence += agreement_factor
            
            # 2. Historical accuracy for this stock
            if symbol in self.historical_accuracy:
                historical_factor = self.historical_accuracy[symbol] * 20
                base_confidence += historical_factor
            
            # 3. Data quality factor
            data_quality = min(len(data) / 60, 1.0)  # 60 days ideal
            base_confidence += data_quality * 10
            
            # 4. Volatility penalty
            if len(data) >= 20:
                volatility = data['Close'].pct_change().std()
                vol_penalty = min(volatility * 100, 20)  # Cap at 20 point penalty
                base_confidence -= vol_penalty
            
            # 5. Market regime bonus
            regime = self.detect_market_regime(symbol)
            if regime == 'BULL':
                base_confidence += 5
            elif regime == 'BEAR':
                base_confidence -= 5
            
            # 6. Volume confirmation
            if len(data) >= 10:
                recent_volume = data['Volume'].iloc[-5:].mean()
                historical_volume = data['Volume'].iloc[-20:-5].mean()
                vol_ratio = recent_volume / historical_volume if historical_volume > 0 else 1
                
                if 0.8 <= vol_ratio <= 1.5:  # Normal volume range
                    base_confidence += 5
                elif vol_ratio > 2.0:  # Very high volume
                    base_confidence += 10
            
            # 7. NEW: Sentiment confidence boost/penalty
            if sentiment_data:
                sentiment_score = sentiment_data.get('sentiment_score', 0)
                sentiment_strength = sentiment_data.get('sentiment_strength', 0)
                article_count = sentiment_data.get('article_count', 0)
                
                # Calculate sentiment confidence adjustment
                # Strong positive sentiment with good article count = confidence boost
                # Strong negative sentiment = confidence penalty for bullish predictions
                sentiment_factor = sentiment_score * sentiment_strength * min(article_count / 5, 1.0)
                
                # Scale to ±15 point adjustment
                sentiment_adjustment = max(-15, min(15, sentiment_factor))
                base_confidence += sentiment_adjustment
                
                # Additional boost if sentiment is very strong and consistent
                if abs(sentiment_score) > 3 and sentiment_strength > 2 and article_count >= 3:
                    base_confidence += 5  # High conviction sentiment bonus
            
            return max(10, min(95, base_confidence))  # Cap between 10-95%
            
        except Exception:
            return 50.0  # Default moderate confidence
    
    def determine_sentiment_enhanced_trend(self, price_change_pct: float, sentiment_data: Dict) -> str:
        """
        Determine trend direction enhanced with sentiment analysis
        
        Args:
            price_change_pct: Expected price change percentage
            sentiment_data: Sentiment analysis data
            
        Returns:
            Enhanced trend direction: BULLISH/BEARISH/NEUTRAL
        """
        try:
            sentiment_score = sentiment_data.get('sentiment_score', 0)
            sentiment_strength = sentiment_data.get('sentiment_strength', 0)
            
            # Base trend from price movement
            if price_change_pct > 2:
                base_trend = "BULLISH"
            elif price_change_pct < -2:
                base_trend = "BEARISH"
            else:
                base_trend = "NEUTRAL"
            
            # Strong sentiment can influence trend determination
            strong_sentiment_threshold = 3
            moderate_sentiment_threshold = 1.5
            
            if sentiment_strength > 1:  # Only consider sentiment if it has some strength
                if sentiment_score > strong_sentiment_threshold:
                    # Very strong positive sentiment
                    if base_trend != "BEARISH":
                        return "BULLISH"  # Override neutral, reinforce bullish
                    elif price_change_pct > -1:  # Weak bearish price signal
                        return "NEUTRAL"  # Sentiment fights weak bearish signal
                        
                elif sentiment_score < -strong_sentiment_threshold:
                    # Very strong negative sentiment
                    if base_trend != "BULLISH":
                        return "BEARISH"  # Override neutral, reinforce bearish
                    elif price_change_pct < 1:  # Weak bullish price signal
                        return "NEUTRAL"  # Sentiment fights weak bullish signal
                        
                elif sentiment_score > moderate_sentiment_threshold and base_trend == "NEUTRAL":
                    # Moderate positive sentiment can tip neutral to bullish
                    return "BULLISH"
                    
                elif sentiment_score < -moderate_sentiment_threshold and base_trend == "NEUTRAL":
                    # Moderate negative sentiment can tip neutral to bearish
                    return "BEARISH"
            
            return base_trend
            
        except Exception:
            # Fallback to price-only trend
            if price_change_pct > 2:
                return "BULLISH"
            elif price_change_pct < -2:
                return "BEARISH"
            else:
                return "NEUTRAL"
    
    def predict_trend(self, symbol: str, days: int = 7) -> Optional[Dict]:
        """
        Enhanced ensemble prediction with sentiment integration
        
        Args:
            symbol: Stock symbol to forecast
            days: Number of trading days to forecast
            
        Returns:
            Enhanced forecast results with sentiment-integrated predictions
        """
        try:
            # Get historical data
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo")
            
            if hist.empty or len(hist) < 30:
                return None
            
            current_price = hist['Close'].iloc[-1]
            
            # NEW: Get sentiment analysis for the stock
            sentiment_data = self.sentiment_analyzer.get_news_sentiment(symbol)
            
            # Detect market regime
            regime = self.detect_market_regime(symbol)
            
            # Adjust weights based on regime AND sentiment
            self.adjust_model_weights_by_regime(regime, sentiment_data)
            
            # Get predictions from all models
            predictions_dict = {}
            
            # Linear Regression
            try:
                predictions_dict['linear_regression'] = self.linear_regression_forecast(hist, days)
            except Exception:
                predictions_dict['linear_regression'] = [current_price] * days
            
            # Moving Average
            predictions_dict['moving_average'] = self.moving_average_forecast(hist, days)
            
            # Exponential Smoothing
            predictions_dict['exponential_smoothing'] = self.exponential_smoothing_forecast(hist, days)
            
            # Random Forest
            try:
                predictions_dict['random_forest'] = self.random_forest_forecast(hist, days)
            except Exception:
                predictions_dict['random_forest'] = [current_price] * days
            
            # Momentum Model
            predictions_dict['momentum_model'] = self.momentum_model_forecast(hist, days)
            
            # Ensemble combination
            ensemble_predictions = []
            for day_idx in range(days):
                weighted_sum = 0
                total_weight = 0
                
                for model_name, predictions in predictions_dict.items():
                    if day_idx < len(predictions):
                        weight = self.models[model_name]['weight']
                        weighted_sum += predictions[day_idx] * weight
                        total_weight += weight
                
                if total_weight > 0:
                    ensemble_predictions.append(weighted_sum / total_weight)
                else:
                    ensemble_predictions.append(current_price)
            
            # NEW: Apply sentiment bias to ensemble predictions
            sentiment_adjusted_predictions = self.apply_sentiment_bias_to_predictions(
                ensemble_predictions, sentiment_data, current_price, days
            )
            
            # Calculate dynamic confidence with sentiment
            confidence = self.calculate_dynamic_confidence(symbol, predictions_dict, hist, sentiment_data)
            
            # Generate trading dates (excluding weekends)
            trading_dates = []
            current_date = datetime.now().date()
            days_added = 0
            
            while days_added < days:
                current_date += timedelta(days=1)
                if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                    trading_dates.append(current_date.strftime('%Y-%m-%d'))
                    days_added += 1
            
            # Format predictions
            predictions = []
            for i, (date, price) in enumerate(zip(trading_dates, sentiment_adjusted_predictions)):
                predictions.append({
                    'date': date,
                    'price': price
                })
            
            # Determine trend direction with sentiment enhancement
            final_price = sentiment_adjusted_predictions[-1]
            total_change = ((final_price - current_price) / current_price) * 100
            
            trend_direction = self.determine_sentiment_enhanced_trend(total_change, sentiment_data)
            
            return {
                'symbol': symbol,
                'current_price': current_price,
                'predictions': predictions,
                'trend_direction': trend_direction,
                'confidence': confidence,
                'total_change_percent': total_change,
                'market_regime': regime,
                'model_weights': {name: data['weight'] for name, data in self.models.items()},
                'individual_predictions': predictions_dict,
                'ensemble_method': 'weighted_average_with_sentiment',
                'sentiment_data': {
                    'sentiment_score': sentiment_data.get('sentiment_score', 0),
                    'sentiment_strength': sentiment_data.get('sentiment_strength', 0),
                    'article_count': sentiment_data.get('article_count', 0),
                    'positive_articles': sentiment_data.get('positive_articles', 0),
                    'negative_articles': sentiment_data.get('negative_articles', 0),
                    'headlines_sample': sentiment_data.get('headlines_sample', [])[:3]  # Top 3 headlines
                }
            }
            
        except Exception as e:
            print(f"Error in sentiment-enhanced ensemble prediction: {e}")
            return None
    
    def update_model_accuracy(self, symbol: str, predicted_price: float, actual_price: float, 
                            model_name: str) -> None:
        """
        Update model accuracy tracking for continuous improvement
        
        Args:
            symbol: Stock symbol
            predicted_price: Previously predicted price
            actual_price: Actual observed price
            model_name: Name of the model that made the prediction
        """
        try:
            # Calculate accuracy
            accuracy = 1 - abs(predicted_price - actual_price) / actual_price
            
            # Update model accuracy
            if model_name in self.models:
                current_accuracy = self.models[model_name]['accuracy']
                # Exponential moving average of accuracy
                new_accuracy = 0.9 * current_accuracy + 0.1 * accuracy
                self.models[model_name]['accuracy'] = new_accuracy
                self.models[model_name]['last_updated'] = datetime.now()
            
            # Update stock-specific accuracy
            if symbol not in self.historical_accuracy:
                self.historical_accuracy[symbol] = accuracy
            else:
                # Exponential moving average
                self.historical_accuracy[symbol] = (0.8 * self.historical_accuracy[symbol] + 
                                                  0.2 * accuracy)
            
            # Rebalance model weights based on updated accuracy
            self.rebalance_model_weights()
            
        except Exception as e:
            print(f"Error updating model accuracy: {e}")
    
    def rebalance_model_weights(self) -> None:
        """
        Rebalance model weights based on current accuracy scores
        """
        try:
            # Calculate total accuracy
            total_accuracy = sum(model['accuracy'] for model in self.models.values())
            
            if total_accuracy > 0:
                # Assign weights proportional to accuracy
                for model_name, model_data in self.models.items():
                    self.models[model_name]['weight'] = model_data['accuracy'] / total_accuracy
                    
        except Exception as e:
            print(f"Error rebalancing weights: {e}")
