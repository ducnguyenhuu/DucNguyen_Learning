"""
StockTrader Main Application
Entry point for the stock trading analysis console application
"""

import sys
from typing import Optional

# Handle both direct execution and package execution
try:
    # When running as package: python -m stocktrader
    from stocktrader.ensemble_forecaster import EnsembleForecaster
    from stocktrader.data_manager import DataManager
    from stocktrader.stock_recommender import StockRecommender
except ImportError:
    # When running directly: python main.py or debugging in VS Code
    from ensemble_forecaster import EnsembleForecaster
    from data_manager import DataManager
    from stock_recommender import StockRecommender


class StockTrader:
    """Main application class for StockTrader console"""
    
    def __init__(self):
        self.data_manager = DataManager()
        self.forecaster = EnsembleForecaster(self.data_manager)
        self.recommender = StockRecommender(self.data_manager)
    
    def recommend_stocks(self, sector: Optional[str] = None, market_cap: Optional[str] = None, 
                        count: int = 10, fortune_500: bool = True) -> None:
        """
        Get stock recommendations using ensemble forecasting with sentiment analysis
        
        Args:
            sector: Specific sector to focus on (e.g., 'Technology', 'Healthcare')  
            market_cap: Market cap filter ('large', 'mid', 'small')
            count: Number of recommendations to return
            fortune_500: Whether to use Fortune 500 companies for analysis (default: True)
        """
        print("🚀 StockTrader - Fortune 500 Ensemble Forecasting Analysis")
        print("=" * 70)
        
        try:
            # Load Fortune 500 companies from config
            import json
            import os
            
            config_path = os.path.join(os.path.dirname(__file__), 'config', 'popular_symbols.json')
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            if fortune_500 and 'fortune_500_companies' in config_data:
                fortune_companies = config_data['fortune_500_companies']
                sectors_data = config_data.get('sectors', {})
                
                # Filter by sector if specified
                if sector and sector.lower() in [s.lower() for s in sectors_data.keys()]:
                    # Find matching sector key (case-insensitive)
                    sector_key = next(s for s in sectors_data.keys() if s.lower() == sector.lower())
                    sector_symbols = sectors_data[sector_key]
                    symbols = [company['symbol'] for company in fortune_companies 
                             if company['symbol'] in sector_symbols][:count*2]  # Get more for filtering
                    print(f"📊 Analyzing {sector} sector Fortune 500 companies...")
                else:
                    # Use top Fortune 500 companies by rank
                    symbols = [company['symbol'] for company in fortune_companies[:count*3]]  # Get more for robust analysis
                    print(f"📊 Analyzing top Fortune 500 companies...")
                    
            else:
                # Fallback to original logic if Fortune 500 data not available
                if sector and sector.lower() == 'technology':
                    symbols = ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA', 'META', 'AMZN', 'CRM', 'ORCL', 'ADBE']
                elif sector and sector.lower() == 'healthcare':
                    symbols = ['JNJ', 'PFE', 'UNH', 'ABBV', 'TMO', 'MDT', 'DHR', 'BMY', 'AMGN', 'GILD']
                elif sector and sector.lower() == 'financial':
                    symbols = ['JPM', 'BAC', 'WFC', 'GS', 'MS', 'C', 'BRK-B', 'V', 'MA', 'AXP']
                elif market_cap and market_cap.lower() == 'large':
                    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'BRK-B', 'JNJ', 'V', 'WMT']
                else:
                    # Diverse mix of popular stocks
                    symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'META', 'NVDA', 'JPM', 'JNJ', 'V', 'UNH', 'HD']
            
            recommendations = []
            successful_analyses = 0
            max_attempts = min(len(symbols), count * 2)  # Analyze up to 2x requested count for better results
            
            print(f"\n📈 Analyzing Fortune 500 stocks using sentiment-enhanced ensemble forecasting...")
            print(f"🎯 Target: {count} recommendations from {max_attempts} companies")
            print("-" * 80)
            
            for symbol in symbols[:max_attempts]:
                if successful_analyses >= count:
                    break
                    
                try:
                    print(f"   🔍 Analyzing {symbol}...", end=" ")
                    
                    # Get 7-day forecast for each stock
                    forecast = self.forecaster.predict_trend(symbol, days=7)
                    
                    if forecast:
                        current_price = forecast['current_price']
                        total_change = forecast['total_change_percent']
                        confidence = forecast['confidence']
                        trend_direction = forecast['trend_direction']
                        market_regime = forecast.get('market_regime', 'UNKNOWN')
                        sentiment_data = forecast.get('sentiment_data', {})
                        
                        # Get fundamental analysis score
                        stock_info = self.data_manager.get_stock_info(symbol)
                        fundamental_score = 0
                        if stock_info:
                            fundamental_score = self.recommender.calculate_fundamental_score(stock_info)
                        
                        # Calculate combined recommendation score (ensemble + fundamental)
                        forecast_score = self._calculate_forecast_score(
                            total_change, confidence, trend_direction, sentiment_data
                        )
                        
                        # Combine forecast score (60%) with fundamental score (40%)
                        combined_score = (forecast_score * 0.6) + (fundamental_score * 0.4)
                        
                        # Get company info from Fortune 500 data
                        company_info = None
                        if fortune_500 and 'fortune_500_companies' in config_data:
                            company_info = next((c for c in config_data['fortune_500_companies'] 
                                               if c['symbol'] == symbol), None)
                        
                        recommendation = {
                            'symbol': symbol,
                            'company_name': company_info['name'] if company_info else symbol,
                            'fortune_rank': company_info['rank'] if company_info else 'N/A',
                            'sector': company_info['sector'] if company_info else 'Unknown',
                            'score': combined_score,
                            'forecast_score': forecast_score,
                            'fundamental_score': fundamental_score,
                            'confidence': confidence,
                            'price': current_price,
                            'total_change': total_change,
                            'trend_direction': trend_direction,
                            'market_regime': market_regime,
                            'sentiment_score': sentiment_data.get('sentiment_score', 0),
                            'action': self._get_forecast_action(total_change, confidence, trend_direction),
                            'stock_info': stock_info
                        }
                        
                        recommendations.append(recommendation)
                        successful_analyses += 1
                        print(f"✅ Score: {combined_score:.1f}/10")
                        
                    else:
                        print(f"❌ No forecast data")
                        
                except Exception as e:
                    print(f"❌ Error: {str(e)[:50]}...")
                    continue
            
            # Sort by recommendation score (higher is better)
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            
            # Take only the requested count for final display
            final_recommendations = recommendations[:count]
            
            print(f"\n🏆 TOP {len(final_recommendations)} FORTUNE 500 INVESTMENT RECOMMENDATIONS")
            print("=" * 80)
            
            # Display recommendations with enhanced fundamental + forecast analysis
            for i, rec in enumerate(final_recommendations, 1):
                action_info = rec['action']
                sentiment_icon = "📈" if rec['sentiment_score'] > 0 else "📉" if rec['sentiment_score'] < 0 else "➡️"
                
                # Fortune 500 company information
                company_name = rec.get('company_name', rec['symbol'])
                fortune_rank = rec.get('fortune_rank', 'N/A')
                company_sector = rec.get('sector', 'Unknown')
                
                # Get comprehensive fundamental info
                stock_info = rec.get('stock_info', {})
                pe_ratio = stock_info.get('pe_ratio', 0)
                roe = stock_info.get('roe', 0)
                debt_to_equity = stock_info.get('debt_to_equity', 0)
                current_ratio = stock_info.get('current_ratio', 0)
                profit_margin = stock_info.get('profit_margin', 0)
                revenue_growth = stock_info.get('revenue_growth', 0)
                eps_growth = stock_info.get('eps_growth', 0)
                book_value = stock_info.get('book_value', 0)
                dividend_yield = stock_info.get('dividend_yield', 0)
                peg_ratio = stock_info.get('peg_ratio', 0)
                market_cap = stock_info.get('market_cap', 0)
                
                print(f"{i:2d}. {rec['symbol']:6s} - {company_name} (#{fortune_rank}) - ${rec['price']:8.2f}")
                print(f"     🏢 Sector: {company_sector} | Fortune 500 Rank: #{fortune_rank}")
                print(f"     {action_info['icon']} **{action_info['action']}** | Combined Score: {rec['score']:.1f}/10")
                print(f"     📊 Forecast: {rec['forecast_score']:.1f}/10 | 📈 Fundamental: {rec['fundamental_score']:.1f}/10")
                print(f"     Expected: {rec['total_change']:+.1f}% over 7 days | {rec['trend_direction']}")
                print(f"     {sentiment_icon} Sentiment: {rec['sentiment_score']:+.1f} | Regime: {rec['market_regime']}")
                
                # Enhanced fundamental metrics display
                if pe_ratio and roe:
                    # Primary valuation metrics
                    peg_display = f"{peg_ratio:.2f}" if peg_ratio else "N/A"
                    pb_display = f"{(rec['price']/book_value):.2f}" if book_value else "N/A"
                    print(f"     💼 **VALUATION**: P/E: {pe_ratio:.1f} | PEG: {peg_display} | P/B: {pb_display}")
                    
                    # Profitability metrics
                    print(f"     💰 **PROFITABILITY**: ROE: {roe:.1f}% | Profit Margin: {profit_margin:.1f}% | EPS Growth: {eps_growth:+.1f}%")
                    
                    # Growth metrics
                    market_cap_display = f"${market_cap/1e9:.1f}B" if market_cap else "N/A"
                    print(f"     📈 **GROWTH**: Revenue Growth: {revenue_growth:+.1f}% | Market Cap: {market_cap_display}")
                    
                    # Financial health metrics
                    debt_health = "Strong" if debt_to_equity < 0.3 else "Moderate" if debt_to_equity < 0.6 else "High Debt"
                    liquidity_health = "Excellent" if current_ratio > 2.0 else "Good" if current_ratio > 1.5 else "Watch"
                    print(f"     🏥 **HEALTH**: D/E: {debt_to_equity:.2f} ({debt_health}) | Current Ratio: {current_ratio:.2f} ({liquidity_health})")
                    
                    # Income metrics
                    if dividend_yield > 0:
                        print(f"     💵 **INCOME**: Dividend Yield: {dividend_yield:.2f}% | Payout Sustainable")
                    else:
                        print(f"     � **INCOME**: No Dividend | Growth-Focused Company")
                        
                    # Value assessment
                    value_assessment = self._assess_value_metrics(pe_ratio, peg_ratio, roe, profit_margin, debt_to_equity)
                    print(f"     🎯 **VALUE ASSESSMENT**: {value_assessment}")
                else:
                    print(f"     💼 **FUNDAMENTAL**: Limited data available - forecast-weighted recommendation")
                    if market_cap:
                        print(f"     📊 **BASIC**: Market Cap: ${market_cap/1e9:.1f}B | Size-based analysis")
                    
                print(f"     💡 {action_info['strategy']}")
                print("-" * 80)
            
            # Display Fortune 500 portfolio recommendations
            self._display_fortune500_portfolio_recommendations(final_recommendations)
            
        except Exception as e:
            print(f"❌ Error getting forecast-based recommendations: {e}")
    
    def _calculate_forecast_score(self, total_change: float, confidence: float, 
                                trend_direction: str, sentiment_data: dict) -> float:
        """Calculate recommendation score based on forecast data"""
        
        # Base score from expected return and confidence
        base_score = 5.0  # Neutral
        
        # Price change component (50% weight)
        if trend_direction == "BULLISH":
            change_score = min(total_change * 0.5, 3.0)  # Cap at +3 points
        elif trend_direction == "BEARISH":
            change_score = max(total_change * 0.5, -3.0)  # Cap at -3 points  
        else:
            change_score = 0
        
        # Confidence component (30% weight)
        confidence_score = (confidence - 50) * 0.06  # Scale to ±3 points
        
        # Sentiment component (20% weight)
        sentiment_score = sentiment_data.get('sentiment_score', 0) * 0.2  # Scale to ±2 points
        
        total_score = base_score + change_score + confidence_score + sentiment_score
        return max(0, min(10, total_score))  # Cap between 0-10
    
    def _get_forecast_action(self, total_change: float, confidence: float, 
                           trend_direction: str) -> dict:
        """Get action recommendation based on forecast"""
        
        if trend_direction == "BULLISH" and total_change > 3 and confidence > 70:
            return {
                'action': 'STRONG BUY',
                'icon': '🟢',
                'strategy': f'High conviction play - target {total_change:+.1f}% gain'
            }
        elif trend_direction == "BULLISH" and total_change > 1 and confidence > 55:
            return {
                'action': 'BUY',
                'icon': '🟢', 
                'strategy': f'Good opportunity - expect {total_change:+.1f}% upside'
            }
        elif trend_direction == "BEARISH" and total_change < -3 and confidence > 60:
            return {
                'action': 'SELL',
                'icon': '🔴',
                'strategy': f'Avoid or short - expect {total_change:.1f}% decline'
            }
        elif trend_direction == "BEARISH" and total_change < -1 and confidence > 50:
            return {
                'action': 'HOLD (Cautious)',
                'icon': '🟡',
                'strategy': f'Monitor closely - potential {total_change:.1f}% decline'
            }
        else:
            return {
                'action': 'HOLD',
                'icon': '⏸️',
                'strategy': f'Sideways expected - wait for better signals'
            }
    
    def _assess_value_metrics(self, pe_ratio: float, peg_ratio: float, roe: float, 
                             profit_margin: float, debt_to_equity: float) -> str:
        """
        Assess overall value proposition based on fundamental metrics
        
        Args:
            pe_ratio: Price-to-earnings ratio
            peg_ratio: Price/earnings to growth ratio
            roe: Return on equity percentage
            profit_margin: Net profit margin percentage
            debt_to_equity: Debt-to-equity ratio
            
        Returns:
            String assessment of value proposition
        """
        score = 0
        assessments = []
        
        # P/E assessment
        if pe_ratio < 15:
            score += 2
            assessments.append("Undervalued P/E")
        elif pe_ratio < 25:
            score += 1
            assessments.append("Fair P/E")
        else:
            assessments.append("High P/E")
            
        # PEG assessment
        if peg_ratio and peg_ratio < 1.0:
            score += 2
            assessments.append("Attractive PEG")
        elif peg_ratio and peg_ratio < 1.5:
            score += 1
            assessments.append("Reasonable PEG")
        elif peg_ratio:
            assessments.append("Expensive PEG")
            
        # Profitability assessment
        if roe > 20:
            score += 2
            assessments.append("Excellent ROE")
        elif roe > 15:
            score += 1
            assessments.append("Good ROE")
        else:
            assessments.append("Weak ROE")
            
        # Margin assessment
        if profit_margin > 20:
            score += 2
            assessments.append("High Margins")
        elif profit_margin > 10:
            score += 1
            assessments.append("Decent Margins")
        else:
            assessments.append("Thin Margins")
            
        # Debt assessment
        if debt_to_equity < 0.3:
            score += 1
            assessments.append("Low Debt")
        elif debt_to_equity > 0.8:
            score -= 1
            assessments.append("High Debt Risk")
            
        # Overall assessment
        if score >= 6:
            return f"🔥 **EXCELLENT VALUE** - {', '.join(assessments[:3])}"
        elif score >= 4:
            return f"✅ **GOOD VALUE** - {', '.join(assessments[:3])}"
        elif score >= 2:
            return f"⚖️ **FAIR VALUE** - {', '.join(assessments[:2])}"
        else:
            return f"⚠️ **OVERVALUED** - {', '.join(assessments[:2])}"
    
    def _display_fortune500_portfolio_recommendations(self, recommendations: list) -> None:
        """Display Fortune 500 portfolio recommendations based on forecasts"""
        
        print("\n" + "=" * 80)
        print("💼 FORTUNE 500 ENHANCED PORTFOLIO STRATEGY")
        print("=" * 80)
        
        # Categorize by Fortune 500 ranking and forecast action
        top_10_fortune = [r for r in recommendations if r.get('fortune_rank', 'N/A') != 'N/A' and int(r['fortune_rank']) <= 10]
        top_50_fortune = [r for r in recommendations if r.get('fortune_rank', 'N/A') != 'N/A' and 11 <= int(r['fortune_rank']) <= 50]
        top_100_fortune = [r for r in recommendations if r.get('fortune_rank', 'N/A') != 'N/A' and 51 <= int(r['fortune_rank']) <= 100]
        
        strong_buys = [r for r in recommendations if 'STRONG BUY' in r['action']['action']]
        buys = [r for r in recommendations if r['action']['action'] == 'BUY']
        holds = [r for r in recommendations if 'HOLD' in r['action']['action']]
        sells = [r for r in recommendations if 'SELL' in r['action']['action']]
        
        print(f"\n🏆 **Fortune 500 Rankings Analysis:**")
        if top_10_fortune:
            companies = [f"{s['symbol']}(#{s['fortune_rank']},Score:{s['score']:.1f})" for s in top_10_fortune]
            print(f"   🥇 TOP 10 FORTUNE ({len(top_10_fortune)}): {', '.join(companies)}")
            print(f"      → Blue-chip investments with highest market stability")
            
        if top_50_fortune:
            companies = [f"{s['symbol']}(#{s['fortune_rank']},Score:{s['score']:.1f})" for s in top_50_fortune]
            print(f"   🥈 TOP 50 FORTUNE ({len(top_50_fortune)}): {', '.join(companies)}")
            print(f"      → Large-cap leaders with strong market positions")
            
        if top_100_fortune:
            companies = [f"{s['symbol']}(#{s['fortune_rank']},Score:{s['score']:.1f})" for s in top_100_fortune]
            print(f"   🥉 TOP 100 FORTUNE ({len(top_100_fortune)}): {', '.join(companies)}")
            print(f"      → Established companies with growth potential")
        
        print(f"\n🎯 **Fortune 500 Sector Diversification:**")
        sector_breakdown = {}
        for rec in recommendations:
            sector = rec.get('sector', 'Unknown')
            if sector not in sector_breakdown:
                sector_breakdown[sector] = []
            sector_breakdown[sector].append(rec)
        
        for sector, stocks in sector_breakdown.items():
            avg_score = sum(s['score'] for s in stocks) / len(stocks)
            symbols = [f"{s['symbol']}({s['score']:.1f})" for s in stocks]
            print(f"   🏭 {sector.upper()} ({len(stocks)}): {', '.join(symbols)} - Avg Score: {avg_score:.1f}")
        
        print(f"\n🎯 **Forecast-Based Action Summary:**")
        if strong_buys:
            symbols = [f"{s['symbol']}({s['total_change']:+.1f}%,#{s.get('fortune_rank','?')})" for s in strong_buys]
            print(f"   🟢 STRONG BUY ({len(strong_buys)}): {', '.join(symbols)}")
            print(f"      → High conviction Fortune 500 investments")
            
        if buys:
            symbols = [f"{s['symbol']}({s['total_change']:+.1f}%,#{s.get('fortune_rank','?')})" for s in buys]
            print(f"   🟢 BUY ({len(buys)}): {', '.join(symbols)}")
            print(f"      → Good opportunities in established companies")
            
        if sells:
            symbols = [f"{s['symbol']}({s['total_change']:.1f}%,#{s.get('fortune_rank','?')})" for s in sells]
            print(f"   🔴 SELL/AVOID ({len(sells)}): {', '.join(symbols)}")
            print(f"      → Even Fortune 500 companies can have downturns")
        
        # Enhanced Fortune 500 specific recommendations
        print(f"\n💼 **Fortune 500 Portfolio Construction:**")
        
        # Core holdings (Fortune 1-50, high fundamental scores)
        core_candidates = [r for r in recommendations 
                          if r.get('fortune_rank', 'N/A') != 'N/A' 
                          and int(r['fortune_rank']) <= 50 
                          and r['fundamental_score'] >= 6.0]
        if core_candidates:
            symbols = [f"{s['symbol']}(#{s['fortune_rank']},F:{s['fundamental_score']:.1f})" for s in core_candidates]
            print(f"   🏛️  CORE HOLDINGS (40-50%): {', '.join(symbols)}")
            print(f"      → Top 50 Fortune companies with strong fundamentals")
        
        # Growth plays (high forecast scores)
        growth_candidates = [r for r in recommendations 
                           if r['forecast_score'] >= 7.5 and r['total_change'] > 3]
        if growth_candidates:
            symbols = [f"{s['symbol']}({s['total_change']:+.1f}%,#{s.get('fortune_rank','?')})" for s in growth_candidates]
            print(f"   🚀 GROWTH PLAYS (30-40%): {', '.join(symbols)}")
            print(f"      → Fortune 500 companies with strong momentum")
        
        # Dividend income (Fortune companies with yield >2%)
        dividend_candidates = []
        for r in recommendations:
            stock_info = r.get('stock_info', {})
            dividend_yield = stock_info.get('dividend_yield', 0)
            if dividend_yield > 0.02:  # >2%
                dividend_candidates.append((r, dividend_yield))
        
        if dividend_candidates:
            symbols = [f"{s[0]['symbol']}({s[1]*100:.1f}%,#{s[0].get('fortune_rank','?')})" 
                      for s in dividend_candidates]
            print(f"   💵 INCOME FOCUS (10-20%): {', '.join(symbols)}")
            print(f"      → Fortune 500 dividend aristocrats")
        
        # Risk warnings specific to Fortune 500
        print(f"\n⚠️  **Fortune 500 Risk Considerations:**")
        
        # High debt Fortune companies
        high_debt_companies = []
        for r in recommendations:
            stock_info = r.get('stock_info', {})
            debt_to_equity = stock_info.get('debt_to_equity', 0)
            if debt_to_equity > 0.6:
                high_debt_companies.append(f"{r['symbol']}(#{r.get('fortune_rank','?')},D/E:{debt_to_equity:.2f})")
        
        if high_debt_companies:
            print(f"   📊 HIGH DEBT WATCH: {', '.join(high_debt_companies)}")
            print(f"      → Even Fortune 500 status doesn't eliminate debt risk")
        
        # Market concentration risk
        tech_heavy = len([r for r in recommendations if r.get('sector', '') == 'Technology'])
        if tech_heavy >= len(recommendations) * 0.4:
            print(f"   🔧 TECH CONCENTRATION RISK: {tech_heavy}/{len(recommendations)} recommendations")
            print(f"      → Consider broader Fortune 500 sector diversification")
        
        print(f"   ✅ FORTUNE 500 ADVANTAGE: Established companies with proven business models")
        print(f"   ✅ LIQUIDITY BENEFIT: High trading volumes and market depth")
        print(f"   ✅ TRANSPARENCY: Regular SEC filings and analyst coverage")

    def _display_forecast_portfolio_recommendations(self, recommendations: list) -> None:
        """Display portfolio recommendations based on forecasts"""
        
        print("\n" + "=" * 80)
        print("💼 ENHANCED PORTFOLIO STRATEGY (Forecast + Fundamental)")
        print("=" * 80)
        
        # Categorize by forecast action
        strong_buys = [r for r in recommendations if 'STRONG BUY' in r['action']['action']]
        buys = [r for r in recommendations if r['action']['action'] == 'BUY']
        holds = [r for r in recommendations if 'HOLD' in r['action']['action']]
        sells = [r for r in recommendations if 'SELL' in r['action']['action']]
        
        print(f"\n🎯 **Forecast-Based Action Summary:**")
        if strong_buys:
            symbols = [f"{s['symbol']}({s['total_change']:+.1f}%)" for s in strong_buys]
            print(f"   🟢 STRONG BUY ({len(strong_buys)}): {', '.join(symbols)}")
            print(f"      → High conviction investments based on ensemble forecasting")
            
        if buys:
            symbols = [f"{s['symbol']}({s['total_change']:+.1f}%)" for s in buys]
            print(f"   � BUY ({len(buys)}): {', '.join(symbols)}")
            print(f"      → Good opportunities with positive sentiment-enhanced forecasts")
            
        if sells:
            symbols = [f"{s['symbol']}({s['total_change']:.1f}%,F:{s['fundamental_score']:.1f})" for s in sells]
            print(f"   🔴 SELL/AVOID ({len(sells)}): {', '.join(symbols)}")
            print(f"      → Negative forecast overrides fundamental strength")
        
        # Enhanced fundamental analysis summary
        print(f"\n💼 **Fundamental Analysis Summary:**")
        
        # Value stocks (good fundamentals)
        value_stocks = [r for r in recommendations if r['fundamental_score'] >= 7.0]
        if value_stocks:
            symbols = [f"{s['symbol']}(F:{s['fundamental_score']:.1f})" for s in value_stocks]
            print(f"   💎 HIGH QUALITY ({len(value_stocks)}): {', '.join(symbols)}")
            print(f"      → Strong fundamentals: ROE >15%, reasonable P/E, healthy balance sheets")
        
        # Growth stocks (high forecast potential)
        growth_stocks = [r for r in recommendations if r['forecast_score'] >= 8.0 and r['total_change'] > 4]
        if growth_stocks:
            symbols = [f"{s['symbol']}({s['total_change']:+.1f}%)" for s in growth_stocks]
            print(f"   🚀 MOMENTUM PLAYS ({len(growth_stocks)}): {', '.join(symbols)}")
            print(f"      → High forecast scores with strong expected returns")
        
        # Balanced picks (good both fundamental and forecast)
        balanced_stocks = [r for r in recommendations if r['fundamental_score'] >= 6.0 and r['forecast_score'] >= 7.0]
        if balanced_stocks:
            symbols = [f"{s['symbol']}(C:{s['score']:.1f})" for s in balanced_stocks]
            print(f"   ⚖️ BALANCED VALUE ({len(balanced_stocks)}): {', '.join(symbols)}")
            print(f"      → Best of both: solid fundamentals + positive technical outlook")
        
        # Risk considerations
        high_debt_stocks = []
        for r in recommendations:
            stock_info = r.get('stock_info', {})
            debt_to_equity = stock_info.get('debt_to_equity', 0)
            if debt_to_equity > 0.6:
                high_debt_stocks.append(f"{r['symbol']}({debt_to_equity:.2f})")
        
        if high_debt_stocks:
            print(f"   ⚠️ HIGH DEBT WATCH ({len(high_debt_stocks)}): {', '.join(high_debt_stocks)}")
            print(f"      → Monitor debt levels - potential financial stress in downturns")
        
        # Dividend income opportunities
        dividend_stocks = []
        for r in recommendations:
            stock_info = r.get('stock_info', {})
            dividend_yield = stock_info.get('dividend_yield', 0)
            if dividend_yield > 2.0:
                dividend_stocks.append(f"{r['symbol']}({dividend_yield:.1f}%)")
        
        if dividend_stocks:
            print(f"   💵 INCOME FOCUS ({len(dividend_stocks)}): {', '.join(dividend_stocks)}")
            print(f"      → Dividend yields >2% - potential income generation")

                

    
    def forecast_stock(self, symbol: str, days: int = 7) -> None:
        """
        Forecast stock price trend for the next N days with recommendation actions
        
        Args:
            symbol: Stock symbol to forecast (e.g., 'AAPL')
            days: Number of days to forecast (default: 7)
        """
        print(f"🔮 StockTrader - {days}-Day Forecast for {symbol.upper()}")
        print("=" * 50)
        
        try:
            forecast = self.forecaster.predict_trend(symbol, days)
            
            if not forecast:
                print(f"❌ Unable to generate ensemble forecast for {symbol}")
                return
            
            current_price = forecast['current_price']
            predicted_prices = forecast['predictions']
            trend_direction = forecast['trend_direction']
            confidence = forecast['confidence']
            market_regime = forecast.get('market_regime', 'UNKNOWN')
            model_weights = forecast.get('model_weights', {})
            
            print(f"\n📊 Current Price: ${current_price:.2f}")
            print(f"🎯 Trend Direction: {trend_direction}")
            print(f"📈 Confidence Level: {confidence:.1f}%")
            print(f"🏛️  Market Regime: {market_regime}")
            
            # NEW: Display sentiment analysis if available
            sentiment_data = forecast.get('sentiment_data', {})
            if sentiment_data:
                sentiment_score = sentiment_data.get('sentiment_score', 0)
                sentiment_strength = sentiment_data.get('sentiment_strength', 0)
                article_count = sentiment_data.get('article_count', 0)
                
                print(f"\n📰 Sentiment Analysis:")
                sentiment_icon = "📈" if sentiment_score > 0 else "📉" if sentiment_score < 0 else "➡️"
                print(f"     {sentiment_icon} Sentiment Score: {sentiment_score:+.1f}/10")
                print(f"     💪 Sentiment Strength: {sentiment_strength:.1f}")
                print(f"     📄 News Articles: {article_count}")
                print(f"     ✅ Positive: {sentiment_data.get('positive_articles', 0)} | "
                      f"❌ Negative: {sentiment_data.get('negative_articles', 0)}")
                
                # Show sample headlines
                headlines = sentiment_data.get('headlines_sample', [])
                if headlines:
                    print(f"     🗞️  Recent Headlines:")
                    for i, headline in enumerate(headlines, 1):
                        print(f"        {i}. {headline[:60]}...")
            
            print(f"\n🤖 Ensemble Model Weights:")
            for model, weight in model_weights.items():
                print(f"     • {model.replace('_', ' ').title()}: {weight:.1%}")
            
            print(f"\n📅 {days}-Day Ensemble Forecast (Trading Days Only):")
            print("-" * 50)
            
            for day, price_data in enumerate(predicted_prices, 1):
                date = price_data['date']
                predicted_price = price_data['price']
                change_pct = ((predicted_price - current_price) / current_price) * 100
                change_indicator = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➡️"
                
                print(f"Day {day} ({date}): ${predicted_price:6.2f} {change_indicator} {change_pct:+5.1f}%")
            
            # Summary
            final_price = predicted_prices[-1]['price']
            total_change = ((final_price - current_price) / current_price) * 100
            
            print("-" * 50)
            print(f"📋 Sentiment-Enhanced Ensemble Summary: {total_change:+.1f}% expected change over {days} days")
            print(f"🎯 Target Price: ${final_price:.2f}")
            
            # Enhanced fundamental analysis for individual stock
            try:
                stock_info = self.data_manager.get_stock_info(symbol)
                if stock_info:
                    print(f"\n💼 **FUNDAMENTAL ANALYSIS FOR {symbol}:**")
                    print("-" * 50)
                    
                    # Valuation metrics
                    pe_ratio = stock_info.get('pe_ratio', 0)
                    peg_ratio = stock_info.get('peg_ratio', 0)
                    book_value = stock_info.get('book_value', 0)
                    if pe_ratio:
                        pb_ratio = current_price / book_value if book_value else 0
                        peg_display = f"{peg_ratio:.2f}" if peg_ratio else "N/A"
                        pb_display = f"{pb_ratio:.2f}" if pb_ratio else "N/A"
                        print(f"📊 **VALUATION**: P/E: {pe_ratio:.1f} | PEG: {peg_display} | P/B: {pb_display}")
                    
                    # Profitability metrics
                    roe = stock_info.get('roe', 0)
                    profit_margin = stock_info.get('profit_margin', 0)
                    roa = stock_info.get('roa', 0)
                    if roe:
                        print(f"💰 **PROFITABILITY**: ROE: {roe:.1f}% | ROA: {roa:.1f}% | Net Margin: {profit_margin:.1f}%")
                    
                    # Growth metrics
                    revenue_growth = stock_info.get('revenue_growth', 0)
                    eps_growth = stock_info.get('eps_growth', 0)
                    earnings_growth = stock_info.get('earnings_growth', 0)
                    if revenue_growth or eps_growth:
                        print(f"📈 **GROWTH**: Revenue: {revenue_growth:+.1f}% | EPS: {eps_growth:+.1f}% | Earnings: {earnings_growth:+.1f}%")
                    
                    # Financial health
                    debt_to_equity = stock_info.get('debt_to_equity', 0)
                    current_ratio = stock_info.get('current_ratio', 0)
                    free_cash_flow = stock_info.get('free_cash_flow', 0)
                    if debt_to_equity or current_ratio:
                        cash_flow_text = f" | FCF: ${free_cash_flow/1e9:.1f}B" if free_cash_flow else ""
                        print(f"🏥 **FINANCIAL HEALTH**: D/E: {debt_to_equity:.2f} | Current Ratio: {current_ratio:.2f}{cash_flow_text}")
                    
                    # Market metrics
                    market_cap = stock_info.get('market_cap', 0)
                    volume = stock_info.get('volume', 0)
                    beta = stock_info.get('beta', 0)
                    if market_cap:
                        cap_size = "Large" if market_cap > 10e9 else "Mid" if market_cap > 2e9 else "Small"
                        beta_display = f"{beta:.2f}" if beta else "N/A"
                        volume_display = f"{volume/1e6:.1f}M" if volume else "N/A"
                        print(f"🏛️ **MARKET**: Cap: ${market_cap/1e9:.1f}B ({cap_size}) | Beta: {beta_display} | Volume: {volume_display}")
                    
                    # Income metrics
                    dividend_yield = stock_info.get('dividend_yield', 0)
                    payout_ratio = stock_info.get('payout_ratio', 0)
                    if dividend_yield > 0:
                        print(f"💵 **INCOME**: Dividend Yield: {dividend_yield:.2f}% | Payout Ratio: {payout_ratio:.1f}%")
                    else:
                        print(f"💵 **INCOME**: No Dividend | Growth-Focused Strategy")
                    
                    # Calculate fundamental score
                    fundamental_score = self.recommender.calculate_fundamental_score(stock_info)
                    value_assessment = self._assess_value_metrics(pe_ratio, peg_ratio, roe, profit_margin, debt_to_equity)
                    print(f"🎯 **OVERALL ASSESSMENT**: Fundamental Score: {fundamental_score:.1f}/10")
                    print(f"    {value_assessment}")
                    
            except Exception as e:
                print(f"⚠️ Fundamental analysis unavailable: {e}")
            
            # Enhanced analysis indicators
            sentiment_data = forecast.get('sentiment_data', {})
            if sentiment_data and abs(sentiment_data.get('sentiment_score', 0)) > 1:
                sentiment_impact = "📈 Positive" if sentiment_data.get('sentiment_score', 0) > 0 else "📉 Negative"
                print(f"📰 Sentiment Impact: {sentiment_impact} news sentiment factored into prediction")
            
            if abs(total_change) > 5:
                print(f"⚠️  High volatility expected ({abs(total_change):.1f}% change)")
            
            if confidence >= 80:
                print(f"✅ High confidence prediction ({confidence:.0f}%)")
            elif confidence <= 50:
                print(f"⚠️  Lower confidence - multiple scenarios possible ({confidence:.0f}%)")
            
            # Generate enhanced recommendation action
            self._generate_enhanced_recommendation_action(
                symbol, current_price, total_change, trend_direction, confidence, market_regime, forecast
            )
            
        except Exception as e:
            print(f"❌ Error generating forecast: {e}")
    
    def _generate_enhanced_recommendation_action(self, symbol: str, current_price: float, 
                                              total_change: float, trend_direction: str, 
                                              confidence: float, market_regime: str, 
                                              forecast_data: Optional[dict] = None) -> None:
        """
        Generate enhanced buy/sell/hold recommendations based on ensemble forecast
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            total_change: Expected percentage change
            trend_direction: BULLISH/BEARISH/NEUTRAL
            confidence: Confidence level (0-100)
            market_regime: BULL/BEAR/VOLATILE/NEUTRAL
        """
        print("\n" + "=" * 60)
        print("🎯 ENHANCED INVESTMENT RECOMMENDATION")
        print("=" * 60)
        
        # Enhanced action determination with confidence and regime factors
        action = "HOLD"
        action_icon = "⏸️"
        risk_level = "MEDIUM"
        position_size = "Small"
        
        # Adjust thresholds based on confidence and market regime
        confidence_factor = confidence / 100.0
        
        # Market regime adjustments
        regime_bullish_boost = 0
        regime_risk_adjustment = 0
        
        if market_regime == 'BULL':
            regime_bullish_boost = 1.0  # Lower threshold for buying
            regime_risk_adjustment = -0.5  # Reduce risk perception
        elif market_regime == 'BEAR':
            regime_bullish_boost = -1.0  # Higher threshold for buying
            regime_risk_adjustment = 1.0  # Increase risk perception
        elif market_regime == 'VOLATILE':
            regime_risk_adjustment = 0.5  # Moderate risk increase
        
        # Dynamic thresholds
        strong_buy_threshold = (4 - regime_bullish_boost) * confidence_factor
        buy_threshold = (2 - regime_bullish_boost) * confidence_factor
        sell_threshold = (-3 - regime_bullish_boost) * confidence_factor
        
        if (trend_direction == "BULLISH" and total_change > strong_buy_threshold and 
            confidence > 70):
            action = "STRONG BUY"
            action_icon = "🟢"
            risk_level = "LOW" if confidence > 85 else "MEDIUM"
            position_size = "Large" if confidence > 80 else "Medium"
            
        elif (trend_direction == "BULLISH" and total_change > buy_threshold and 
              confidence > 55):
            action = "BUY"
            action_icon = "🟢"
            risk_level = "MEDIUM"
            position_size = "Medium" if confidence > 70 else "Small"
            
        elif (trend_direction == "BEARISH" and total_change < sell_threshold and 
              confidence > 60):
            action = "SELL"
            action_icon = "🔴"
            risk_level = "HIGH"
            position_size = "Reduce Holdings"
            
        elif (trend_direction == "BEARISH" and total_change < -1 and confidence > 50):
            action = "HOLD (Cautious)"
            action_icon = "🟡"
            risk_level = "MEDIUM-HIGH"
            position_size = "Avoid New Positions"
        
        # Apply regime-based risk adjustment
        if regime_risk_adjustment > 0 and risk_level == "LOW":
            risk_level = "MEDIUM"
        elif regime_risk_adjustment > 0.5 and risk_level == "MEDIUM":
            risk_level = "MEDIUM-HIGH"
        elif regime_risk_adjustment < 0 and risk_level == "MEDIUM":
            risk_level = "LOW"
        
        # Display enhanced recommendation
        print(f"\n{action_icon} **{action}** {symbol}")
        print(f"📊 Target Price Range: ${current_price * (1 + total_change/100):.2f}")
        print(f"⚡ Risk Level: {risk_level}")
        print(f"📦 Position Size: {position_size}")
        print(f"🏛️  Market Context: {market_regime} regime")
        print(f"🎯 Confidence: {confidence:.0f}%")
        
        # Enhanced action steps with regime context
        print(f"\n📋 **Enhanced Action Steps:**")
        
        if "BUY" in action:
            print(f"   1. 💰 Consider buying {symbol} at current price ${current_price:.2f}")
            print(f"   2. 🎯 Set target price: ${current_price * (1 + total_change/100):.2f} ({total_change:+.1f}%)")
            
            # Dynamic stop-loss based on regime and confidence
            if market_regime == 'VOLATILE':
                stop_loss = 0.93  # Wider stop-loss in volatile markets
            elif confidence > 80:
                stop_loss = 0.96  # Tighter stop-loss with high confidence
            else:
                stop_loss = 0.95  # Standard stop-loss
                
            print(f"   3. 🛑 Set stop-loss: ${current_price * stop_loss:.2f} ({(stop_loss-1)*100:+.0f}%)")
            print(f"   4. ⏰ Time horizon: {7} trading days")
            print(f"   5. 🏛️  Market regime consideration: {market_regime}")
            
            if confidence < 70:
                print(f"   6. ⚠️  Start with small position due to moderate confidence")
            if market_regime == 'BEAR':
                print(f"   7. 🐻 Bear market: Consider DCA over longer period")
                
        elif "SELL" in action:
            print(f"   1. 📉 Consider selling {symbol} at current price ${current_price:.2f}")
            print(f"   2. 💸 Expected decline to: ${current_price * (1 + total_change/100):.2f}")
            print(f"   3. 🔄 Consider re-entry if price drops below ${current_price * 0.85:.2f}")
            print(f"   4. ⏰ Review position in {7} trading days")
            print(f"   5. 🏛️  {market_regime} regime supports bearish outlook")
            
        else:  # HOLD
            print(f"   1. ⏸️  Hold current {symbol} positions")
            print(f"   2. 👀 Monitor for trend changes and regime shifts")
            print(f"   3. 📊 Expected range: ${current_price * 0.97:.2f} - ${current_price * 1.03:.2f}")
            print(f"   4. 🔄 Reassess when market regime changes from {market_regime}")
        
        # Enhanced risk warnings with regime context
        print(f"\n⚠️  **Enhanced Risk Considerations:**")
        if confidence < 60:
            print(f"   • Low confidence forecast ({confidence:.0f}%) - use smaller position sizes")
        if abs(total_change) > 5:
            print(f"   • High volatility expected ({abs(total_change):.1f}%) - consider tighter stop-losses")
        if market_regime == 'BEAR':
            print(f"   • Bear market regime - expect higher volatility and potential false breakouts")
        elif market_regime == 'VOLATILE':
            print(f"   • Volatile market regime - consider scaling into positions")
        
        # NEW: Sentiment-based risk warnings
        sentiment_data = forecast_data.get('sentiment_data', {}) if forecast_data else {}
        if sentiment_data:
            sentiment_score = sentiment_data.get('sentiment_score', 0)
            article_count = sentiment_data.get('article_count', 0)
            
            if abs(sentiment_score) > 3 and article_count < 3:
                print(f"   • Strong sentiment with limited news coverage - verify with additional sources")
            elif sentiment_score > 0 and trend_direction == "BEARISH":
                print(f"   • Positive sentiment conflicts with bearish technical trend - mixed signals")
            elif sentiment_score < 0 and trend_direction == "BULLISH":
                print(f"   • Negative sentiment conflicts with bullish technical trend - mixed signals")
        
        print(f"   • Multiple model ensemble used - better than single model predictions")
        print(f"   • Market regime analysis included - {market_regime} context applied")
        print(f"   • Sentiment-enhanced forecasting - news impact integrated")
        """
        Generate specific buy/sell/hold recommendations based on forecast
        
        Args:
            symbol: Stock symbol
            current_price: Current stock price
            total_change: Expected percentage change
            trend_direction: BULLISH/BEARISH/NEUTRAL
            confidence: Confidence level (0-100)
        """
        print("\n" + "=" * 50)
        print("🎯 INVESTMENT RECOMMENDATION")
        print("=" * 50)
        
        # Determine action based on forecast
        action = "HOLD"
        action_icon = "⏸️"
        risk_level = "MEDIUM"
        position_size = "Small"
        
        if trend_direction == "BULLISH" and total_change > 3 and confidence > 60:
            action = "BUY"
            action_icon = "🟢"
            risk_level = "LOW" if confidence > 75 else "MEDIUM"
            position_size = "Large" if confidence > 80 else "Medium"
            
        elif trend_direction == "BULLISH" and total_change > 1 and confidence > 50:
            action = "BUY (Small Position)"
            action_icon = "🟢"
            risk_level = "MEDIUM"
            position_size = "Small"
            
        elif trend_direction == "BEARISH" and total_change < -3 and confidence > 60:
            action = "SELL"
            action_icon = "🔴"
            risk_level = "HIGH"
            position_size = "Reduce Holdings"
            
        elif trend_direction == "BEARISH" and total_change < -1 and confidence > 50:
            action = "HOLD (Cautious)"
            action_icon = "🟡"
            risk_level = "MEDIUM-HIGH"
            position_size = "Avoid New Positions"
        
        # Display recommendation
        print(f"\n{action_icon} **{action}** {symbol}")
        print(f"📊 Target Price Range: ${current_price * (1 + total_change/100):.2f}")
        print(f"⚡ Risk Level: {risk_level}")
        print(f"📦 Position Size: {position_size}")
        
        # Specific action steps
        print(f"\n📋 **Action Steps:**")
        
        if "BUY" in action:
            print(f"   1. 💰 Consider buying {symbol} at current price ${current_price:.2f}")
            print(f"   2. 🎯 Set target price: ${current_price * (1 + total_change/100):.2f} ({total_change:+.1f}%)")
            print(f"   3. 🛑 Set stop-loss: ${current_price * 0.95:.2f} (-5%)")
            print(f"   4. ⏰ Time horizon: {7} trading days")
            if confidence < 70:
                print(f"   5. ⚠️  Start with small position due to moderate confidence")
                
        elif "SELL" in action:
            print(f"   1. 📉 Consider selling {symbol} at current price ${current_price:.2f}")
            print(f"   2. 💸 Expected decline to: ${current_price * (1 + total_change/100):.2f}")
            print(f"   3. 🔄 Consider re-entry if price drops below ${current_price * 0.90:.2f}")
            print(f"   4. ⏰ Review position in {7} trading days")
            
        else:  # HOLD
            print(f"   1. ⏸️  Hold current {symbol} positions")
            print(f"   2. 👀 Monitor for trend changes")
            print(f"   3. 📊 Expected range: ${current_price * 0.97:.2f} - ${current_price * 1.03:.2f}")
            print(f"   4. 🔄 Reassess in {7} trading days")
        
        # Risk warnings
        print(f"\n⚠️  **Risk Considerations:**")
        if confidence < 60:
            print(f"   • Low confidence forecast - use smaller position sizes")
        if abs(total_change) > 5:
            print(f"   • High volatility expected - consider tighter stop-losses")
        if trend_direction == "BEARISH":
            print(f"   • Bearish trend - avoid catching falling knife")


