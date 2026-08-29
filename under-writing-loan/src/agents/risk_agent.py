"""
Risk Agent - Financial risk assessment for loan underwriting.

Calculates financial metrics (DTI, LTV, PTI) and performs AI-powered
risk analysis using credit data from MCP server.

Components:
- FinancialCalculator: DTI, LTV, PTI calculations
- RiskAnalyzer: GPT-4o risk assessment with reasoning
- RiskVisualizer: Plotly charts for metrics
"""

import logging
import os
import json
from decimal import Decimal
from typing import Dict, Optional, List, Tuple, Union
from datetime import datetime
from openai import AzureOpenAI
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# Load models
import sys
from pathlib import Path
src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from models import RiskAssessment, CreditReport

logger = logging.getLogger(__name__)


class FinancialCalculator:
    """
    Calculate key financial ratios for loan risk assessment.
    
    Implements industry-standard formulas for:
    - DTI (Debt-to-Income): Total monthly debt / monthly income
    - LTV (Loan-to-Value): Loan amount / property value
    - PTI (Payment-to-Income): Monthly payment / monthly income
    
    All ratios returned as percentages (0-100).
    """
    
    def __init__(self):
        """Initialize financial calculator."""
        logger.info("FinancialCalculator initialized")
    
    def calculate_dti(
        self,
        monthly_debt: Decimal,
        monthly_income: Decimal
    ) -> Decimal:
        """
        Calculate Debt-to-Income (DTI) ratio.
        
        Formula: DTI = (monthly_debt / monthly_income) × 100
        
        DTI measures how much of monthly income goes toward debt payments.
        Standard thresholds:
        - ≤36%: Excellent
        - 37-43%: Acceptable (conventional loans)
        - >43%: High risk (may not qualify)
        
        Args:
            monthly_debt: Total monthly debt payments (mortgage, car, credit cards, etc.)
            monthly_income: Gross monthly income before taxes
        
        Returns:
            DTI ratio as percentage (e.g., 38.5 for 38.5%)
        
        Raises:
            ValueError: If monthly_income is zero or negative
            TypeError: If inputs are not Decimal/numeric types
        
        Examples:
            >>> calc = FinancialCalculator()
            >>> dti = calc.calculate_dti(Decimal("2500"), Decimal("6500"))
            >>> print(f"DTI: {dti}%")
            DTI: 38.46%
        """
        # Validate inputs
        if not isinstance(monthly_debt, (Decimal, int, float)):
            raise TypeError(f"monthly_debt must be numeric, got {type(monthly_debt)}")
        
        if not isinstance(monthly_income, (Decimal, int, float)):
            raise TypeError(f"monthly_income must be numeric, got {type(monthly_income)}")
        
        # Convert to Decimal for precision
        monthly_debt = Decimal(str(monthly_debt))
        monthly_income = Decimal(str(monthly_income))
        
        # Validate values
        if monthly_income <= 0:
            raise ValueError(
                f"monthly_income must be positive, got {monthly_income}"
            )
        
        if monthly_debt < 0:
            raise ValueError(
                f"monthly_debt cannot be negative, got {monthly_debt}"
            )
        
        # Calculate DTI ratio
        dti_ratio = (monthly_debt / monthly_income) * Decimal("100")
        
        # Round to 2 decimal places
        dti_ratio = dti_ratio.quantize(Decimal("0.01"))
        
        logger.info(
            f"DTI calculated: {dti_ratio}% "
            f"(debt: ${monthly_debt}, income: ${monthly_income})"
        )
        
        return dti_ratio
    
    def calculate_ltv(
        self,
        loan_amount: Decimal,
        property_value: Decimal
    ) -> Decimal:
        """
        Calculate Loan-to-Value (LTV) ratio.
        
        Formula: LTV = (loan_amount / property_value) × 100
        
        LTV measures the loan amount relative to property value.
        Standard thresholds:
        - ≤80%: Conventional (no PMI required)
        - 81-95%: High LTV (PMI required)
        - >95%: Very high risk
        
        Args:
            loan_amount: Total loan principal requested
            property_value: Appraised value of the property
        
        Returns:
            LTV ratio as percentage (e.g., 82.35 for 82.35%)
        
        Raises:
            ValueError: If property_value is zero or negative
            TypeError: If inputs are not Decimal/numeric types
        
        Examples:
            >>> calc = FinancialCalculator()
            >>> ltv = calc.calculate_ltv(Decimal("350000"), Decimal("425000"))
            >>> print(f"LTV: {ltv}%")
            LTV: 82.35%
        """
        # Validate inputs
        if not isinstance(loan_amount, (Decimal, int, float)):
            raise TypeError(f"loan_amount must be numeric, got {type(loan_amount)}")
        
        if not isinstance(property_value, (Decimal, int, float)):
            raise TypeError(f"property_value must be numeric, got {type(property_value)}")
        
        # Convert to Decimal for precision
        loan_amount = Decimal(str(loan_amount))
        property_value = Decimal(str(property_value))
        
        # Validate values
        if property_value <= 0:
            raise ValueError(
                f"property_value must be positive, got {property_value}"
            )
        
        if loan_amount < 0:
            raise ValueError(
                f"loan_amount cannot be negative, got {loan_amount}"
            )
        
        # Calculate LTV ratio
        ltv_ratio = (loan_amount / property_value) * Decimal("100")
        
        # Round to 2 decimal places
        ltv_ratio = ltv_ratio.quantize(Decimal("0.01"))
        
        logger.info(
            f"LTV calculated: {ltv_ratio}% "
            f"(loan: ${loan_amount}, property: ${property_value})"
        )
        
        return ltv_ratio
    
    def calculate_pti(
        self,
        loan_amount: Decimal,
        annual_interest_rate: Decimal,
        loan_term_years: int,
        monthly_income: Decimal
    ) -> Decimal:
        """
        Calculate Payment-to-Income (PTI) ratio.
        
        Formula: PTI = (monthly_payment / monthly_income) × 100
        Monthly payment calculated using amortization formula:
        M = P * [r(1+r)^n] / [(1+r)^n - 1]
        
        Where:
        - M = Monthly payment
        - P = Principal (loan amount)
        - r = Monthly interest rate (annual rate / 12)
        - n = Total payments (years × 12)
        
        PTI measures mortgage payment burden relative to income.
        Standard thresholds:
        - ≤28%: Comfortable
        - 29-36%: Acceptable
        - >36%: High burden
        
        Args:
            loan_amount: Total loan principal
            annual_interest_rate: Annual interest rate as percentage (e.g., 6.5 for 6.5%)
            loan_term_years: Loan term in years (e.g., 30 for 30-year mortgage)
            monthly_income: Gross monthly income before taxes
        
        Returns:
            PTI ratio as percentage (e.g., 28.5 for 28.5%)
        
        Raises:
            ValueError: If monthly_income is zero/negative or loan_term_years < 1
            TypeError: If inputs are not correct types
        
        Examples:
            >>> calc = FinancialCalculator()
            >>> pti = calc.calculate_pti(
            ...     Decimal("350000"),  # loan amount
            ...     Decimal("6.5"),     # 6.5% annual interest
            ...     30,                 # 30-year mortgage
            ...     Decimal("6500")     # monthly income
            ... )
            >>> print(f"PTI: {pti}%")
            PTI: 34.12%
        """
        # Validate inputs
        if not isinstance(loan_amount, (Decimal, int, float)):
            raise TypeError(f"loan_amount must be numeric, got {type(loan_amount)}")
        
        if not isinstance(annual_interest_rate, (Decimal, int, float)):
            raise TypeError(f"annual_interest_rate must be numeric, got {type(annual_interest_rate)}")
        
        if not isinstance(loan_term_years, int):
            raise TypeError(f"loan_term_years must be int, got {type(loan_term_years)}")
        
        if not isinstance(monthly_income, (Decimal, int, float)):
            raise TypeError(f"monthly_income must be numeric, got {type(monthly_income)}")
        
        # Convert to Decimal for precision
        loan_amount = Decimal(str(loan_amount))
        annual_interest_rate = Decimal(str(annual_interest_rate))
        monthly_income = Decimal(str(monthly_income))
        
        # Validate values
        if loan_amount < 0:
            raise ValueError(f"loan_amount cannot be negative, got {loan_amount}")
        
        if annual_interest_rate < 0:
            raise ValueError(f"annual_interest_rate cannot be negative, got {annual_interest_rate}")
        
        if loan_term_years < 1:
            raise ValueError(f"loan_term_years must be at least 1, got {loan_term_years}")
        
        if monthly_income <= 0:
            raise ValueError(f"monthly_income must be positive, got {monthly_income}")
        
        # Handle zero interest rate edge case (interest-free loan)
        if annual_interest_rate == 0:
            total_months = loan_term_years * 12
            monthly_payment = loan_amount / Decimal(total_months)
        else:
            # Calculate monthly interest rate (annual rate / 12 / 100)
            monthly_interest_rate = annual_interest_rate / Decimal("12") / Decimal("100")
            
            # Calculate total number of payments
            total_payments = loan_term_years * 12
            
            # Amortization formula: M = P * [r(1+r)^n] / [(1+r)^n - 1]
            # Using Decimal for precision
            one_plus_r = Decimal("1") + monthly_interest_rate
            one_plus_r_power_n = one_plus_r ** total_payments
            
            numerator = loan_amount * monthly_interest_rate * one_plus_r_power_n
            denominator = one_plus_r_power_n - Decimal("1")
            
            monthly_payment = numerator / denominator
        
        # Round monthly payment to 2 decimal places (cents)
        monthly_payment = monthly_payment.quantize(Decimal("0.01"))
        
        # Calculate PTI ratio
        pti_ratio = (monthly_payment / monthly_income) * Decimal("100")
        
        # Round to 2 decimal places
        pti_ratio = pti_ratio.quantize(Decimal("0.01"))
        
        logger.info(
            f"PTI calculated: {pti_ratio}% "
            f"(monthly payment: ${monthly_payment}, income: ${monthly_income}, "
            f"loan: ${loan_amount}, rate: {annual_interest_rate}%, term: {loan_term_years}yr)"
        )
        
        return pti_ratio
    
    def calculate_all_ratios(
        self,
        loan_amount: Decimal,
        property_value: Decimal,
        monthly_debt: Decimal,
        monthly_income: Decimal,
        annual_interest_rate: Decimal,
        loan_term_years: int
    ) -> Dict[str, Decimal]:
        """
        Calculate all three financial ratios (DTI, LTV, PTI) at once.
        
        Convenience method for calculating all ratios in a single call.
        
        Args:
            loan_amount: Total loan principal
            property_value: Appraised property value
            monthly_debt: Total monthly debt payments
            monthly_income: Gross monthly income
            annual_interest_rate: Annual interest rate as percentage
            loan_term_years: Loan term in years
        
        Returns:
            Dictionary with keys: 'dti', 'ltv', 'pti' (all as Decimal percentages)
        
        Examples:
            >>> calc = FinancialCalculator()
            >>> ratios = calc.calculate_all_ratios(
            ...     Decimal("350000"), Decimal("425000"),
            ...     Decimal("2500"), Decimal("6500"),
            ...     Decimal("6.5"), 30
            ... )
            >>> print(f"DTI: {ratios['dti']}%, LTV: {ratios['ltv']}%, PTI: {ratios['pti']}%")
        """
        dti = self.calculate_dti(monthly_debt, monthly_income)
        ltv = self.calculate_ltv(loan_amount, property_value)
        pti = self.calculate_pti(loan_amount, annual_interest_rate, loan_term_years, monthly_income)
        
        logger.info(
            f"All ratios calculated - DTI: {dti}%, LTV: {ltv}%, PTI: {pti}%"
        )
        
        return {
            "dti": dti,
            "ltv": ltv,
            "pti": pti,
        }
    
    def get_dti_assessment(self, dti: Decimal) -> str:
        """
        Get qualitative assessment of DTI ratio.
        
        Args:
            dti: DTI ratio as percentage
        
        Returns:
            Assessment string: "excellent", "good", "acceptable", "high", "very_high"
        """
        if dti <= 36:
            return "excellent"
        elif dti <= 43:
            return "acceptable"
        elif dti <= 50:
            return "high"
        else:
            return "very_high"
    
    def get_ltv_assessment(self, ltv: Decimal) -> str:
        """
        Get qualitative assessment of LTV ratio.
        
        Args:
            ltv: LTV ratio as percentage
        
        Returns:
            Assessment string: "excellent", "good", "high", "very_high"
        """
        if ltv <= 80:
            return "excellent"
        elif ltv <= 90:
            return "good"
        elif ltv <= 95:
            return "high"
        else:
            return "very_high"
    
    def get_pti_assessment(self, pti: Decimal) -> str:
        """
        Get qualitative assessment of PTI ratio.
        
        Args:
            pti: PTI ratio as percentage
        
        Returns:
            Assessment string: "comfortable", "acceptable", "high", "very_high"
        """
        if pti <= 28:
            return "comfortable"
        elif pti <= 36:
            return "acceptable"
        elif pti <= 45:
            return "high"
        else:
            return "very_high"


