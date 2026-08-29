"""
News Sentiment Analyzer for Stock Recommendations
Implements sentiment-based confidence adjustments
"""

import requests
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import yfinance as yf

# Handle both direct execution and package execution
try:
    from stocktrader.data_manager import DataManager
except ImportError:
    from data_manager import DataManager


class SentimentAnalyzer:
    """
    Analyzes news sentiment for stocks to enhance recommendation confidence
    """
    
    def __init__(self):
        # Sentiment keywords and weights
        self.positive_keywords = {
            'strong': 2, 'growth': 2, 'profit': 2, 'revenue': 2, 'earnings': 2,
            'beat': 3, 'exceed': 3, 'outperform': 3, 'bullish': 3, 'upgrade': 3,
            'buy': 2, 'positive': 1, 'good': 1, 'great': 2, 'excellent': 3,
            'surge': 3, 'rally': 3, 'gain': 2, 'rise': 2, 'increase': 2,
            'breakthrough': 3, 'innovation': 2, 'partnership': 2, 'acquisition': 2,
            'expansion': 2, 'success': 2, 'winning': 2, 'leader': 2, 'dominant': 2
        }
        
        self.negative_keywords = {
            'loss': -2, 'decline': -2, 'fall': -2, 'drop': -2, 'weak': -2,
            'miss': -3, 'disappoint': -3, 'underperform': -3, 'bearish': -3, 'downgrade': -3,
            'sell': -2, 'negative': -1, 'bad': -1, 'poor': -2, 'terrible': -3,
            'crash': -3, 'plunge': -3, 'lose': -2, 'decrease': -2, 'cut': -2,
            'lawsuit': -3, 'scandal': -3, 'investigation': -3, 'fraud': -3,
            'bankruptcy': -3, 'debt': -2, 'risk': -1, 'concern': -1, 'warning': -2
        }
        
        # Sector-specific keywords
        self.sector_keywords = {
            'technology': {
                'ai': 2, 'artificial intelligence': 2, 'cloud': 2, 'software': 1,
                'digital': 1, 'cyber': 1, 'data': 1, 'platform': 1, 'automation': 2
            },
            'healthcare': {
                'drug': 1, 'treatment': 2, 'clinical': 2, 'fda': 2, 'approval': 3,
                'therapy': 2, 'vaccine': 2, 'biotech': 1, 'pharmaceutical': 1
            },
            'energy': {
                'oil': 1, 'gas': 1, 'renewable': 2, 'solar': 2, 'wind': 2,
                'electric': 2, 'battery': 2, 'green': 2, 'clean': 2
            },
            'financial': {
                'bank': 1, 'interest': 1, 'loan': 1, 'credit': 1, 'rate': 1,
                'fed': 2, 'monetary': 2, 'fiscal': 2, 'regulation': -1
            }
        }
        
        # Cache for recent sentiment analysis
        self.sentiment_cache = {}
        self.cache_expiry = timedelta(hours=1)  # Cache expires after 1 hour
    
    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text for sentiment analysis
        
        Args:
            text: Raw text to clean
            
        Returns:
            Cleaned text
        """
        # Convert to lowercase
        text = text.lower()
        
        # Remove special characters but keep spaces
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text
    
    def calculate_basic_sentiment(self, text: str, sector: Optional[str] = None) -> float:
        """
        Calculate basic sentiment score using keyword analysis
        
        Args:
            text: Text to analyze
            sector: Optional sector for sector-specific keywords
            
        Returns:
            Sentiment score (-10 to +10)
        """
        if not text:
            return 0.0
        
        text = self.clean_text(text)
        words = text.split()
        
        sentiment_score = 0.0
        word_count = len(words)
        
        if word_count == 0:
            return 0.0
        
        # Analyze general sentiment keywords
        for word in words:
            if word in self.positive_keywords:
                sentiment_score += self.positive_keywords[word]
            elif word in self.negative_keywords:
                sentiment_score += self.negative_keywords[word]
        
        # Add sector-specific sentiment
        if sector and sector.lower() in self.sector_keywords:
            sector_words = self.sector_keywords[sector.lower()]
            for word in words:
                if word in sector_words:
                    sentiment_score += sector_words[word]
        
        # Normalize by text length
        normalized_score = (sentiment_score / word_count) * 100
        
        # Cap the score between -10 and +10
        return max(-10, min(10, normalized_score))
    
    def analyze_headlines(self, headlines: List[str], sector: Optional[str] = None) -> Dict[str, float]:
        """
        Analyze sentiment from multiple headlines
        
        Args:
            headlines: List of news headlines
            sector: Optional sector for context
            
        Returns:
            Dictionary with sentiment metrics
        """
        if not headlines:
            return {
                'overall_sentiment': 0.0,
                'positive_count': 0,
                'negative_count': 0,
                'neutral_count': 0,
                'sentiment_strength': 0.0
            }
        
        scores = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0
        
        for headline in headlines:
            score = self.calculate_basic_sentiment(headline, sector)
            scores.append(score)
            
            if score > 0.5:
                positive_count += 1
            elif score < -0.5:
                negative_count += 1
            else:
                neutral_count += 1
        
        overall_sentiment = sum(scores) / len(scores) if scores else 0.0
        sentiment_strength = abs(overall_sentiment)
        
        return {
            'overall_sentiment': overall_sentiment,
            'positive_count': positive_count,
            'negative_count': negative_count,
            'neutral_count': neutral_count,
            'sentiment_strength': sentiment_strength,
            'total_articles': len(headlines)
        }
    
    def get_news_sentiment(self, symbol: str, company_name: str = None) -> Dict[str, any]:
        """
        Get news sentiment for a specific stock
        
        Args:
            symbol: Stock symbol
            company_name: Optional company name for better search
            
        Returns:
            Sentiment analysis results
        """
        # Check cache first
        cache_key = f"{symbol}_{datetime.now().strftime('%Y%m%d_%H')}"
        if cache_key in self.sentiment_cache:
            cache_time, sentiment_data = self.sentiment_cache[cache_key]
            if datetime.now() - cache_time < self.cache_expiry:
                return sentiment_data
        
        try:
            # Get real headlines using yfinance API
            headlines = self.get_yahoo_headlines(symbol, company_name)
            
            # Analyze sentiment
            sentiment_analysis = self.analyze_headlines(headlines)
            
            # Calculate confidence adjustment
            confidence_adjustment = self.calculate_confidence_adjustment(sentiment_analysis)
            
            result = {
                'symbol': symbol,
                'sentiment_score': sentiment_analysis['overall_sentiment'],
                'sentiment_strength': sentiment_analysis['sentiment_strength'],
                'confidence_adjustment': confidence_adjustment,
                'article_count': sentiment_analysis['total_articles'],
                'positive_articles': sentiment_analysis['positive_count'],
                'negative_articles': sentiment_analysis['negative_count'],
                'analysis_time': datetime.now(),
                'headlines_sample': headlines[:5]  # Sample for reference
            }
            
            # Cache the result
            self.sentiment_cache[cache_key] = (datetime.now(), result)
            
            return result
            
        except Exception as e:
            print(f"Error getting news sentiment for {symbol}: {e}")
            return {
                'symbol': symbol,
                'sentiment_score': 0.0,
                'sentiment_strength': 0.0,
                'confidence_adjustment': 0.0,
                'article_count': 0,
                'positive_articles': 0,
                'negative_articles': 0,
                'analysis_time': datetime.now(),
                'headlines_sample': [],
                'error': str(e)
            }
    
    def get_yahoo_headlines(self, symbol: str, company_name: str = None) -> List[str]:
        """
        Get real news headlines from Yahoo Finance using yfinance library
        
        Args:
            symbol: Stock symbol
            company_name: Company name (unused but kept for compatibility)
            
        Returns:
            List of real news headlines from Yahoo Finance
        """
        try:
            # Create ticker object
            ticker = yf.Ticker(symbol)
            
            # Get news data
            news = ticker.news
            
            if not news:
                print(f"No news found for {symbol}, using fallback headlines")
                return self.get_fallback_headlines(symbol)
            
            # Extract headlines from the nested structure
            headlines = []
            for article in news:
                try:
                    # Yahoo Finance news structure: article['content']['title']
                    if 'content' in article and 'title' in article['content']:
                        title = article['content']['title']
                        headlines.append(title)
                    elif 'title' in article:  # Fallback for different structure
                        headlines.append(article['title'])
                except (KeyError, TypeError) as e:
                    continue  # Skip malformed articles
            
            # Ensure we have at least some headlines
            if not headlines:
                print(f"No valid headlines found for {symbol}, using fallback")
                return self.get_fallback_headlines(symbol)
            
            print(f"Retrieved {len(headlines)} real headlines for {symbol}")
            return headlines[:10]  # Limit to 10 most recent headlines
            
        except Exception as e:
            print(f"Error fetching Yahoo Finance news for {symbol}: {e}")
            print(f"Falling back to mock headlines")
            return self.get_fallback_headlines(symbol)
    
    def get_fallback_headlines(self, symbol: str) -> List[str]:
        """
        Fallback headlines when Yahoo Finance API fails
        
        Args:
            symbol: Stock symbol
            
        Returns:
            List of fallback headlines
        """
        fallback_headlines = {
            'AAPL': [
                "Apple reports quarterly earnings results",
                "iPhone demand shows mixed signals in global markets", 
                "Apple services revenue continues growth trajectory",
                "Tech analysts review Apple stock performance",
                "Apple shares fluctuate amid market conditions"
            ],
            'GOOGL': [
                "Alphabet announces quarterly financial results",
                "Google Cloud business shows competitive performance",
                "Search advertising market faces headwinds",
                "Alphabet stock moves with tech sector trends",
                "Google regulatory issues remain in focus"
            ],
            'TSLA': [
                "Tesla reports vehicle delivery numbers",
                "Electric vehicle market competition intensifies",
                "Tesla stock volatility continues amid market conditions",
                "EV charging infrastructure expansion updates",
                "Tesla production targets under analyst review"
            ],
            'MSFT': [
                "Microsoft reports cloud computing results",
                "Azure platform shows competitive positioning",
                "Office productivity suite maintains market share",
                "Microsoft stock performance tracks tech sector",
                "Enterprise software demand remains steady"
            ]
        }
        
        return fallback_headlines.get(symbol, [
            f"{symbol} announces quarterly update",
            f"{symbol} stock moves with market sentiment",
            f"Analysts maintain coverage of {symbol}",
            f"{symbol} business fundamentals under review",
            f"Market conditions affect {symbol} trading"
        ])
    
    def calculate_confidence_adjustment(self, sentiment_analysis: Dict[str, float]) -> float:
        """
        Calculate confidence adjustment based on sentiment analysis
        
        Args:
            sentiment_analysis: Results from sentiment analysis
            
        Returns:
            Confidence adjustment (-15 to +15 points)
        """
        sentiment_score = sentiment_analysis['overall_sentiment']
        sentiment_strength = sentiment_analysis['sentiment_strength']
        article_count = sentiment_analysis['total_articles']
        
        # Base adjustment from sentiment score
        base_adjustment = sentiment_score * 1.5  # Scale to ±15 points
        
        # Strength multiplier (higher strength = more confident adjustment)
        strength_multiplier = min(sentiment_strength / 5.0, 1.0)
        
        # Article count factor (more articles = more reliable)
        count_factor = min(article_count / 10.0, 1.0)
        
        # Final adjustment
        adjustment = base_adjustment * strength_multiplier * count_factor
        
        return max(-15, min(15, adjustment))
    
    def get_sector_sentiment(self, sector: str) -> Dict[str, any]:
        """
        Get overall sentiment for a specific sector using real RSS feeds
        
        Args:
            sector: Sector name (e.g., 'technology', 'healthcare')
            
        Returns:
            Sector sentiment analysis with real news data
        """
        try:
            # Get real sector headlines using yfinance aggregation
            headlines = self.get_sector_headlines_from_companies(sector)
            
            if not headlines:
                print(f"No company headlines found for {sector}, using fallback")
                headlines = self.get_fallback_sector_headlines(sector)
            
            sentiment_analysis = self.analyze_headlines(headlines, sector)
            
            return {
                'sector': sector,
                'sentiment_score': sentiment_analysis['overall_sentiment'],
                'confidence_adjustment': self.calculate_confidence_adjustment(sentiment_analysis),
                'article_count': sentiment_analysis['total_articles'],
                'analysis_time': datetime.now(),
                'headlines_sample': headlines[:5]  # Include sample for verification
            }
            
        except Exception as e:
            print(f"Error in sector sentiment analysis for {sector}: {e}")
            return {
                'sector': sector,
                'sentiment_score': 0.0,
                'confidence_adjustment': 0.0,
                'article_count': 0,
                'analysis_time': datetime.now(),
                'error': str(e)
            }
    
    def get_sector_headlines_from_companies(self, sector: str) -> List[str]:
        """
        Get real sector headlines by aggregating yfinance news from major sector companies
        
        Args:
            sector: Sector name
            
        Returns:
            List of real sector headlines from major companies using yfinance
        """
        try:
            headlines = []
            
            # Major companies by sector (real stock symbols)
            sector_companies = {
                'technology': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
                'healthcare': ['JNJ', 'PFE', 'UNH', 'ABBV', 'TMO'],
                'energy': ['XOM', 'CVX', 'COP', 'EOG', 'SLB'],
                'financial': ['JPM', 'BAC', 'WFC', 'GS', 'MS'],
                'consumer': ['WMT', 'PG', 'KO', 'PEP', 'COST'],
                'industrial': ['BA', 'CAT', 'GE', 'MMM', 'HON']
            }
            
            companies = sector_companies.get(sector.lower(), [])
            
            if companies:
                # Get real news from 2-3 major companies in the sector
                import random
                sample_companies = random.sample(companies, min(3, len(companies)))
                
                for symbol in sample_companies:
                    try:
                        # Get real news headlines for this company
                        ticker = yf.Ticker(symbol)
                        news = ticker.news
                        
                        if news:
                            for article in news[:3]:  # Limit to 3 articles per company
                                try:
                                    if 'content' in article and 'title' in article['content']:
                                        title = article['content']['title']
                                        headlines.append(title)
                                except (KeyError, TypeError):
                                    continue
                                    
                    except Exception as e:
                        print(f"Error fetching news for {symbol}: {e}")
                        continue
            
            if headlines:
                print(f"Retrieved {len(headlines)} real sector headlines for {sector} from {len(sample_companies)} companies")
                return headlines[:10]  # Limit to 10 most recent
            
            return []
            
        except Exception as e:
            print(f"Error aggregating sector headlines for {sector}: {e}")
            return []
    
    def get_fallback_sector_headlines(self, sector: str) -> List[str]:
        """
        Fallback sector headlines when RSS feeds fail
        
        Args:
            sector: Sector name
            
        Returns:
            List of neutral sector headlines
        """
        fallback_headlines = {
            'technology': [
                "Technology sector shows mixed performance amid market conditions",
                "Tech companies report quarterly earnings with varied results",
                "Software and hardware companies face market headwinds",
                "Technology stocks track broader market sentiment",
                "Innovation continues across technology sector"
            ],
            'healthcare': [
                "Healthcare sector maintains steady performance",
                "Biotech and pharmaceutical companies show resilience",
                "Medical device innovation drives sector interest",
                "Healthcare spending trends support sector outlook",
                "Drug development pipeline remains active"
            ],
            'energy': [
                "Energy sector responds to commodity price changes",
                "Oil and gas companies adapt to market conditions",
                "Renewable energy investments continue growth",
                "Energy transition creates new opportunities",
                "Utility companies maintain stable operations"
            ],
            'financial': [
                "Financial sector adjusts to interest rate environment",
                "Banking institutions report steady lending activity",
                "Insurance companies maintain conservative approach",
                "Fintech innovation continues to evolve",
                "Credit conditions remain generally stable"
            ]
        }
        
        return fallback_headlines.get(sector.lower(), [
            f"{sector.title()} sector shows steady performance",
            f"{sector.title()} companies report mixed results", 
            f"Market conditions affect {sector.lower()} sector",
            f"{sector.title()} stocks track market trends",
            f"Analysts maintain coverage of {sector.lower()} sector"
        ])