def main():
    """Main entry point for StockTrader console application"""
    print("🚀 StockTrader - Fortune 500 Sentiment-Enhanced Ensemble Forecasting")
    print("=" * 70)
    
    # Initialize StockTrader
    app = StockTrader()
    
    try:
        # Example 1: Get Fortune 500 forecast-based stock recommendations
        print("\n📊 Getting Fortune 500 Investment Recommendations...")
        app.recommend_stocks(count=8, fortune_500=True)
        
        print("\n" + "=" * 70)
        
        # Example 2: Get detailed stock forecast for top Fortune 500 company
        print("\n🔮 Getting Detailed Forecast for Walmart (Fortune #1)...")
        app.forecast_stock('WMT', days=7)
        
    except KeyboardInterrupt:
        print("\n\n🛑 Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Direct method calls - modify these as needed
    app = StockTrader()
    
    # Example usage - Fortune 500 Analysis:
    
    # Get top 10 Fortune 500 investment recommendations
    print("🏆 Analyzing Top Fortune 500 Companies...")
    #app.recommend_stocks(count=10, fortune_500=True)
    
    print("\n" + "=" * 60)
    
    # Sector-specific Fortune 500 analysis
    #print("\n💻 Analyzing Fortune 500 Technology Sector...")
    #app.recommend_stocks(sector='Technology', count=5, fortune_500=True)
    
    print("\n" + "=" * 60)
    
    # Healthcare Fortune 500 analysis
    #print("\n🏥 Analyzing Fortune 500 Healthcare Sector...")
    #app.recommend_stocks(sector='Healthcare', count=5, fortune_500=True)
    
    # Additional examples you can uncomment:
    
    # Test sentiment-enhanced forecasting on a specific Fortune 500 company
    #print("\n🔮 Testing Fortune 500 Stock Forecast...")
    app.forecast_stock('NFLX', days=14)  # Walmart - #1 Fortune 500
    
    # Get Financial sector Fortune 500 recommendations
    # app.recommend_stocks(sector='Financial', count=5, fortune_500=True)
    
    # Get top 20 Fortune 500 companies for analysis
    #app.recommend_stocks(count=10, fortune_500=True)
    
    # Forecast specific Fortune 500 companies
    #app.forecast_stock('F', days=14)  # Pfizer - #60 Fortune 500
    
    #app.forecast_stock('NVO', days=14)  # Amazon - #2 Fortune 500
    
    # You can also call main() for the combined demo
    # main()