class RiskAnalyzer:
    """
    AI-powered risk analysis using GPT-4o.
    
    Combines calculated financial metrics (DTI, LTV, PTI) with credit data
    to generate comprehensive risk assessment with reasoning.
    
    Features:
    - GPT-4o integration for intelligent risk analysis
    - Identifies top 3 risk factors and 3 mitigating factors
    - Generates detailed reasoning for risk level
    - Produces structured RiskAssessment output per data model
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: Optional[str] = None
    ):
        """
        Initialize Risk Analyzer with Azure OpenAI credentials.
        
        Args:
            api_key: Azure OpenAI API key (defaults to env var)
            endpoint: Azure OpenAI endpoint (defaults to env var)
            deployment: GPT-4o deployment name (defaults to env var)
            api_version: API version (defaults to env var)
        """
        self.api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
        self.endpoint = endpoint or os.getenv("AZURE_OPENAI_ENDPOINT")
        self.deployment = deployment or os.getenv("AZURE_OPENAI_DEPLOYMENT_GPT4", "gpt-4o-mini")
        self.api_version = api_version or os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
        
        if not all([self.api_key, self.endpoint, self.deployment]):
            raise ValueError(
                "Missing Azure OpenAI credentials. Set AZURE_OPENAI_API_KEY, "
                "AZURE_OPENAI_ENDPOINT, and AZURE_OPENAI_DEPLOYMENT_GPT4 in environment."
            )
        
        # Initialize Azure OpenAI client
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=self.api_version,
            azure_endpoint=self.endpoint
        )
        
        logger.info(
            f"RiskAnalyzer initialized with deployment: {self.deployment}, "
            f"endpoint: {self.endpoint}"
        )
    
    def analyze_risk(
        self,
        application_id: str,
        credit_report: CreditReport,
        dti: Decimal,
        ltv: Decimal,
        pti: Decimal,
        monthly_debt: Decimal,
        monthly_income: Decimal,
        loan_amount: Decimal,
        property_value: Decimal
    ) -> RiskAssessment:
        """
        Perform comprehensive risk analysis using GPT-4o.
        
        Combines financial metrics and credit data to generate:
        - Risk level (low/medium/high)
        - Top 3 risk factors
        - Top 3 mitigating factors
        - Detailed reasoning
        - Recommendation (approve/review/deny)
        
        Args:
            application_id: Unique application identifier
            credit_report: Credit report from MCP server
            dti: Debt-to-Income ratio (percentage)
            ltv: Loan-to-Value ratio (percentage)
            pti: Payment-to-Income ratio (percentage)
            monthly_debt: Total monthly debt payments
            monthly_income: Gross monthly income
            loan_amount: Requested loan amount
            property_value: Property appraised value
        
        Returns:
            RiskAssessment object with structured risk analysis
        
        Raises:
            ValueError: If GPT-4o returns invalid response
            Exception: If API call fails
        
        Examples:
            >>> analyzer = RiskAnalyzer()
            >>> credit = CreditReport(ssn="111-11-1111", credit_score=720, ...)
            >>> assessment = analyzer.analyze_risk(
            ...     "APP-2025-001", credit,
            ...     Decimal("38.5"), Decimal("82.35"), Decimal("34.12"),
            ...     Decimal("2500"), Decimal("6500"),
            ...     Decimal("350000"), Decimal("425000")
            ... )
            >>> print(assessment.risk_level)
            medium
        """
        logger.info(f"Starting risk analysis for application {application_id}")
        
        # Build prompt with financial context
        prompt = self._build_risk_analysis_prompt(
            credit_report=credit_report,
            dti=dti,
            ltv=ltv,
            pti=pti,
            monthly_debt=monthly_debt,
            monthly_income=monthly_income,
            loan_amount=loan_amount,
            property_value=property_value
        )
        
        try:
            # Call GPT-4o for risk analysis
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an expert loan underwriting risk analyst. "
                            "Analyze financial metrics and credit data to assess loan risk. "
                            "Provide structured, objective risk assessment following industry standards."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3,  # Lower temperature for consistent analysis
                max_tokens=1500,
                response_format={"type": "json_object"}  # Ensure JSON response
            )
            
            # Parse GPT-4o response
            result = json.loads(response.choices[0].message.content)
            
            logger.info(
                f"GPT-4o analysis complete: risk_level={result.get('risk_level')}, "
                f"tokens={response.usage.total_tokens}"
            )
            
            # Calculate risk score (0-100)
            risk_score = self._calculate_risk_score(
                risk_level=result["risk_level"],
                credit_score=credit_report.credit_score,
                dti=dti,
                ltv=ltv,
                pti=pti
            )
            
            # Create RiskAssessment object
            assessment = RiskAssessment(
                application_id=application_id,
                assessed_at=datetime.utcnow(),
                risk_level=result["risk_level"],
                risk_score=risk_score,
                debt_to_income_ratio=dti,
                loan_to_value_ratio=ltv,
                monthly_debt_payments=monthly_debt,
                monthly_gross_income=monthly_income,
                risk_factors=result["risk_factors"],
                mitigating_factors=result["mitigating_factors"],
                reasoning=result["reasoning"],
                recommendation=result["recommendation"]
            )
            
            logger.info(
                f"Risk assessment created: {application_id} - "
                f"{assessment.risk_level} risk, score {assessment.risk_score}"
            )
            
            return assessment
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse GPT-4o response as JSON: {e}")
            raise ValueError(f"Invalid JSON response from GPT-4o: {e}")
        
        except KeyError as e:
            logger.error(f"Missing required field in GPT-4o response: {e}")
            raise ValueError(f"GPT-4o response missing field: {e}")
        
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}")
            raise
    
    def _build_risk_analysis_prompt(
        self,
        credit_report: CreditReport,
        dti: Decimal,
        ltv: Decimal,
        pti: Decimal,
        monthly_debt: Decimal,
        monthly_income: Decimal,
        loan_amount: Decimal,
        property_value: Decimal
    ) -> str:
        """
        Build GPT-4o prompt with financial context.
        
        Structures all relevant data for risk analysis in clear format.
        
        Returns:
            Formatted prompt string
        """
        prompt = f"""Analyze the following loan application for risk assessment:

