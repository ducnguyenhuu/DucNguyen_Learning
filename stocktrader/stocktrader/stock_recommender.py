"""
Stock Recommender Module
Analyzes stocks and provides investment recommendations based on 
technical and fundamental analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

# Handle both direct execution and package execution
try:
    from stocktrader.data_manager import DataManager
except ImportError:
    from data_manager import DataManager


class StockRecommender:
    """Provides intelligent stock investment recommendations"""
    
    def __init__(self, data_manager: DataManager):
        self.data_manager = data_manager
        
        # Scoring weights for different criteria
        self.weights = {
            'pe_ratio': 0.20,       # Lower P/E is better
            'roe': 0.15,            # Higher ROE is better
            'debt_to_equity': 0.10, # Lower debt is better
            'revenue_growth': 0.15, # Higher growth is better
            'profit_margin': 0.10,  # Higher margin is better
            'dividend_yield': 0.10, # Dividend preference
            'market_cap': 0.10,     # Stability preference
            'technical': 0.10       # Technical indicators
        }
    
    def calculate_fundamental_score(self, stock_info: Dict) -> float:
        """
        Calculate fundamental analysis score (0-10)
        
        Args:
            stock_info: Stock information dictionary
            
        Returns:
            Fundamental score from 0 to 10
        """
        score = 0.0
        
        # P/E Ratio scoring (lower is better, reasonable range 5-25)
        pe_ratio = stock_info.get('pe_ratio')
        if pe_ratio and pe_ratio > 0:
            if pe_ratio < 15:
                score += 10 * self.weights['pe_ratio']
            elif pe_ratio < 25:
                score += 7 * self.weights['pe_ratio']
            else:
                score += 3 * self.weights['pe_ratio']
        else:
            score += 5 * self.weights['pe_ratio']  # Neutral for missing P/E
        
        # ROE scoring (higher is better, >15% is excellent)
        roe = stock_info.get('roe', 0)
        if roe > 20:
            score += 10 * self.weights['roe']
        elif roe > 15:
            score += 8 * self.weights['roe']
        elif roe > 10:
            score += 6 * self.weights['roe']
        else:
            score += 3 * self.weights['roe']
        
        # Debt-to-Equity scoring (lower is better)
        debt_to_equity = stock_info.get('debt_to_equity', 50)
        if debt_to_equity < 30:
            score += 10 * self.weights['debt_to_equity']
        elif debt_to_equity < 50:
            score += 7 * self.weights['debt_to_equity']
        else:
            score += 4 * self.weights['debt_to_equity']
        
        # Revenue Growth scoring
        revenue_growth = stock_info.get('revenue_growth', 0)
        if revenue_growth > 20:
            score += 10 * self.weights['revenue_growth']
        elif revenue_growth > 10:
            score += 8 * self.weights['revenue_growth']
        elif revenue_growth > 5:
            score += 6 * self.weights['revenue_growth']
        else:
            score += 3 * self.weights['revenue_growth']
        
        # Profit Margin scoring
        profit_margin = stock_info.get('profit_margin', 0)
        if profit_margin > 20:
            score += 10 * self.weights['profit_margin']
        elif profit_margin > 10:
            score += 8 * self.weights['profit_margin']
        elif profit_margin > 5:
            score += 6 * self.weights['profit_margin']
        else:
            score += 3 * self.weights['profit_margin']
        
        # Dividend Yield (preference for dividend-paying stocks)
        dividend_yield = stock_info.get('dividend_yield', 0)
        if dividend_yield > 3:
            score += 10 * self.weights['dividend_yield']
        elif dividend_yield > 1:
            score += 7 * self.weights['dividend_yield']
        else:
            score += 5 * self.weights['dividend_yield']
        
        # Market Cap (stability factor)
        market_cap = stock_info.get('market_cap', 0)
        if market_cap > 100_000_000_000:  # >100B = Large cap
            score += 8 * self.weights['market_cap']
        elif market_cap > 10_000_000_000:  # >10B = Mid cap
            score += 7 * self.weights['market_cap']
        else:
            score += 5 * self.weights['market_cap']
        
        return min(score, 10.0)  # Cap at 10
    
    def calculate_technical_score(self, symbol: str) -> float:
        """
        Calculate technical analysis score based on recent price action
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Technical score from 0 to 10
        """
        try:
            # Get 3 months of data for technical analysis
            data = self.data_manager.get_historical_data(symbol, "3mo")
            
            if data.empty or len(data) < 20:
                return 5.0  # Neutral score if insufficient data
            
            score = 0.0
            
            # Calculate simple moving averages
            data['SMA_20'] = data['Close'].rolling(window=20).mean()
            data['SMA_50'] = data['Close'].rolling(window=50).mean() if len(data) >= 50 else data['Close'].rolling(window=len(data)//2).mean()
            
            current_price = data['Close'].iloc[-1]
            sma_20 = data['SMA_20'].iloc[-1]
            sma_50 = data['SMA_50'].iloc[-1]
            
            # Price above moving averages is bullish
            if current_price > sma_20:
                score += 3
            if current_price > sma_50:
                score += 3
            
            # SMA trend (20 > 50 is bullish)
            if sma_20 > sma_50:
                score += 2
            
            # Volume trend (recent volume higher than average)
            recent_volume = data['Volume'].tail(5).mean()
            avg_volume = data['Volume'].mean()
            if recent_volume > avg_volume * 1.2:
                score += 2
            
            return min(score, 10.0)
            
        except Exception as e:
            print(f"Warning: Technical analysis failed for {symbol}: {e}")
            return 5.0  # Neutral score on error
    
    def generate_recommendation_reason(self, stock_info: Dict, fund_score: float, tech_score: float) -> str:
        """
        Generate human-readable recommendation reason
        
        Args:
            stock_info: Stock information dictionary
            fund_score: Fundamental score
            tech_score: Technical score
            
        Returns:
            Recommendation reasoning string
        """
        reasons = []
        
        # Fundamental reasons
        if fund_score > 7:
            if stock_info.get('roe', 0) > 15:
                reasons.append("Strong ROE")
            if stock_info.get('pe_ratio') and stock_info['pe_ratio'] < 20:
                reasons.append("Reasonable valuation")
            if stock_info.get('revenue_growth', 0) > 10:
                reasons.append("Good growth")
        
        # Technical reasons
        if tech_score > 7:
            reasons.append("Positive momentum")
        elif tech_score < 4:
            reasons.append("Technical weakness")
        
        # Market cap consideration
        market_cap = stock_info.get('market_cap', 0)
        if market_cap > 100_000_000_000:
            reasons.append("Large-cap stability")
        
        # Sector leadership
        if stock_info.get('symbol') in ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']:
            reasons.append("Market leader")
        
        if not reasons:
            reasons = ["Balanced fundamentals"]
        
        return ", ".join(reasons[:3])  # Limit to top 3 reasons
    
    def get_investment_recommendations(self, sector: Optional[str] = None, 
                                     market_cap: Optional[str] = None, 
                                     count: int = 10) -> List[Dict]:
        """
        Get stock investment recommendations based on analysis
        
        Args:
            sector: Filter by sector (e.g., 'technology', 'healthcare')
            market_cap: Filter by market cap ('large', 'mid', 'small')
            count: Number of recommendations to return
            
        Returns:
            List of recommended stocks with scores and reasoning
        """
        print(f"Analyzing stocks for recommendations...")
        
        # Get symbols to analyze
        symbols = self.data_manager.get_market_sector_symbols(sector)
        
        # Expand symbol list for better coverage
        if len(symbols) < 30:
            symbols.extend(self.data_manager.popular_symbols)
            symbols = list(set(symbols))  # Remove duplicates
        
        # Fetch stock information
        stocks_info = self.data_manager.get_multiple_stocks_info(symbols)
        
        if not stocks_info:
            print("Warning: No stock data could be fetched")
            return []
        
        print(f"Scoring {len(stocks_info)} stocks...")
        
        recommendations = []
        
        for stock_info in stocks_info:
            try:
                # Filter by market cap if specified
                if market_cap:
                    market_cap_value = stock_info.get('market_cap', 0)
                    if market_cap == 'large' and market_cap_value < 10_000_000_000:
                        continue
                    elif market_cap == 'mid' and (market_cap_value < 2_000_000_000 or market_cap_value > 10_000_000_000):
                        continue
                    elif market_cap == 'small' and market_cap_value > 2_000_000_000:
                        continue
                
                # Calculate scores
                fundamental_score = self.calculate_fundamental_score(stock_info)
                technical_score = self.calculate_technical_score(stock_info['symbol'])
                
                # Combined score (weighted average)
                # update weighted here
                total_score = (fundamental_score * 0.5) + (technical_score * 0.5)
                
                # Generate recommendation reason
                reason = self.generate_recommendation_reason(stock_info, fundamental_score, technical_score)
                
                recommendation = {
                    'symbol': stock_info['symbol'],
                    'name': stock_info['name'],
                    'price': stock_info['price'],
                    'score': total_score,
                    'fundamental_score': fundamental_score,
                    'technical_score': technical_score,
                    'reason': reason,
                    'sector': stock_info['sector'],
                    'pe_ratio': f"{stock_info.get('pe_ratio', 0):.1f}" if stock_info.get('pe_ratio') else "N/A",
                    'roe': f"{stock_info.get('roe', 0):.1f}" if stock_info.get('roe') else "N/A",
                    'market_cap': stock_info.get('market_cap', 0)
                }
                
                recommendations.append(recommendation)
                
            except Exception as e:
                print(f"Warning: Error processing {stock_info.get('symbol', 'Unknown')}: {e}")
                continue
        
        # Sort by score and return top recommendations
        recommendations.sort(key=lambda x: x['score'], reverse=True)
        
        print(f"Generated {len(recommendations)} recommendations")
        return recommendations[:count]