## Financial Metrics
- **Debt-to-Income (DTI)**: {dti}%
  - Industry threshold: ≤36% excellent, ≤43% acceptable
  - Monthly debt: ${monthly_debt}
  - Monthly income: ${monthly_income}

- **Loan-to-Value (LTV)**: {ltv}%
  - Industry threshold: ≤80% no PMI, ≤95% acceptable
  - Loan amount: ${loan_amount}
  - Property value: ${property_value}

- **Payment-to-Income (PTI)**: {pti}%
  - Industry threshold: ≤28% comfortable, ≤36% acceptable

## Credit Profile
- **Credit Score**: {credit_report.credit_score} (Range: 300-850)
- **Credit Utilization**: {credit_report.credit_utilization}%
- **Payment History**: {credit_report.payment_history}
- **Open Accounts**: {credit_report.accounts_open}
- **Derogatory Marks**: {credit_report.derogatory_marks}
- **Credit Age**: {credit_report.credit_age_months} months
- **Late Payments (12mo)**: {credit_report.late_payments_12mo}
- **Hard Inquiries (12mo)**: {credit_report.hard_inquiries_12mo}

## Your Task
Provide a comprehensive risk assessment with the following structure:

```json
{{
  "risk_level": "<low|medium|high>",
  "risk_factors": [
    "<Factor 1: describe specific risk>",
    "<Factor 2: describe specific risk>",
    "<Factor 3: describe specific risk>"
  ],
  "mitigating_factors": [
    "<Factor 1: describe positive aspect>",
    "<Factor 2: describe positive aspect>",
    "<Factor 3: describe positive aspect>"
  ],
  "reasoning": "<3-5 sentences explaining the risk level, considering both risk factors and mitigating factors. Be specific with numbers and thresholds.>",
  "recommendation": "<approve|review|deny>"
}}
```

## Guidelines
1. **Risk Level Criteria**:
   - **Low**: Credit ≥740, DTI ≤36%, LTV ≤80%, excellent payment history
   - **Medium**: Credit 640-739, DTI 37-43%, LTV 81-95%, good payment history
   - **High**: Credit <640, DTI >43%, LTV >95%, or poor payment history

2. **Risk Factors**: Focus on metrics exceeding thresholds or negative credit indicators

3. **Mitigating Factors**: Highlight strengths like high credit score, low utilization, stable history

4. **Recommendation**:
   - **approve**: Low risk, meets all standards
   - **review**: Medium risk, needs manual review or conditions
   - **deny**: High risk, does not meet minimum standards

Provide objective, data-driven assessment following industry underwriting standards."""

        return prompt
    
    def _calculate_risk_score(
        self,
        risk_level: str,
        credit_score: int,
        dti: Decimal,
        ltv: Decimal,
        pti: Decimal
    ) -> float:
        """
        Calculate numeric risk score (0-100).
        
        Lower score = lower risk, higher score = higher risk.
        
        Combines multiple factors:
        - Credit score (40% weight)
        - DTI ratio (25% weight)
        - LTV ratio (20% weight)
        - PTI ratio (15% weight)
        
        Args:
            risk_level: low/medium/high from GPT-4o
            credit_score: FICO score (300-850)
            dti: DTI percentage
            ltv: LTV percentage
            pti: PTI percentage
        
        Returns:
            Risk score (0-100, lower is better)
        """
        # Credit score component (inverted: 850 → 0, 300 → 100)
        credit_component = (850 - credit_score) / 550 * 100 * 0.40
        
        # DTI component (36% threshold)
        dti_component = min(float(dti) / 43 * 100, 100) * 0.25
        
        # LTV component (80% threshold)
        ltv_component = min(float(ltv) / 95 * 100, 100) * 0.20
        
        # PTI component (28% threshold)
        pti_component = min(float(pti) / 36 * 100, 100) * 0.15
        
        # Calculate weighted score
        score = credit_component + dti_component + ltv_component + pti_component
        
        # Ensure score is in valid range
        score = max(0.0, min(100.0, score))
        
        # Round to 2 decimal places
        score = round(score, 2)
        
        logger.info(
            f"Risk score calculated: {score} "
            f"(credit: {credit_component:.2f}, dti: {dti_component:.2f}, "
            f"ltv: {ltv_component:.2f}, pti: {pti_component:.2f})"
        )
        
        return score


class RiskVisualizer:
    """
    Interactive visualization generator for financial risk metrics.
    
    Creates Plotly charts to display DTI, LTV, and PTI ratios with
    industry threshold lines for clear visual risk assessment.
    
    Features:
    - Bar chart for all three ratios
    - Threshold lines for industry standards
    - Color-coded risk levels (green/yellow/red)
    - Interactive hover labels with detailed information
    - Responsive layout for notebooks
    """
    
    def __init__(self):
        """Initialize risk visualizer."""
        logger.info("RiskVisualizer initialized")
    
    def create_metrics_chart(
        self,
        dti: Decimal,
        ltv: Decimal,
        pti: Decimal,
        risk_level: str = "medium",
        title: str = "Financial Risk Metrics"
    ) -> go.Figure:
        """
        Create interactive bar chart for DTI, LTV, PTI ratios.
        
        Displays all three financial metrics with:
        - Color-coded bars based on risk level
        - Threshold lines for industry standards
        - Interactive hover labels
        - Clear visual indication of risk
        
        Args:
            dti: Debt-to-Income ratio (percentage)
            ltv: Loan-to-Value ratio (percentage)
            pti: Payment-to-Income ratio (percentage)
            risk_level: Overall risk level ("low", "medium", "high")
            title: Chart title
        
        Returns:
            Plotly Figure object ready for display
        
        Examples:
            >>> visualizer = RiskVisualizer()
            >>> fig = visualizer.create_metrics_chart(
            ...     Decimal("38.46"), Decimal("82.35"), Decimal("34.03"),
            ...     risk_level="medium"
            ... )
            >>> fig.show()  # Display in notebook
        """
        logger.info(
            f"Creating metrics chart: DTI={dti}%, LTV={ltv}%, PTI={pti}%, "
            f"risk_level={risk_level}"
        )
        
        # Convert Decimal to float for Plotly
        dti_val = float(dti)
        ltv_val = float(ltv)
        pti_val = float(pti)
        
        # Determine bar colors based on risk level
        color_map = {
            "low": "#10b981",      # Green
            "medium": "#f59e0b",   # Yellow/Orange
            "high": "#ef4444"      # Red
        }
        bar_color = color_map.get(risk_level.lower(), "#6b7280")  # Gray default
        
        # Create figure
        fig = go.Figure()
        
        # Add bars for each metric
        fig.add_trace(go.Bar(
            x=["DTI", "LTV", "PTI"],
            y=[dti_val, ltv_val, pti_val],
            name="Current Ratios",
            marker=dict(
                color=[bar_color, bar_color, bar_color],
                line=dict(color='rgba(0,0,0,0.3)', width=1)
            ),
            text=[f"{dti_val:.2f}%", f"{ltv_val:.2f}%", f"{pti_val:.2f}%"],
            textposition='outside',
            hovertemplate=(
                "<b>%{x}</b><br>"
                "Value: %{y:.2f}%<br>"
                "<extra></extra>"
            )
        ))
        
        # Add threshold lines for DTI
        # Excellent: ≤36%, Acceptable: ≤43%
        fig.add_shape(
            type="line",
            x0=-0.5, x1=0.5,
            y0=36, y1=36,
            line=dict(color="green", width=2, dash="dash"),
            name="DTI Excellent (36%)"
        )
        fig.add_shape(
            type="line",
            x0=-0.5, x1=0.5,
            y0=43, y1=43,
            line=dict(color="orange", width=2, dash="dash"),
            name="DTI Acceptable (43%)"
        )
        
        # Add threshold lines for LTV
        # No PMI: ≤80%, Acceptable: ≤95%
        fig.add_shape(
            type="line",
            x0=0.5, x1=1.5,
            y0=80, y1=80,
            line=dict(color="green", width=2, dash="dash"),
            name="LTV No PMI (80%)"
        )
        fig.add_shape(
            type="line",
            x0=0.5, x1=1.5,
            y0=95, y1=95,
            line=dict(color="orange", width=2, dash="dash"),
            name="LTV Acceptable (95%)"
        )
        
        # Add threshold lines for PTI
        # Comfortable: ≤28%, Acceptable: ≤36%
        fig.add_shape(
            type="line",
            x0=1.5, x1=2.5,
            y0=28, y1=28,
            line=dict(color="green", width=2, dash="dash"),
            name="PTI Comfortable (28%)"
        )
        fig.add_shape(
            type="line",
            x0=1.5, x1=2.5,
            y0=36, y1=36,
            line=dict(color="orange", width=2, dash="dash"),
            name="PTI Acceptable (36%)"
        )
        
        # Add annotations for thresholds
        annotations = [
            # DTI thresholds
            dict(
                x=0, y=36, text="Excellent (36%)",
                showarrow=False, yshift=10, font=dict(size=10, color="green")
            ),
            dict(
                x=0, y=43, text="Acceptable (43%)",
                showarrow=False, yshift=10, font=dict(size=10, color="orange")
            ),
            # LTV thresholds
            dict(
                x=1, y=80, text="No PMI (80%)",
                showarrow=False, yshift=10, font=dict(size=10, color="green")
            ),
            dict(
                x=1, y=95, text="Acceptable (95%)",
                showarrow=False, yshift=10, font=dict(size=10, color="orange")
            ),
            # PTI thresholds
            dict(
                x=2, y=28, text="Comfortable (28%)",
                showarrow=False, yshift=10, font=dict(size=10, color="green")
            ),
            dict(
                x=2, y=36, text="Acceptable (36%)",
                showarrow=False, yshift=10, font=dict(size=10, color="orange")
            ),
        ]
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"{title}<br><sub>Risk Level: {risk_level.upper()}</sub>",
                font=dict(size=18)
            ),
            xaxis=dict(
                title=dict(text="Financial Ratio", font=dict(size=14)),
                tickfont=dict(size=12)
            ),
            yaxis=dict(
                title=dict(text="Percentage (%)", font=dict(size=14)),
                tickfont=dict(size=12),
                range=[0, max(dti_val, ltv_val, pti_val, 100) + 10]
            ),
            annotations=annotations,
            showlegend=False,
            hovermode='x unified',
            plot_bgcolor='rgba(240,240,240,0.5)',
            height=500,
            width=800,
            margin=dict(t=100, b=80, l=80, r=80)
        )
        
        logger.info("Metrics chart created successfully")
        return fig
    
    def create_comparison_chart(
        self,
        scenarios: List[Dict[str, Union[str, Decimal]]],
        title: str = "Risk Comparison Analysis"
    ) -> go.Figure:
        """
        Create side-by-side comparison chart for multiple scenarios.
        
        Useful for comparing different applicants or what-if scenarios.
        
        Args:
            scenarios: List of scenario dicts, each containing:
                - name: Scenario name (e.g., "Applicant A")
                - dti: DTI ratio
                - ltv: LTV ratio
                - pti: PTI ratio
                - risk_level: Risk level (optional)
            title: Chart title
        
        Returns:
            Plotly Figure object with grouped bar chart
        
        Examples:
            >>> visualizer = RiskVisualizer()
            >>> scenarios = [
            ...     {
            ...         "name": "Excellent Credit (780)",
            ...         "dti": Decimal("32.5"),
            ...         "ltv": Decimal("75.0"),
            ...         "pti": Decimal("26.0"),
            ...         "risk_level": "low"
            ...     },
            ...     {
            ...         "name": "Poor Credit (620)",
            ...         "dti": Decimal("45.0"),
            ...         "ltv": Decimal("92.0"),
            ...         "pti": Decimal("38.0"),
            ...         "risk_level": "high"
            ...     }
            ... ]
            >>> fig = visualizer.create_comparison_chart(scenarios)
            >>> fig.show()
        """
        logger.info(f"Creating comparison chart with {len(scenarios)} scenarios")
        
        # Extract data for each metric
        names = [s["name"] for s in scenarios]
        dti_values = [float(s["dti"]) for s in scenarios]
        ltv_values = [float(s["ltv"]) for s in scenarios]
        pti_values = [float(s["pti"]) for s in scenarios]
        
        # Determine colors based on risk levels
        color_map = {
            "low": "#10b981",      # Green
            "medium": "#f59e0b",   # Yellow/Orange
            "high": "#ef4444"      # Red
        }
        colors = [
            color_map.get(s.get("risk_level", "medium").lower(), "#6b7280")
            for s in scenarios
        ]
        
        # Create figure with subplots
        fig = make_subplots(
            rows=1, cols=3,
            subplot_titles=("Debt-to-Income (DTI)", "Loan-to-Value (LTV)", "Payment-to-Income (PTI)"),
            horizontal_spacing=0.12
        )
        
        # Add DTI bars
        fig.add_trace(
            go.Bar(
                x=names,
                y=dti_values,
                name="DTI",
                marker=dict(color=colors),
                text=[f"{v:.1f}%" for v in dti_values],
                textposition='outside',
                hovertemplate="<b>%{x}</b><br>DTI: %{y:.2f}%<extra></extra>"
            ),
            row=1, col=1
        )
        
        # Add LTV bars
        fig.add_trace(
            go.Bar(
                x=names,
                y=ltv_values,
                name="LTV",
                marker=dict(color=colors),
                text=[f"{v:.1f}%" for v in ltv_values],
                textposition='outside',
                hovertemplate="<b>%{x}</b><br>LTV: %{y:.2f}%<extra></extra>"
            ),
            row=1, col=2
        )
        
        # Add PTI bars
        fig.add_trace(
            go.Bar(
                x=names,
                y=pti_values,
                name="PTI",
                marker=dict(color=colors),
                text=[f"{v:.1f}%" for v in pti_values],
                textposition='outside',
                hovertemplate="<b>%{x}</b><br>PTI: %{y:.2f}%<extra></extra>"
            ),
            row=1, col=3
        )
        
        # Add threshold lines
        # DTI thresholds
        fig.add_hline(y=36, line_dash="dash", line_color="green", opacity=0.7, row=1, col=1)
        fig.add_hline(y=43, line_dash="dash", line_color="orange", opacity=0.7, row=1, col=1)
        
        # LTV thresholds
        fig.add_hline(y=80, line_dash="dash", line_color="green", opacity=0.7, row=1, col=2)
        fig.add_hline(y=95, line_dash="dash", line_color="orange", opacity=0.7, row=1, col=2)
        
        # PTI thresholds
        fig.add_hline(y=28, line_dash="dash", line_color="green", opacity=0.7, row=1, col=3)
        fig.add_hline(y=36, line_dash="dash", line_color="orange", opacity=0.7, row=1, col=3)
        
        # Update layout
        fig.update_xaxes(tickangle=45)
        fig.update_yaxes(title_text="Percentage (%)", row=1, col=1)
        fig.update_yaxes(title_text="Percentage (%)", row=1, col=2)
        fig.update_yaxes(title_text="Percentage (%)", row=1, col=3)
        
        fig.update_layout(
            title=dict(text=title, font=dict(size=18)),
            showlegend=False,
            height=500,
            width=1200,
            plot_bgcolor='rgba(240,240,240,0.5)',
            margin=dict(t=100, b=120, l=60, r=60)
        )
        
        logger.info("Comparison chart created successfully")
        return fig
    
    def create_risk_gauge(
        self,
        risk_score: float,
        risk_level: str,
        title: str = "Overall Risk Score"
    ) -> go.Figure:
        """
        Create gauge chart for risk score visualization.
        
        Displays risk score (0-100) with color-coded zones.
        
        Args:
            risk_score: Numeric risk score (0-100, lower is better)
            risk_level: Risk level classification ("low", "medium", "high")
            title: Chart title
        
        Returns:
            Plotly Figure object with gauge chart
        
        Examples:
            >>> visualizer = RiskVisualizer()
            >>> fig = visualizer.create_risk_gauge(63.33, "medium")
            >>> fig.show()
        """
        logger.info(f"Creating risk gauge: score={risk_score}, level={risk_level}")
        
        # Determine gauge color
        if risk_score < 40:
            gauge_color = "#10b981"  # Green (low risk)
        elif risk_score < 70:
            gauge_color = "#f59e0b"  # Yellow/Orange (medium risk)
        else:
            gauge_color = "#ef4444"  # Red (high risk)
        
        # Create gauge
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=risk_score,
            title=dict(text=f"{title}<br><sub>Risk Level: {risk_level.upper()}</sub>"),
            delta=dict(reference=50, increasing=dict(color="red")),
            gauge=dict(
                axis=dict(range=[0, 100], tickwidth=1, tickcolor="darkgray"),
                bar=dict(color=gauge_color, thickness=0.75),
                bgcolor="white",
                borderwidth=2,
                bordercolor="gray",
                steps=[
                    dict(range=[0, 40], color="rgba(16, 185, 129, 0.2)"),   # Low risk zone
                    dict(range=[40, 70], color="rgba(245, 158, 11, 0.2)"),  # Medium risk zone
                    dict(range=[70, 100], color="rgba(239, 68, 68, 0.2)")   # High risk zone
                ],
                threshold=dict(
                    line=dict(color="black", width=4),
                    thickness=0.75,
                    value=risk_score
                )
            )
        ))
        
        # Add annotations for zones
        fig.add_annotation(
            x=0.5, y=0.1,
            text="<b>Low Risk:</b> 0-40 | <b>Medium Risk:</b> 40-70 | <b>High Risk:</b> 70-100",
            showarrow=False,
            font=dict(size=11, color="gray"),
            xref="paper", yref="paper"
        )
        
        fig.update_layout(
            height=400,
            width=600,
            margin=dict(t=100, b=50, l=50, r=50)
        )
        
        logger.info("Risk gauge created successfully")
        return fig
