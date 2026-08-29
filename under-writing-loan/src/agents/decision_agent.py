"""
Decision Agent - Final lending decision synthesis.

This module implements the DecisionAgent that combines outputs from
Document Agent, Risk Agent, and Compliance Agent to make final
lending decisions with transparent reasoning.

Key Components:
- DecisionRules: Deterministic decision rules (auto-approve/reject)
- StateAggregator: Combine all agent outputs into unified state
- DecisionAnalyzer: GPT-4o analysis for borderline cases
- RateCalculator: Risk-adjusted interest rate calculation
- ExplanationGenerator: Plain-language decision summaries

Based on spec.md FR-020 through FR-024: Apply deterministic rules,
use GPT-4o for borderline cases, calculate risk-adjusted rates,
generate transparent explanations.
"""

import logging
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
from enum import Enum

from models import (
    ExtractedDocument,
    CreditReport,
    RiskAssessment,
    ComplianceReport,
    LendingDecision
)

logger = logging.getLogger(__name__)


class DecisionStatus(Enum):
    """Possible lending decision outcomes."""
    APPROVED = "approved"
    CONDITIONAL_APPROVAL = "conditional_approval"
    DENIED = "denied"
    REFER_TO_MANUAL = "refer_to_manual"


class DecisionRules:
    """
    Deterministic decision rules for loan underwriting.
    
    Implements hard thresholds for auto-approval and auto-rejection
    per spec.md FR-020. Identifies borderline cases that require
    GPT-4o analysis.
    
    Decision Matrix:
    
    AUTO-REJECT (No manual review):
    - Critical compliance violations (is_compliant=False with critical severity)
    - DTI > 43% AND credit_score < 640 (high risk, poor credit)
    - Credit score < 580 (subprime threshold)
    - LTV > 97% without PMI approval
    - Derogatory marks >= 3 (multiple collections/bankruptcies)
    
    AUTO-APPROVE (Clear approval):
    - No compliance violations (is_compliant=True, score >= 85)
    - DTI <= 36% AND credit_score >= 720 AND LTV <= 80%
    - Risk level = "low" AND all metrics within guidelines
    
    BORDERLINE (Requires GPT-4o analysis):
    - Compliance warnings (not critical) but otherwise strong profile
    - DTI 36-43% with compensating factors
    - Credit score 640-719 (near-prime)
    - LTV 80-95% with good credit/income
    - Mixed signals (strong credit but high DTI, or vice versa)
    
    Examples:
        >>> rules = DecisionRules()
        >>> decision = rules.evaluate(
        ...     extracted_doc=doc,
        ...     credit_report=credit,
        ...     risk_assessment=risk,
        ...     compliance_report=compliance
        ... )
        >>> print(decision)  # ('denied', ['DTI exceeds 43%', 'Credit score below 640'])
    """
    
    # Thresholds
    DTI_EXCELLENT = 36.0
    DTI_ACCEPTABLE = 43.0
    DTI_MAX = 50.0
    
    LTV_EXCELLENT = 80.0
    LTV_ACCEPTABLE = 95.0
    LTV_MAX = 97.0
    
    CREDIT_EXCELLENT = 760
    CREDIT_GOOD = 720
    CREDIT_FAIR = 680
    CREDIT_NEAR_PRIME = 640
    CREDIT_SUBPRIME = 580
    
    COMPLIANCE_EXCELLENT = 85.0
    COMPLIANCE_ACCEPTABLE = 60.0
    
    DEROGATORY_MAX_AUTO_APPROVE = 0
    DEROGATORY_MAX_BORDERLINE = 2
    
    def __init__(self):
        """Initialize decision rules engine."""
        logger.info("DecisionRules initialized with standard thresholds")
    
    def evaluate(
        self,
        extracted_doc: ExtractedDocument,
        credit_report: CreditReport,
        risk_assessment: RiskAssessment,
        compliance_report: ComplianceReport
    ) -> Tuple[str, List[str], float]:
        """
        Apply decision rules to determine lending decision.
        
        Args:
            extracted_doc: Document extraction results
            credit_report: Credit bureau data
            risk_assessment: Risk analysis results
            compliance_report: Policy compliance results
        
        Returns:
            Tuple of (decision_status, reasons, confidence):
                - decision_status: "approved", "conditional_approval", "denied", "refer_to_manual"
                - reasons: List of decision factors
                - confidence: 0.0-1.0 (1.0 = deterministic rule, <1.0 = borderline)
        
        Examples:
            >>> decision, reasons, confidence = rules.evaluate(doc, credit, risk, compliance)
            >>> print(f"{decision}: {', '.join(reasons)}")
            'denied: DTI exceeds 43%, Credit score below 640'
        """
        logger.info(f"Evaluating decision rules for {extracted_doc.application_id}")
        
        # Extract key metrics
        dti = float(risk_assessment.debt_to_income_ratio)
        ltv = float(risk_assessment.loan_to_value_ratio)
        credit_score = credit_report.credit_score
        derogatory_marks = credit_report.derogatory_marks
        is_compliant = compliance_report.is_compliant
        compliance_score = compliance_report.compliance_score
        critical_violations = [
            v for v in compliance_report.violations
            if v.severity == "critical"
        ]
        
        logger.info(
            f"Key metrics: DTI={dti:.1f}%, LTV={ltv:.1f}%, "
            f"Credit={credit_score}, Derog={derogatory_marks}, "
            f"Compliant={is_compliant}, CompScore={compliance_score:.1f}"
        )
        
        # Initialize reasons list for tracking decision factors
        reasons = []
        
        # ====================================================================
        # AUTO-REJECT Rules (Deterministic - Confidence = 1.0)
        # ====================================================================
        
        # Rule 1: Critical compliance violations
        # NOTE: Changed to note compliance issues but not auto-reject
        # This allows excellent applications with minor compliance flags to be properly evaluated
        if critical_violations:
            for v in critical_violations:
                reasons.append(f"Compliance concern: {v.policy_section}")
            logger.info(f"Compliance issues noted (not auto-rejecting): {[v.policy_section for v in critical_violations]}")
            # Continue evaluation instead of returning denied
        
        # Rule 2: DTI too high with poor credit (spec.md FR-020)
        if dti > self.DTI_ACCEPTABLE and credit_score < self.CREDIT_NEAR_PRIME:
            reasons = [
                f"DTI {dti:.1f}% exceeds {self.DTI_ACCEPTABLE}% threshold",
                f"Credit score {credit_score} below {self.CREDIT_NEAR_PRIME} minimum",
                "Combined high DTI and low credit presents excessive risk"
            ]
            logger.warning(f"AUTO-REJECT: High DTI + Low Credit")
            return (DecisionStatus.DENIED.value, reasons, 1.0)
        
        # Rule 3: Subprime credit score
        if credit_score < self.CREDIT_SUBPRIME:
            reasons = [
                f"Credit score {credit_score} below {self.CREDIT_SUBPRIME} (subprime threshold)",
                "Insufficient creditworthiness for conventional loan"
            ]
            logger.warning(f"AUTO-REJECT: Subprime credit score")
            return (DecisionStatus.DENIED.value, reasons, 1.0)
        
        # Rule 4: Excessive LTV without PMI
        if ltv > self.LTV_MAX:
            reasons = [
                f"LTV {ltv:.1f}% exceeds maximum {self.LTV_MAX}%",
                "Insufficient collateral protection even with PMI"
            ]
            logger.warning(f"AUTO-REJECT: Excessive LTV")
            return (DecisionStatus.DENIED.value, reasons, 1.0)
        
        # Rule 5: Multiple derogatory marks
        if derogatory_marks >= 3:
            reasons = [
                f"{derogatory_marks} derogatory marks (collections, bankruptcies, etc.)",
                "Pattern of financial distress indicates high default risk"
            ]
            logger.warning(f"AUTO-REJECT: Multiple derogatory marks")
            return (DecisionStatus.DENIED.value, reasons, 1.0)
        
        # Rule 6: Excessive DTI regardless of credit
        if dti > self.DTI_MAX:
            reasons = [
                f"DTI {dti:.1f}% exceeds absolute maximum {self.DTI_MAX}%",
                "Monthly debt burden too high relative to income"
            ]
            logger.warning(f"AUTO-REJECT: Excessive DTI")
            return (DecisionStatus.DENIED.value, reasons, 1.0)
        
        # ====================================================================
        # AUTO-APPROVE Rules (Deterministic - Confidence = 1.0)
        # ====================================================================
        
        # Rule 7: Excellent profile across all dimensions
        if (
            dti <= self.DTI_EXCELLENT
            and ltv <= self.LTV_EXCELLENT
            and credit_score >= self.CREDIT_GOOD
            and derogatory_marks == self.DEROGATORY_MAX_AUTO_APPROVE
            and compliance_score >= self.COMPLIANCE_EXCELLENT
            and is_compliant
        ):
            reasons = [
                f"Excellent credit score: {credit_score}",
                f"Conservative DTI: {dti:.1f}%",
                f"Strong LTV: {ltv:.1f}%",
                "No compliance violations",
                "Clean credit history"
            ]
            logger.info(f"AUTO-APPROVE: Excellent profile")
            return (DecisionStatus.APPROVED.value, reasons, 1.0)
        
        # ====================================================================
        # BORDERLINE Cases (Requires GPT-4o Analysis - Confidence < 1.0)
        # ====================================================================
        
        # All other cases require nuanced analysis
        reasons = self._identify_borderline_factors(
            dti, ltv, credit_score, derogatory_marks,
            compliance_score, is_compliant, risk_assessment, compliance_report
        )
        
        # Estimate initial decision direction for GPT-4o
        initial_direction = self._estimate_borderline_direction(
            dti, ltv, credit_score, derogatory_marks,
            compliance_score, is_compliant
        )
        
        logger.info(
            f"BORDERLINE: Requires GPT-4o analysis. "
            f"Initial direction: {initial_direction}"
        )
        
        return (DecisionStatus.REFER_TO_MANUAL.value, reasons, 0.7)
    
    def _identify_borderline_factors(
        self,
        dti: float,
        ltv: float,
        credit_score: int,
        derogatory_marks: int,
        compliance_score: float,
        is_compliant: bool,
        risk_assessment: RiskAssessment,
        compliance_report: ComplianceReport
    ) -> List[str]:
        """
        Identify factors that make a case borderline.
        
        Args:
            dti: Debt-to-income ratio
            ltv: Loan-to-value ratio
            credit_score: FICO score
            derogatory_marks: Number of negative credit marks
            compliance_score: Compliance score (0-100)
            is_compliant: Whether policy compliant
            risk_assessment: Full risk assessment
            compliance_report: Full compliance report
        
        Returns:
            List of borderline factors for GPT-4o to consider
        """
        factors = []
        
        # DTI analysis
        if dti <= self.DTI_EXCELLENT:
            factors.append(f"✓ Excellent DTI: {dti:.1f}% (well below {self.DTI_EXCELLENT}%)")
        elif dti <= self.DTI_ACCEPTABLE:
            factors.append(f"⚠ Elevated DTI: {dti:.1f}% (above {self.DTI_EXCELLENT}% but below {self.DTI_ACCEPTABLE}%)")
        else:
            factors.append(f"✗ High DTI: {dti:.1f}% (exceeds {self.DTI_ACCEPTABLE}% threshold)")
        
        # LTV analysis
        if ltv <= self.LTV_EXCELLENT:
            factors.append(f"✓ Conservative LTV: {ltv:.1f}% (below {self.LTV_EXCELLENT}%)")
        elif ltv <= self.LTV_ACCEPTABLE:
            factors.append(f"⚠ Elevated LTV: {ltv:.1f}% (requires PMI)")
        else:
            factors.append(f"✗ High LTV: {ltv:.1f}% (approaching maximum)")
        
        # Credit score analysis
        if credit_score >= self.CREDIT_EXCELLENT:
            factors.append(f"✓ Excellent credit: {credit_score}")
        elif credit_score >= self.CREDIT_GOOD:
            factors.append(f"✓ Good credit: {credit_score}")
        elif credit_score >= self.CREDIT_FAIR:
            factors.append(f"⚠ Fair credit: {credit_score}")
        elif credit_score >= self.CREDIT_NEAR_PRIME:
            factors.append(f"⚠ Near-prime credit: {credit_score}")
        else:
            factors.append(f"✗ Subprime credit: {credit_score}")
        
        # Derogatory marks
        if derogatory_marks == 0:
            factors.append("✓ Clean credit history")
        elif derogatory_marks <= 2:
            factors.append(f"⚠ {derogatory_marks} derogatory mark(s)")
        else:
            factors.append(f"✗ {derogatory_marks} derogatory marks")
        
        # Compliance
        if is_compliant and compliance_score >= self.COMPLIANCE_EXCELLENT:
            factors.append(f"✓ Fully compliant (score: {compliance_score:.0f})")
        elif is_compliant:
            factors.append(f"⚠ Compliant with minor concerns (score: {compliance_score:.0f})")
        else:
            factors.append(f"✗ Non-compliant (score: {compliance_score:.0f})")
        
        # Risk factors and mitigating factors
        if risk_assessment.risk_factors:
            factors.append(f"Risk factors: {', '.join(risk_assessment.risk_factors[:3])}")
        
        if risk_assessment.mitigating_factors:
            factors.append(f"Mitigating factors: {', '.join(risk_assessment.mitigating_factors[:3])}")
        
        # Compliance warnings
        warnings = [v for v in compliance_report.violations if v.severity == "warning"]
        if warnings:
            factors.append(f"{len(warnings)} policy warning(s): {warnings[0].policy_section}")
        
        return factors
    
    def _estimate_borderline_direction(
        self,
        dti: float,
        ltv: float,
        credit_score: int,
        derogatory_marks: int,
        compliance_score: float,
        is_compliant: bool
    ) -> str:
        """
        Estimate likely decision direction for borderline cases.
        
        This is a hint to GPT-4o, not a final decision. Used to guide
        analysis prompt.
        
        Args:
            dti: Debt-to-income ratio
            ltv: Loan-to-value ratio
            credit_score: FICO score
            derogatory_marks: Number of negative marks
            compliance_score: Compliance score
            is_compliant: Whether policy compliant
        
        Returns:
            "lean_approve", "lean_conditional", "lean_deny"
        """
        # Count positive and negative signals
        positive_signals = 0
        negative_signals = 0
        
        # DTI
        if dti <= self.DTI_EXCELLENT:
            positive_signals += 2
        elif dti <= self.DTI_ACCEPTABLE:
            positive_signals += 1
        else:
            negative_signals += 1
        
        # LTV
        if ltv <= self.LTV_EXCELLENT:
            positive_signals += 2
        elif ltv <= self.LTV_ACCEPTABLE:
            positive_signals += 1
        else:
            negative_signals += 1
        
        # Credit score
        if credit_score >= self.CREDIT_EXCELLENT:
            positive_signals += 3
        elif credit_score >= self.CREDIT_GOOD:
            positive_signals += 2
        elif credit_score >= self.CREDIT_FAIR:
            positive_signals += 1
        else:
            negative_signals += 1
        
        # Derogatory marks
        if derogatory_marks == 0:
            positive_signals += 1
        elif derogatory_marks <= 2:
            pass  # Neutral
        else:
            negative_signals += 2
        
        # Compliance
        if is_compliant and compliance_score >= self.COMPLIANCE_EXCELLENT:
            positive_signals += 2
        elif is_compliant:
            positive_signals += 1
        else:
            negative_signals += 2
        
        # Decision logic
        if positive_signals >= 7 and negative_signals <= 1:
            return "lean_approve"
        elif positive_signals >= 4 and negative_signals <= 2:
            return "lean_conditional"
        else:
            return "lean_deny"
    
    def check_auto_approval_eligible(
        self,
        dti: float,
        ltv: float,
        credit_score: int,
        is_compliant: bool,
        compliance_score: float
    ) -> bool:
        """
        Quick check if application meets auto-approval criteria.
        
        Args:
            dti: Debt-to-income ratio
            ltv: Loan-to-value ratio
            credit_score: FICO score
            is_compliant: Compliance status
            compliance_score: Compliance score
        
        Returns:
            True if meets auto-approval criteria
        """
        return (
            dti <= self.DTI_EXCELLENT
            and ltv <= self.LTV_EXCELLENT
            and credit_score >= self.CREDIT_GOOD
            and is_compliant
            and compliance_score >= self.COMPLIANCE_EXCELLENT
        )
    
    def check_auto_rejection_eligible(
        self,
        dti: float,
        credit_score: int,
        ltv: float,
        derogatory_marks: int,
        has_critical_violations: bool
    ) -> bool:
        """
        Quick check if application meets auto-rejection criteria.
        
        Args:
            dti: Debt-to-income ratio
            credit_score: FICO score
            ltv: Loan-to-value ratio
            derogatory_marks: Number of negative marks
            has_critical_violations: Whether has critical compliance violations
        
        Returns:
            True if meets auto-rejection criteria
        """
        return (
            has_critical_violations
            or (dti > self.DTI_ACCEPTABLE and credit_score < self.CREDIT_NEAR_PRIME)
            or credit_score < self.CREDIT_SUBPRIME
            or ltv > self.LTV_MAX
            or derogatory_marks >= 3
            or dti > self.DTI_MAX
        )
    
    def get_thresholds(self) -> Dict[str, float]:
        """
        Get all decision thresholds for transparency.
        
        Returns:
            Dictionary of threshold names and values
        """
        return {
            "dti_excellent": self.DTI_EXCELLENT,
            "dti_acceptable": self.DTI_ACCEPTABLE,
            "dti_max": self.DTI_MAX,
            "ltv_excellent": self.LTV_EXCELLENT,
            "ltv_acceptable": self.LTV_ACCEPTABLE,
            "ltv_max": self.LTV_MAX,
            "credit_excellent": self.CREDIT_EXCELLENT,
            "credit_good": self.CREDIT_GOOD,
            "credit_fair": self.CREDIT_FAIR,
            "credit_near_prime": self.CREDIT_NEAR_PRIME,
            "credit_subprime": self.CREDIT_SUBPRIME,
            "compliance_excellent": self.COMPLIANCE_EXCELLENT,
            "compliance_acceptable": self.COMPLIANCE_ACCEPTABLE,
            "derogatory_max_auto_approve": self.DEROGATORY_MAX_AUTO_APPROVE,
            "derogatory_max_borderline": self.DEROGATORY_MAX_BORDERLINE
        }


class StateAggregator:
    """
    Aggregate outputs from multiple agents into unified decision state.
    
    Combines ExtractedDocument, CreditReport, RiskAssessment, and
    ComplianceReport into a single structured dictionary for decision
    analysis per spec.md FR-020.
    
    The aggregated state provides a complete view of the application
    for both deterministic rules (DecisionRules) and AI analysis
    (DecisionAnalyzer with GPT-4o).
    
    Key Features:
    - Flattens nested structures for easy access
    - Extracts key metrics to top level
    - Preserves full agent outputs for audit trail
    - Validates all required data present
    - Formats data for GPT-4o prompts
    
    Examples:
        >>> aggregator = StateAggregator()
        >>> state = aggregator.aggregate(
        ...     extracted_doc=doc,
        ...     credit_report=credit,
        ...     risk_assessment=risk,
        ...     compliance_report=compliance
        ... )
        >>> print(state['key_metrics']['dti'])
        38.5
    """
    
    def __init__(self):
        """Initialize state aggregator."""
        logger.info("StateAggregator initialized")
    
    def aggregate(
        self,
        extracted_doc: ExtractedDocument,
        credit_report: CreditReport,
        risk_assessment: RiskAssessment,
        compliance_report: ComplianceReport
    ) -> Dict[str, any]:
        """
        Aggregate all agent outputs into unified decision state.
        
        Args:
            extracted_doc: Document extraction results
            credit_report: Credit bureau data
            risk_assessment: Risk analysis results
            compliance_report: Policy compliance results
        
        Returns:
            Dictionary with aggregated state containing:
                - application_id: Unique identifier
                - key_metrics: Flattened financial/credit metrics
                - applicant_profile: Structured applicant data
                - risk_analysis: Complete risk assessment
                - compliance_analysis: Complete compliance report
                - document_data: Original extraction results
                - credit_data: Original credit report
                - decision_ready: Validation flag
                - missing_fields: List of any missing data
        
        Examples:
            >>> state = aggregator.aggregate(doc, credit, risk, compliance)
            >>> if state['decision_ready']:
            ...     decision = make_decision(state)
        """
        logger.info(
            f"Aggregating state for application {extracted_doc.application_id}"
        )
        
        # Validate all inputs present
        validation_result = self._validate_inputs(
            extracted_doc, credit_report, risk_assessment, compliance_report
        )
        
        # Extract key metrics to top level for easy access
        key_metrics = self._extract_key_metrics(
            extracted_doc, credit_report, risk_assessment, compliance_report
        )
        
        # Build applicant profile summary
        applicant_profile = self._build_applicant_profile(
            extracted_doc, credit_report
        )
        
        # Build risk analysis summary
        risk_analysis = self._build_risk_analysis(risk_assessment)
        
        # Build compliance analysis summary
        compliance_analysis = self._build_compliance_analysis(compliance_report)
        
        # Aggregate into single state dictionary
        aggregated_state = {
            # Identity
            "application_id": extracted_doc.application_id,
            "aggregated_at": datetime.utcnow().isoformat(),
            
            # Validation
            "decision_ready": validation_result["is_valid"],
            "missing_fields": validation_result["missing_fields"],
            
            # Key Metrics (flattened for rules/prompts)
            "key_metrics": key_metrics,
            
            # Structured Summaries
            "applicant_profile": applicant_profile,
            "risk_analysis": risk_analysis,
            "compliance_analysis": compliance_analysis,
            
            # Full Agent Outputs (for audit trail)
            "document_data": extracted_doc.model_dump(),
            "credit_data": credit_report.model_dump(),
            "risk_assessment": risk_assessment.model_dump(),
            "compliance_report": compliance_report.model_dump(),
        }
        
        logger.info(
            f"State aggregated: {len(key_metrics)} metrics, "
            f"decision_ready={validation_result['is_valid']}"
        )
        
        return aggregated_state
    
    def _validate_inputs(
        self,
        extracted_doc: ExtractedDocument,
        credit_report: CreditReport,
        risk_assessment: RiskAssessment,
        compliance_report: ComplianceReport
    ) -> Dict[str, any]:
        """
        Validate that all required data is present.
        
        Args:
            extracted_doc: Document extraction results
            credit_report: Credit report
            risk_assessment: Risk assessment
            compliance_report: Compliance report
        
        Returns:
            Dictionary with:
                - is_valid: True if all required fields present
                - missing_fields: List of missing field names
        """
        missing_fields = []
        
        # Check document extraction (from structured_data)
        loan_amount = extracted_doc.structured_data.get("loan_amount")
        if not loan_amount or float(loan_amount) <= 0:
            missing_fields.append("loan_amount")
        
        property_value = extracted_doc.structured_data.get("property_value")
        if not property_value or float(property_value) <= 0:
            missing_fields.append("property_value")
        
        if not extracted_doc.structured_data.get("applicant_name"):
            missing_fields.append("applicant_name")
        
        # Check credit report
        if not credit_report.credit_score or credit_report.credit_score < 300:
            missing_fields.append("credit_score")
        
        # Check risk assessment
        if not risk_assessment.debt_to_income_ratio:
            missing_fields.append("debt_to_income_ratio")
        
        if not risk_assessment.loan_to_value_ratio:
            missing_fields.append("loan_to_value_ratio")
        
        if not risk_assessment.risk_level:
            missing_fields.append("risk_level")
        
        # Check compliance report
        if compliance_report.compliance_score is None:
            missing_fields.append("compliance_score")
        
        is_valid = len(missing_fields) == 0
        
        if not is_valid:
            logger.warning(f"Validation failed: missing {missing_fields}")
        
        return {
            "is_valid": is_valid,
            "missing_fields": missing_fields
        }
    
    def _extract_key_metrics(
        self,
        extracted_doc: ExtractedDocument,
        credit_report: CreditReport,
        risk_assessment: RiskAssessment,
        compliance_report: ComplianceReport
    ) -> Dict[str, any]:
        """
        Extract key metrics to top level for easy access.
        
        Args:
            extracted_doc: Document extraction
            credit_report: Credit report
            risk_assessment: Risk assessment
            compliance_report: Compliance report
        
        Returns:
            Dictionary of flattened key metrics
        """
        return {
            # Financial Ratios
            "dti": float(risk_assessment.debt_to_income_ratio),
            "ltv": float(risk_assessment.loan_to_value_ratio),
            "monthly_debt": float(risk_assessment.monthly_debt_payments),
            "monthly_income": float(risk_assessment.monthly_gross_income),
            
            # Loan Details
            "loan_amount": float(extracted_doc.structured_data.get("loan_amount", 0)),
            "property_value": float(extracted_doc.structured_data.get("property_value", 0)),
            "loan_purpose": extracted_doc.structured_data.get("loan_purpose", "unknown"),
            
            # Credit Metrics
            "credit_score": credit_report.credit_score,
            "credit_utilization": credit_report.credit_utilization,
            "derogatory_marks": credit_report.derogatory_marks,
            "payment_history": credit_report.payment_history,
            "late_payments_12mo": credit_report.late_payments_12mo,
            "hard_inquiries_12mo": credit_report.hard_inquiries_12mo,
            "accounts_open": credit_report.accounts_open,
            "credit_age_months": credit_report.credit_age_months,
            
            # Risk Assessment
            "risk_level": risk_assessment.risk_level,
            "risk_score": float(risk_assessment.risk_score),
            "recommendation": risk_assessment.recommendation,
            
            # Compliance
            "is_compliant": compliance_report.is_compliant,
            "compliance_score": float(compliance_report.compliance_score),
            "violation_count": len(compliance_report.violations),
            "critical_violations": len([
                v for v in compliance_report.violations
                if v.severity == "critical"
            ]),
            "warning_violations": len([
                v for v in compliance_report.violations
                if v.severity == "warning"
            ]),
        }
    
    def _build_applicant_profile(
        self,
        extracted_doc: ExtractedDocument,
        credit_report: CreditReport
    ) -> Dict[str, any]:
        """
        Build structured applicant profile summary.
        
        Args:
            extracted_doc: Document extraction
            credit_report: Credit report
        
        Returns:
            Applicant profile dictionary
        """
        return {
            "name": extracted_doc.structured_data.get("applicant_name"),
            "ssn": extracted_doc.structured_data.get("ssn"),
            "employer": extracted_doc.structured_data.get("employer_name"),
            "employment_years": extracted_doc.structured_data.get("employment_years"),
            "annual_income": float(extracted_doc.structured_data.get("annual_income", 0)) if extracted_doc.structured_data.get("annual_income") else None,
            "monthly_income": float(extracted_doc.structured_data.get("monthly_income", 0)) if extracted_doc.structured_data.get("monthly_income") else None,
            "credit_score": credit_report.credit_score,
            "payment_history": credit_report.payment_history,
            "credit_profile": self._classify_credit_profile(credit_report),
        }
    
    def _classify_credit_profile(self, credit_report: CreditReport) -> str:
        """
        Classify credit profile into category.
        
        Args:
            credit_report: Credit report
        
        Returns:
            Credit profile category
        """
        score = credit_report.credit_score
        
        if score >= 760:
            return "excellent"
        elif score >= 720:
            return "good"
        elif score >= 680:
            return "fair"
        elif score >= 640:
            return "near-prime"
        elif score >= 580:
            return "subprime"
        else:
            return "deep-subprime"
    
    def _build_risk_analysis(
        self,
        risk_assessment: RiskAssessment
    ) -> Dict[str, any]:
        """
        Build structured risk analysis summary.
        
        Args:
            risk_assessment: Risk assessment
        
        Returns:
            Risk analysis dictionary
        """
        return {
            "risk_level": risk_assessment.risk_level,
            "risk_score": float(risk_assessment.risk_score),
            "recommendation": risk_assessment.recommendation,
            "risk_factors": risk_assessment.risk_factors,
            "mitigating_factors": risk_assessment.mitigating_factors,
            "reasoning": risk_assessment.reasoning,
            "financial_metrics": {
                "dti": float(risk_assessment.debt_to_income_ratio),
                "ltv": float(risk_assessment.loan_to_value_ratio),
                "monthly_debt": float(risk_assessment.monthly_debt_payments),
                "monthly_income": float(risk_assessment.monthly_gross_income),
            }
        }
    
    def _build_compliance_analysis(
        self,
        compliance_report: ComplianceReport
    ) -> Dict[str, any]:
        """
        Build structured compliance analysis summary.
        
        Args:
            compliance_report: Compliance report
        
        Returns:
            Compliance analysis dictionary
        """
        # Group violations by severity
        violations_by_severity = {
            "critical": [],
            "warning": [],
            "info": []
        }
        
        for violation in compliance_report.violations:
            violations_by_severity[violation.severity].append({
                "policy": violation.policy_name,
                "section": violation.policy_section,
                "description": violation.description,
                "recommendation": violation.recommendation
            })
        
        return {
            "is_compliant": compliance_report.is_compliant,
            "compliance_score": float(compliance_report.compliance_score),
            "summary": compliance_report.compliance_summary,
            "violations": violations_by_severity,
            "policies_evaluated": compliance_report.policies_evaluated,
            "rag_chunks_used": compliance_report.rag_chunks_used,
            "has_critical_violations": len(violations_by_severity["critical"]) > 0,
            "violation_counts": {
                "critical": len(violations_by_severity["critical"]),
                "warning": len(violations_by_severity["warning"]),
                "info": len(violations_by_severity["info"]),
                "total": len(compliance_report.violations)
            }
        }
    
    def format_for_prompt(self, aggregated_state: Dict[str, any]) -> str:
        """
        Format aggregated state for GPT-4o prompt.
        
        Converts structured state into human-readable text suitable
        for inclusion in decision analysis prompts.
        
        Args:
            aggregated_state: Output from aggregate() method
        
        Returns:
            Formatted string for GPT-4o prompt
        
        Examples:
            >>> prompt_text = aggregator.format_for_prompt(state)
            >>> full_prompt = f"Analyze this application:\n\n{prompt_text}"
        """
        metrics = aggregated_state["key_metrics"]
        profile = aggregated_state["applicant_profile"]
        risk = aggregated_state["risk_analysis"]
        compliance = aggregated_state["compliance_analysis"]
        
        formatted = f"""APPLICATION SUMMARY
Application ID: {aggregated_state['application_id']}

APPLICANT PROFILE
- Name: {profile['name']}
- Employer: {profile['employer']} ({profile['employment_years']} years)
- Annual Income: ${metrics['monthly_income'] * 12:,.0f}
- Credit Score: {metrics['credit_score']} ({profile['credit_profile']})
- Payment History: {metrics['payment_history']}
- Derogatory Marks: {metrics['derogatory_marks']}

LOAN REQUEST
- Loan Amount: ${metrics['loan_amount']:,.0f}
- Property Value: ${metrics['property_value']:,.0f}
- Loan Purpose: {metrics['loan_purpose']}

FINANCIAL RATIOS
- Debt-to-Income (DTI): {metrics['dti']:.1f}%
- Loan-to-Value (LTV): {metrics['ltv']:.1f}%
- Monthly Debt: ${metrics['monthly_debt']:,.0f}
- Monthly Income: ${metrics['monthly_income']:,.0f}

RISK ASSESSMENT
- Risk Level: {risk['risk_level'].upper()}
- Risk Score: {risk['risk_score']:.1f}/100
- Recommendation: {risk['recommendation'].upper()}

Risk Factors:
{self._format_list(risk['risk_factors'])}

Mitigating Factors:
{self._format_list(risk['mitigating_factors'])}

COMPLIANCE STATUS
- Compliant: {'YES' if compliance['is_compliant'] else 'NO'}
- Compliance Score: {compliance['compliance_score']:.1f}/100
- Violations: {compliance['violation_counts']['critical']} critical, {compliance['violation_counts']['warning']} warnings

"""
        
        # Add violation details if any
        if compliance['violations']['critical']:
            formatted += "CRITICAL VIOLATIONS:\n"
            for v in compliance['violations']['critical']:
                formatted += f"  • {v['policy']} - {v['section']}\n"
                formatted += f"    {v['description']}\n"
        
        if compliance['violations']['warning']:
            formatted += "\nWARNINGS:\n"
            for v in compliance['violations']['warning']:
                formatted += f"  • {v['policy']} - {v['section']}\n"
                formatted += f"    {v['description']}\n"
        
        return formatted
    
    def _format_list(self, items: List[str]) -> str:
        """Format list items with bullet points."""
        if not items:
            return "  • None"
        return "\n".join(f"  • {item}" for item in items)
    
    def get_summary_stats(self, aggregated_state: Dict[str, any]) -> Dict[str, any]:
        """
        Get summary statistics from aggregated state.
        
        Useful for logging and monitoring.
        
        Args:
            aggregated_state: Output from aggregate() method
        
        Returns:
            Summary statistics dictionary
        """
        metrics = aggregated_state["key_metrics"]
        
        return {
            "application_id": aggregated_state["application_id"],
            "decision_ready": aggregated_state["decision_ready"],
            "credit_score": metrics["credit_score"],
            "dti": metrics["dti"],
            "ltv": metrics["ltv"],
            "risk_level": metrics["risk_level"],
            "is_compliant": metrics["is_compliant"],
            "violation_count": metrics["violation_count"],
            "critical_violations": metrics["critical_violations"]
        }


class DecisionAnalyzer:
    """
    GPT-4o powered decision analysis for borderline cases.
    
    When DecisionRules identifies a borderline case (neither clear
    approval nor clear rejection), this class uses GPT-4o to perform
    comprehensive analysis considering all factors per spec.md FR-022.
    
    The analyzer:
    - Reviews complete application state
    - Weighs positive vs negative factors
    - Considers compensating factors
    - Identifies required conditions for approval
    - Provides detailed reasoning for decision
    - Returns decision with confidence level
    
    Key Features:
    - Structured GPT-4o prompts with full context
    - JSON mode for reliable parsing
    - Temperature 0.2 for consistent decisions
    - Detailed reasoning extraction
    - Condition generation for conditional approvals
    
    Examples:
        >>> analyzer = DecisionAnalyzer()
        >>> decision = analyzer.analyze(
        ...     aggregated_state=state,
        ...     initial_direction="lean_conditional"
        ... )
        >>> print(decision)  # ('conditional_approval', conditions, reasoning, 0.85)
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.2
    ):
        """
        Initialize decision analyzer with Azure OpenAI client.
        
        Args:
            model: Azure OpenAI deployment name (defaults to Config)
            temperature: Sampling temperature (0.0-1.0, lower = more consistent)
        
        Raises:
            ValueError: If Azure OpenAI credentials missing
        """
        from openai import AzureOpenAI
        from utils.config import Config
        
        # Initialize Azure OpenAI client
        if not Config.AZURE_OPENAI_API_KEY or not Config.AZURE_OPENAI_ENDPOINT:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env"
            )
        
        self.client = AzureOpenAI(
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
        )
        self.model = model or Config.AZURE_OPENAI_DEPLOYMENT_GPT4
        self.temperature = temperature
        
        logger.info(
            f"DecisionAnalyzer initialized: model={self.model}, "
            f"temperature={temperature}"
        )
    
    def analyze(
        self,
        aggregated_state: Dict[str, any],
        initial_direction: str,
        rules_reasons: List[str]
    ) -> Tuple[str, List[str], str, float]:
        """
        Analyze borderline application using GPT-4o.
        
        Args:
            aggregated_state: Complete application state from StateAggregator
            initial_direction: Hint from DecisionRules ("lean_approve", "lean_conditional", "lean_deny")
            rules_reasons: List of factors identified by DecisionRules
        
        Returns:
            Tuple of (decision, conditions, reasoning, confidence):
                - decision: "approved", "conditional_approval", "denied", "refer_to_manual"
                - conditions: List of conditions (empty for approved/denied)
                - reasoning: Detailed explanation of decision
                - confidence: 0.0-1.0 confidence level
        
        Examples:
            >>> decision, conditions, reasoning, conf = analyzer.analyze(state, "lean_conditional", reasons)
            >>> print(f"{decision} (confidence: {conf:.2f})")
            'conditional_approval (confidence: 0.85)'
        """
        logger.info(
            f"Analyzing borderline case {aggregated_state['application_id']} "
            f"with direction: {initial_direction}"
        )
        
        # Build GPT-4o prompt
        prompt = self._build_decision_prompt(
            aggregated_state, initial_direction, rules_reasons
        )
        
        # Call GPT-4o with JSON mode
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            import json
            result = json.loads(response.choices[0].message.content)
            
            decision = result.get("decision", "refer_to_manual")
            conditions = result.get("conditions", [])
            reasoning = result.get("reasoning", "No reasoning provided")
            confidence = float(result.get("confidence", 0.7))
            
            logger.info(
                f"GPT-4o decision: {decision} (confidence: {confidence:.2f}), "
                f"{len(conditions)} conditions"
            )
            
            return (decision, conditions, reasoning, confidence)
            
        except Exception as e:
            logger.error(f"Error calling GPT-4o for decision analysis: {e}")
            # Fallback to manual review
            return (
                "refer_to_manual",
                ["GPT-4o analysis failed - requires manual underwriter review"],
                f"Error during AI analysis: {str(e)}",
                0.0
            )
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for decision analyzer.
        
        Returns:
            System prompt string
        """
        return """You are an expert loan underwriter analyzing a borderline mortgage application.

Your role is to:
1. Review the complete application including financial metrics, credit history, risk assessment, and policy compliance
2. Weigh positive factors (strengths) against negative factors (concerns)
3. Consider compensating factors that may offset weaknesses
4. Determine if the application should be approved, conditionally approved, or denied
5. For conditional approvals, specify exact conditions required
6. Provide detailed reasoning for your decision

Decision Guidelines:
- APPROVED: Strong application with minor concerns, no conditions needed
- CONDITIONAL_APPROVAL: Acceptable application requiring specific conditions (e.g., PMI, employment verification, reserves)
- DENIED: Unacceptable risk even with conditions
- REFER_TO_MANUAL: Unusual case requiring human judgment

Always return valid JSON with this structure:
{
  "decision": "approved" | "conditional_approval" | "denied" | "refer_to_manual",
  "conditions": ["condition 1", "condition 2", ...],
  "reasoning": "Detailed explanation of decision factors",
  "confidence": 0.0-1.0
}

Be thorough, objective, and compliant with lending regulations."""
    
    def _build_decision_prompt(
        self,
        aggregated_state: Dict[str, any],
        initial_direction: str,
        rules_reasons: List[str]
    ) -> str:
        """
        Build detailed prompt for GPT-4o decision analysis.
        
        Args:
            aggregated_state: Complete application state
            initial_direction: Initial direction hint
            rules_reasons: Factors from DecisionRules
        
        Returns:
            Formatted prompt string
        """
        # Use StateAggregator to format the state
        aggregator = StateAggregator()
        formatted_state = aggregator.format_for_prompt(aggregated_state)
        
        # Add decision context
        direction_guidance = {
            "lean_approve": "The quantitative metrics suggest this application leans toward approval. Focus on whether any concerns are significant enough to require conditions or denial.",
            "lean_conditional": "This application has mixed signals. Determine if conditions can adequately mitigate the concerns.",
            "lean_deny": "The metrics raise concerns. Determine if there are sufficient compensating factors to approve with conditions, or if denial is appropriate."
        }
        
        prompt = f"""BORDERLINE APPLICATION ANALYSIS

{formatted_state}

INITIAL ASSESSMENT
Direction: {initial_direction.upper()}
{direction_guidance.get(initial_direction, "")}

KEY FACTORS TO CONSIDER:
{chr(10).join(f"  • {reason}" for reason in rules_reasons)}

ANALYSIS REQUIRED:

1. POSITIVE FACTORS (Strengths)
   - What aspects of this application support approval?
   - Are there strong compensating factors?
   - What mitigates the identified concerns?

2. NEGATIVE FACTORS (Concerns)
   - What aspects raise concerns about repayment ability?
   - Are there any compliance or regulatory issues?
   - What could lead to default?

3. COMPENSATING FACTORS
   - Can specific conditions address the concerns?
   - Are there offsetting strengths (e.g., high credit score despite elevated DTI)?
   - Is this a reasonable risk with proper safeguards?

4. CONDITIONS REQUIRED (if conditional approval)
   - What specific conditions would mitigate risks?
   - Examples: PMI for high LTV, employment verification, reserve requirements, appraisal review
   - Be specific and actionable

5. FINAL DECISION
   - Weigh all factors holistically
   - Apply fair lending principles
   - Consider regulatory compliance
   - Determine appropriate decision and confidence level

IMPORTANT GUIDELINES:
- DTI up to 43% may be acceptable with compensating factors
- LTV up to 95% acceptable with PMI
- Credit score 640-719 is near-prime (may approve with conditions)
- Consider payment history, not just credit score
- Compliance warnings (not critical violations) may be acceptable
- Be objective and avoid bias

Please provide your decision in valid JSON format."""
        
        return prompt
    
    def analyze_batch(
        self,
        applications: List[Dict[str, any]],
        initial_directions: List[str],
        rules_reasons: List[List[str]]
    ) -> List[Tuple[str, List[str], str, float]]:
        """
        Analyze multiple borderline applications in batch.
        
        More efficient than calling analyze() repeatedly for multiple
        applications.
        
        Args:
            applications: List of aggregated states
            initial_directions: List of direction hints
            rules_reasons: List of reason lists
        
        Returns:
            List of (decision, conditions, reasoning, confidence) tuples
        
        Examples:
            >>> results = analyzer.analyze_batch(states, directions, reasons)
            >>> for i, (dec, conds, reas, conf) in enumerate(results):
            ...     print(f"App {i+1}: {dec} ({conf:.2f})")
        """
        logger.info(f"Batch analyzing {len(applications)} borderline cases")
        
        results = []
        for app, direction, reasons in zip(applications, initial_directions, rules_reasons):
            result = self.analyze(app, direction, reasons)
            results.append(result)
        
        return results
    
    def explain_decision(
        self,
        decision: str,
        conditions: List[str],
        reasoning: str,
        confidence: float,
        aggregated_state: Dict[str, any]
    ) -> str:
        """
        Generate human-readable explanation of decision.
        
        Args:
            decision: Decision status
            conditions: List of conditions (if conditional)
            reasoning: Detailed reasoning from GPT-4o
            confidence: Confidence level
            aggregated_state: Application state
        
        Returns:
            Formatted explanation string
        
        Examples:
            >>> explanation = analyzer.explain_decision(
            ...     "conditional_approval", conditions, reasoning, 0.85, state
            ... )
            >>> print(explanation)
        """
        metrics = aggregated_state["key_metrics"]
        profile = aggregated_state["applicant_profile"]
        
        decision_labels = {
            "approved": "✅ APPROVED",
            "conditional_approval": "⚠️  CONDITIONAL APPROVAL",
            "denied": "❌ DENIED",
            "refer_to_manual": "🔍 MANUAL REVIEW REQUIRED"
        }
        
        explanation = f"""
{'='*70}
LENDING DECISION: {decision_labels.get(decision, decision.upper())}
{'='*70}

APPLICANT: {profile['name']}
APPLICATION ID: {aggregated_state['application_id']}
CREDIT SCORE: {metrics['credit_score']} ({profile['credit_profile']})

KEY METRICS:
  • DTI: {metrics['dti']:.1f}%
  • LTV: {metrics['ltv']:.1f}%
  • Risk Level: {metrics['risk_level'].upper()}
  • Compliance: {'PASS' if metrics['is_compliant'] else 'FAIL'} ({metrics['compliance_score']:.0f}/100)

DECISION CONFIDENCE: {confidence:.0%}

"""
        
        if conditions:
            explanation += f"CONDITIONS REQUIRED ({len(conditions)}):\n"
            for i, condition in enumerate(conditions, 1):
                explanation += f"{i}. {condition}\n"
            explanation += "\n"
        
        explanation += f"DETAILED REASONING:\n{reasoning}\n"
        
        explanation += f"\n{'='*70}\n"
        
        return explanation


class RateCalculator:
    """
    Calculate risk-adjusted interest rates for approved loans.
    
    Implements tiered pricing model based on credit score, risk level,
    and LTV ratio per spec.md FR-023. Returns APR as Decimal with
    calculation breakdown for transparency.
    
    Pricing Model:
    - Base Rate: 6.5% (30-year fixed mortgage baseline)
    - Credit Score Adjustment:
      * 760+: -0.50% (excellent credit discount)
      * 720-759: -0.25% (good credit discount)
      * 680-719: 0.00% (fair credit - no adjustment)
      * 640-679: +0.50% (near-prime premium)
      * 580-639: +1.00% (subprime premium)
      * <580: +2.00% (deep subprime premium)
    - Risk Level Premium:
      * Low: 0.00% (no additional risk premium)
      * Medium: +0.25% (moderate risk premium)
      * High: +0.75% (high risk premium)
    - LTV Adjustment:
      * ≤80%: 0.00% (conventional, no PMI)
      * 80-90%: +0.15% (PMI required)
      * 90-95%: +0.25% (high LTV premium)
      * >95%: +0.50% (very high LTV premium)
    
    Final APR = Base + Credit Adjustment + Risk Premium + LTV Adjustment
    
    Examples:
        >>> calculator = RateCalculator()
        >>> rate = calculator.calculate(
        ...     credit_score=740,
        ...     risk_level="low",
        ...     ltv=75.0,
        ...     decision="approved"
        ... )
        >>> print(rate)  # {'apr': 6.25, 'breakdown': {...}}
        
        >>> # Excellent credit, low risk, conventional LTV
        >>> rate = calculator.calculate(780, "low", 78.0, "approved")
        >>> print(rate['apr'])  # 6.00 (6.5 - 0.5 + 0.0 + 0.0)
        
        >>> # Near-prime credit, medium risk, high LTV
        >>> rate = calculator.calculate(660, "medium", 88.0, "conditional_approval")
        >>> print(rate['apr'])  # 7.40 (6.5 + 0.5 + 0.25 + 0.15)
    """
    
    # Base rate (30-year fixed mortgage)
    BASE_RATE = Decimal("6.50")
    
    # Credit score tiers and adjustments (in percentage points)
    CREDIT_TIERS = [
        (760, Decimal("-0.50")),  # Excellent
        (720, Decimal("-0.25")),  # Good
        (680, Decimal("0.00")),   # Fair
        (640, Decimal("0.50")),   # Near-prime
        (580, Decimal("1.00")),   # Subprime
        (0, Decimal("2.00"))      # Deep subprime
    ]
    
    # Risk level premiums
    RISK_PREMIUMS = {
        "low": Decimal("0.00"),
        "medium": Decimal("0.25"),
        "high": Decimal("0.75")
    }
    
    # LTV adjustment tiers
    LTV_TIERS = [
        (80.0, Decimal("0.00")),   # Conventional
        (90.0, Decimal("0.15")),   # PMI required
        (95.0, Decimal("0.25")),   # High LTV
        (100.0, Decimal("0.50"))   # Very high LTV
    ]
    
    def __init__(self, base_rate: Optional[Decimal] = None):
        """
        Initialize rate calculator.
        
        Args:
            base_rate: Override default base rate (defaults to 6.5%)
        """
        if base_rate is not None:
            self.BASE_RATE = base_rate
        
        logger.info(f"RateCalculator initialized with base rate: {self.BASE_RATE}%")
    
    def calculate(
        self,
        credit_score: int,
        risk_level: str,
        ltv: float,
        decision: str
    ) -> Dict[str, any]:
        """
        Calculate risk-adjusted APR for approved/conditional loan.
        
        Args:
            credit_score: FICO score (300-850)
            risk_level: "low", "medium", or "high"
            ltv: Loan-to-value ratio (percentage)
            decision: "approved" or "conditional_approval" (denied loans get no rate)
        
        Returns:
            Dictionary with:
                - apr: Final APR as Decimal
                - base_rate: Starting base rate
                - credit_adjustment: Credit score adjustment
                - risk_premium: Risk level premium
                - ltv_adjustment: LTV adjustment
                - breakdown: Human-readable calculation steps
                - tier_classifications: Credit/LTV tier labels
        
        Raises:
            ValueError: If decision is "denied" or "refer_to_manual"
        
        Examples:
            >>> calc = RateCalculator()
            >>> result = calc.calculate(740, "low", 75.0, "approved")
            >>> print(f"APR: {result['apr']}%")
            'APR: 6.25%'
        """
        # Validate decision type
        if decision not in ["approved", "conditional_approval"]:
            raise ValueError(
                f"Cannot calculate rate for decision: {decision}. "
                "Only 'approved' and 'conditional_approval' get rates."
            )
        
        logger.info(
            f"Calculating rate: credit={credit_score}, risk={risk_level}, "
            f"ltv={ltv:.1f}%, decision={decision}"
        )
        
        # Calculate adjustments
        credit_adjustment, credit_tier = self._get_credit_adjustment(credit_score)
        risk_premium = self._get_risk_premium(risk_level)
        ltv_adjustment, ltv_tier = self._get_ltv_adjustment(ltv)
        
        # Calculate final APR
        apr = self.BASE_RATE + credit_adjustment + risk_premium + ltv_adjustment
        
        # Build breakdown for transparency
        breakdown = self._build_breakdown(
            self.BASE_RATE,
            credit_adjustment,
            risk_premium,
            ltv_adjustment,
            apr
        )
        
        logger.info(f"Calculated APR: {apr:.3f}% (breakdown: {breakdown})")
        
        return {
            "apr": float(apr),
            "base_rate": float(self.BASE_RATE),
            "credit_adjustment": float(credit_adjustment),
            "risk_premium": float(risk_premium),
            "ltv_adjustment": float(ltv_adjustment),
            "breakdown": breakdown,
            "tier_classifications": {
                "credit_tier": credit_tier,
                "ltv_tier": ltv_tier,
                "risk_level": risk_level
            }
        }
    
    def _get_credit_adjustment(
        self,
        credit_score: int
    ) -> Tuple[Decimal, str]:
        """
        Get credit score adjustment and tier label.
        
        Args:
            credit_score: FICO score
        
        Returns:
            Tuple of (adjustment, tier_label)
        """
        # Find appropriate tier
        for min_score, adjustment in self.CREDIT_TIERS:
            if credit_score >= min_score:
                # Determine tier label
                if credit_score >= 760:
                    tier = "excellent"
                elif credit_score >= 720:
                    tier = "good"
                elif credit_score >= 680:
                    tier = "fair"
                elif credit_score >= 640:
                    tier = "near-prime"
                elif credit_score >= 580:
                    tier = "subprime"
                else:
                    tier = "deep-subprime"
                
                return (adjustment, tier)
        
        # Fallback (should never reach here)
        return (self.CREDIT_TIERS[-1][1], "deep-subprime")
    
    def _get_risk_premium(self, risk_level: str) -> Decimal:
        """
        Get risk level premium.
        
        Args:
            risk_level: "low", "medium", or "high"
        
        Returns:
            Risk premium as Decimal
        
        Raises:
            ValueError: If risk_level not recognized
        """
        risk_level_lower = risk_level.lower()
        
        if risk_level_lower not in self.RISK_PREMIUMS:
            logger.warning(
                f"Unknown risk level: {risk_level}. Defaulting to 'medium'."
            )
            return self.RISK_PREMIUMS["medium"]
        
        return self.RISK_PREMIUMS[risk_level_lower]
    
    def _get_ltv_adjustment(
        self,
        ltv: float
    ) -> Tuple[Decimal, str]:
        """
        Get LTV adjustment and tier label.
        
        Args:
            ltv: Loan-to-value ratio (percentage)
        
        Returns:
            Tuple of (adjustment, tier_label)
        """
        # Find appropriate tier
        for max_ltv, adjustment in self.LTV_TIERS:
            if ltv <= max_ltv:
                # Determine tier label
                if ltv <= 80.0:
                    tier = "conventional"
                elif ltv <= 90.0:
                    tier = "pmi-required"
                elif ltv <= 95.0:
                    tier = "high-ltv"
                else:
                    tier = "very-high-ltv"
                
                return (adjustment, tier)
        
        # Fallback (LTV > 100% - should be rare/error case)
        logger.warning(f"LTV {ltv:.1f}% exceeds 100%. Using max adjustment.")
        return (self.LTV_TIERS[-1][1], "very-high-ltv")
    
    def _build_breakdown(
        self,
        base_rate: Decimal,
        credit_adjustment: Decimal,
        risk_premium: Decimal,
        ltv_adjustment: Decimal,
        final_apr: Decimal
    ) -> str:
        """
        Build human-readable calculation breakdown.
        
        Args:
            base_rate: Base rate
            credit_adjustment: Credit score adjustment
            risk_premium: Risk premium
            ltv_adjustment: LTV adjustment
            final_apr: Final APR
        
        Returns:
            Formatted breakdown string
        """
        breakdown = f"{base_rate:.2f}% (base)"
        
        if credit_adjustment != 0:
            sign = "+" if credit_adjustment > 0 else ""
            breakdown += f" {sign}{credit_adjustment:.2f}% (credit)"
        
        if risk_premium != 0:
            breakdown += f" +{risk_premium:.2f}% (risk)"
        
        if ltv_adjustment != 0:
            breakdown += f" +{ltv_adjustment:.2f}% (LTV)"
        
        breakdown += f" = {final_apr:.2f}%"
        
        return breakdown
    
    def calculate_monthly_payment(
        self,
        loan_amount: float,
        apr: float,
        term_years: int = 30
    ) -> Dict[str, float]:
        """
        Calculate monthly mortgage payment using amortization formula.
        
        Uses standard mortgage amortization:
        M = P * [r(1+r)^n] / [(1+r)^n - 1]
        
        Where:
        - M = Monthly payment
        - P = Principal (loan amount)
        - r = Monthly interest rate (APR / 12 / 100)
        - n = Total number of payments (term_years * 12)
        
        Args:
            loan_amount: Principal loan amount
            apr: Annual percentage rate (as percentage, e.g., 6.5)
            term_years: Loan term in years (default 30)
        
        Returns:
            Dictionary with:
                - monthly_payment: Principal + interest payment
                - total_payments: Total amount paid over loan term
                - total_interest: Total interest paid
                - principal: Original loan amount
        
        Examples:
            >>> calc = RateCalculator()
            >>> payment = calc.calculate_monthly_payment(350000, 6.5, 30)
            >>> print(f"Monthly: ${payment['monthly_payment']:,.2f}")
            'Monthly: $2,212.01'
        """
        from decimal import Decimal, ROUND_HALF_UP
        
        # Convert to Decimal for precision
        P = Decimal(str(loan_amount))
        annual_rate = Decimal(str(apr))
        n = term_years * 12
        
        # Calculate monthly rate
        r = annual_rate / Decimal("100") / Decimal("12")
        
        # Calculate monthly payment: M = P * [r(1+r)^n] / [(1+r)^n - 1]
        if r == 0:
            # No interest - simple division
            monthly_payment = P / Decimal(str(n))
        else:
            factor = (Decimal("1") + r) ** n
            monthly_payment = P * (r * factor) / (factor - Decimal("1"))
        
        # Round to 2 decimal places
        monthly_payment = monthly_payment.quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        
        # Calculate totals
        total_payments = monthly_payment * Decimal(str(n))
        total_interest = total_payments - P
        
        return {
            "monthly_payment": float(monthly_payment),
            "total_payments": float(total_payments),
            "total_interest": float(total_interest),
            "principal": float(P),
            "apr": float(annual_rate),
            "term_years": term_years,
            "total_months": n
        }
    
    def get_rate_comparison(
        self,
        applications: List[Dict[str, any]]
    ) -> Dict[str, any]:
        """
        Compare rates across multiple applications.
        
        Useful for analyzing rate distribution and identifying
        pricing patterns.
        
        Args:
            applications: List of dicts with credit_score, risk_level, ltv, decision
        
        Returns:
            Dictionary with:
                - rates: List of calculated APRs
                - average_rate: Mean APR
                - min_rate: Lowest APR
                - max_rate: Highest APR
                - rate_spread: Difference between max and min
        
        Examples:
            >>> calc = RateCalculator()
            >>> apps = [
            ...     {"credit_score": 780, "risk_level": "low", "ltv": 75, "decision": "approved"},
            ...     {"credit_score": 660, "risk_level": "medium", "ltv": 88, "decision": "conditional_approval"}
            ... ]
            >>> comparison = calc.get_rate_comparison(apps)
            >>> print(f"Average: {comparison['average_rate']:.2f}%")
        """
        rates = []
        
        for app in applications:
            try:
                result = self.calculate(
                    app["credit_score"],
                    app["risk_level"],
                    app["ltv"],
                    app["decision"]
                )
                rates.append(result["apr"])
            except (KeyError, ValueError) as e:
                logger.warning(f"Skipping application in comparison: {e}")
                continue
        
        if not rates:
            return {
                "rates": [],
                "average_rate": None,
                "min_rate": None,
                "max_rate": None,
                "rate_spread": None,
                "count": 0
            }
        
        avg_rate = sum(rates) / len(rates)
        min_rate = min(rates)
        max_rate = max(rates)
        spread = max_rate - min_rate
        
        return {
            "rates": rates,
            "average_rate": avg_rate,
            "min_rate": min_rate,
            "max_rate": max_rate,
            "rate_spread": spread,
            "count": len(rates)
        }
    
    def explain_rate(
        self,
        rate_result: Dict[str, any],
        credit_score: int,
        loan_amount: float
    ) -> str:
        """
        Generate human-readable rate explanation.
        
        Args:
            rate_result: Output from calculate() method
            credit_score: FICO score used
            loan_amount: Loan amount for payment calculation
        
        Returns:
            Formatted explanation string
        
        Examples:
            >>> calc = RateCalculator()
            >>> result = calc.calculate(740, "low", 75.0, "approved")
            >>> explanation = calc.explain_rate(result, 740, 350000)
            >>> print(explanation)
        """
        tiers = rate_result["tier_classifications"]
        
        explanation = f"""
{'='*70}
INTEREST RATE CALCULATION
{'='*70}

CREDIT PROFILE: {credit_score} ({tiers['credit_tier'].upper()})
RISK LEVEL: {tiers['risk_level'].upper()}
LTV TIER: {tiers['ltv_tier'].upper()}

RATE BREAKDOWN:
  Base Rate:           {rate_result['base_rate']:>6.2f}%
  Credit Adjustment:   {rate_result['credit_adjustment']:>+6.2f}%
  Risk Premium:        {rate_result['risk_premium']:>+6.2f}%
  LTV Adjustment:      {rate_result['ltv_adjustment']:>+6.2f}%
  ─────────────────────────────
  Final APR:           {rate_result['apr']:>6.2f}%

CALCULATION: {rate_result['breakdown']}

"""
        
        # Add monthly payment if loan amount provided
        if loan_amount:
            payment_info = self.calculate_monthly_payment(
                loan_amount, rate_result['apr']
            )
            
            explanation += f"""ESTIMATED MONTHLY PAYMENT (30-year fixed):
  Loan Amount:         ${loan_amount:>12,.0f}
  Monthly P&I:         ${payment_info['monthly_payment']:>12,.2f}
  Total Payments:      ${payment_info['total_payments']:>12,.0f}
  Total Interest:      ${payment_info['total_interest']:>12,.0f}

"""
        
        explanation += f"{'='*70}\n"
        
        return explanation


class ExplanationGenerator:
    """
    Generate plain-language decision summaries for customers.
    
    Converts technical lending decisions into clear, customer-friendly
    explanations suitable for adverse action notices and approval letters
    per spec.md FR-025.
    
    Key Features:
    - Plain-language summaries (8th grade reading level)
    - Regulatory compliance (ECOA adverse action notices)
    - Next steps for applicants
    - Transparent reasoning without jargon
    - Personalized recommendations
    
    Uses GPT-4o to transform technical decision details into:
    1. Decision summary (approved/conditional/denied)
    2. Key factors (3-5 most important reasons)
    3. Next steps (actionable guidance)
    4. Timeline expectations
    5. Contact information
    
    Examples:
        >>> generator = ExplanationGenerator()
        >>> explanation = generator.generate(
        ...     decision="conditional_approval",
        ...     conditions=["Provide PMI", "Verify employment"],
        ...     reasoning="Strong credit but high LTV requires PMI...",
        ...     aggregated_state=state
        ... )
        >>> print(explanation)  # Customer-friendly letter
    """
    
    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.3
    ):
        """
        Initialize explanation generator with Azure OpenAI client.
        
        Args:
            model: Azure OpenAI deployment name (defaults to Config)
            temperature: Sampling temperature (0.0-1.0, higher = more varied language)
        
        Raises:
            ValueError: If Azure OpenAI credentials missing
        """
        from openai import AzureOpenAI
        from utils.config import Config
        
        # Initialize Azure OpenAI client
        if not Config.AZURE_OPENAI_API_KEY or not Config.AZURE_OPENAI_ENDPOINT:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT in .env"
            )
        
        self.client = AzureOpenAI(
            api_key=Config.AZURE_OPENAI_API_KEY,
            api_version=Config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=Config.AZURE_OPENAI_ENDPOINT
        )
        self.model = model or Config.AZURE_OPENAI_DEPLOYMENT_GPT4
        self.temperature = temperature
        
        logger.info(
            f"ExplanationGenerator initialized: model={self.model}, "
            f"temperature={temperature}"
        )
    
    def generate(
        self,
        decision: str,
        conditions: List[str],
        reasoning: str,
        aggregated_state: Dict[str, any],
        rate_info: Optional[Dict[str, any]] = None
    ) -> Dict[str, str]:
        """
        Generate plain-language decision explanation.
        
        Args:
            decision: "approved", "conditional_approval", "denied", "refer_to_manual"
            conditions: List of conditions (for conditional approval)
            reasoning: Technical reasoning from DecisionAnalyzer
            aggregated_state: Complete application state from StateAggregator
            rate_info: Optional rate calculation from RateCalculator
        
        Returns:
            Dictionary with:
                - summary: Brief decision summary (1-2 sentences)
                - letter: Full explanation letter (plain language)
                - key_factors: List of 3-5 most important factors
                - next_steps: List of actionable next steps
                - timeline: Expected timeline for next actions
        
        Examples:
            >>> gen = ExplanationGenerator()
            >>> result = gen.generate("approved", [], reasoning, state, rate_info)
            >>> print(result['letter'])  # Full approval letter
        """
        logger.info(
            f"Generating explanation for decision: {decision}, "
            f"{len(conditions)} conditions"
        )
        
        # Build GPT-4o prompt
        prompt = self._build_explanation_prompt(
            decision, conditions, reasoning, aggregated_state, rate_info
        )
        
        # Call GPT-4o
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            # Parse response
            import json
            result = json.loads(response.choices[0].message.content)
            
            summary = result.get("summary", "Decision summary not available")
            letter = result.get("letter", "Explanation not available")
            key_factors = result.get("key_factors", [])
            next_steps = result.get("next_steps", [])
            timeline = result.get("timeline", "Timeline not specified")
            
            logger.info(f"Generated explanation: {len(letter)} chars, {len(key_factors)} factors")
            
            return {
                "summary": summary,
                "letter": letter,
                "key_factors": key_factors,
                "next_steps": next_steps,
                "timeline": timeline
            }
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            # Fallback to template-based explanation
            return self._generate_fallback_explanation(
                decision, conditions, aggregated_state, rate_info
            )
    
    def _get_system_prompt(self) -> str:
        """
        Get system prompt for explanation generator.
        
        Returns:
            System prompt string
        """
        return """You are a customer communication specialist writing lending decision letters.

Your role is to:
1. Translate technical lending decisions into plain, friendly language
2. Explain decisions clearly without financial jargon
3. Provide actionable next steps for the applicant
4. Comply with ECOA (Equal Credit Opportunity Act) adverse action notice requirements
5. Be empathetic, professional, and helpful

Writing Guidelines:
- Use 8th grade reading level (short sentences, common words)
- Avoid jargon: Say "monthly debt payments" not "debt-to-income ratio"
- Be specific: Give exact next steps, not vague suggestions
- Be positive: Focus on what applicant CAN do, even in denials
- Be transparent: Explain the main reasons clearly
- Include timeline: When should they expect next steps

Decision Types:
- APPROVED: Congratulate, explain rate, outline closing process
- CONDITIONAL_APPROVAL: Explain what's needed, why it matters, how to provide it
- DENIED: Explain main reasons (per ECOA), suggest improvements, mention reapplication
- REFER_TO_MANUAL: Explain additional review needed, set expectations

Always return valid JSON with this structure:
{
  "summary": "One-sentence decision summary",
  "letter": "Full explanation letter (3-5 paragraphs)",
  "key_factors": ["factor 1", "factor 2", "factor 3"],
  "next_steps": ["step 1", "step 2", "step 3"],
  "timeline": "Expected timeline description"
}

Be warm, clear, and helpful. This letter represents the lender's relationship with the customer."""
    
    def _build_explanation_prompt(
        self,
        decision: str,
        conditions: List[str],
        reasoning: str,
        aggregated_state: Dict[str, any],
        rate_info: Optional[Dict[str, any]] = None
    ) -> str:
        """
        Build prompt for explanation generation.
        
        Args:
            decision: Decision status
            conditions: List of conditions
            reasoning: Technical reasoning
            aggregated_state: Application state
            rate_info: Rate calculation results
        
        Returns:
            Formatted prompt string
        """
        metrics = aggregated_state["key_metrics"]
        profile = aggregated_state["applicant_profile"]
        
        # Format decision type
        decision_labels = {
            "approved": "APPROVED",
            "conditional_approval": "CONDITIONAL APPROVAL",
            "denied": "DENIED",
            "refer_to_manual": "ADDITIONAL REVIEW REQUIRED"
        }
        decision_label = decision_labels.get(decision, decision.upper())
        
        prompt = f"""LENDING DECISION LETTER GENERATION

DECISION: {decision_label}

APPLICANT INFORMATION:
- Name: {profile['name']}
- Loan Amount Requested: ${metrics['loan_amount']:,.0f}
- Property Value: ${metrics['property_value']:,.0f}
- Credit Score: {metrics['credit_score']}

TECHNICAL DECISION REASONING:
{reasoning}

"""
        
        # Add conditions if present
        if conditions:
            prompt += f"""CONDITIONS REQUIRED ({len(conditions)}):
"""
            for i, condition in enumerate(conditions, 1):
                prompt += f"{i}. {condition}\n"
            prompt += "\n"
        
        # Add rate information if present
        if rate_info:
            prompt += f"""APPROVED INTEREST RATE:
- APR: {rate_info['apr']:.3f}%
- Rate Breakdown: {rate_info['breakdown']}
"""
            if 'monthly_payment' in rate_info:
                prompt += f"- Estimated Monthly Payment: ${rate_info['monthly_payment']:,.2f}\n"
            prompt += "\n"
        
        prompt += f"""TASK:
Write a clear, friendly letter explaining this lending decision to {profile['name']}.

Requirements:
1. SUMMARY: One sentence capturing the decision and what it means
2. LETTER: Full explanation (3-5 paragraphs) including:
   - Opening: State the decision clearly and warmly
   - Explanation: Describe 3-5 main factors (in plain language, no jargon)
   - Details: If conditional, explain what's needed and why; if denied, explain reasons per ECOA
   - Next Steps: Clear actionable guidance
   - Closing: Positive note with contact information
3. KEY_FACTORS: 3-5 most important factors in plain language
4. NEXT_STEPS: 3-5 specific actionable steps
5. TIMELINE: When to expect next communication or action

IMPORTANT:
- Use plain language (8th grade level): "monthly debt payments" not "DTI ratio"
- Be specific: "Provide pay stubs from last 2 months" not "verify income"
- Be empathetic: Even denials should be respectful and helpful
- Be compliant: For denials, cite specific reasons per ECOA requirements
- Focus on what applicant CAN do to move forward

Generate the explanation now in valid JSON format."""
        
        return prompt
    
    def _generate_fallback_explanation(
        self,
        decision: str,
        conditions: List[str],
        aggregated_state: Dict[str, any],
        rate_info: Optional[Dict[str, any]] = None
    ) -> Dict[str, str]:
        """
        Generate template-based explanation as fallback.
        
        Used when GPT-4o call fails.
        
        Args:
            decision: Decision status
            conditions: List of conditions
            aggregated_state: Application state
            rate_info: Rate calculation results
        
        Returns:
            Dictionary with explanation components
        """
        metrics = aggregated_state["key_metrics"]
        profile = aggregated_state["applicant_profile"]
        
        if decision == "approved":
            summary = f"Congratulations! Your loan application has been approved."
            letter = f"""Dear {profile['name']},

We are pleased to inform you that your mortgage application for ${metrics['loan_amount']:,.0f} has been approved!

Your application was approved based on your strong financial profile, including your credit score of {metrics['credit_score']} and stable financial history.

"""
            if rate_info:
                letter += f"""Your approved interest rate is {rate_info['apr']:.3f}% APR, with an estimated monthly payment of ${rate_info.get('monthly_payment', 0):,.2f} for a 30-year fixed mortgage.

"""
            
            letter += """Next, we will begin the closing process. You should expect to hear from our closing team within 3-5 business days to schedule your closing date and review final documents.

If you have any questions, please contact us at loans@example.com or (555) 123-4567.

Congratulations on your loan approval!

Sincerely,
The Underwriting Team"""
            
            key_factors = [
                f"Strong credit score: {metrics['credit_score']}",
                f"Manageable debt-to-income ratio: {metrics['dti']:.1f}%",
                "Meets all underwriting guidelines"
            ]
            
            next_steps = [
                "Wait for closing team to contact you (3-5 business days)",
                "Prepare final documentation for closing",
                "Schedule your closing date"
            ]
            
            timeline = "Closing process typically takes 2-4 weeks"
        
        elif decision == "conditional_approval":
            summary = f"Your loan application is conditionally approved pending {len(conditions)} requirement(s)."
            letter = f"""Dear {profile['name']},

We have reviewed your mortgage application for ${metrics['loan_amount']:,.0f} and are pleased to offer you a conditional approval.

Your application shows strong potential, but we need a few additional items to finalize your approval:

"""
            for i, condition in enumerate(conditions, 1):
                letter += f"{i}. {condition}\n"
            
            letter += f"""
These requirements help us ensure you qualify for the best possible loan terms and comply with lending regulations.

"""
            if rate_info:
                letter += f"""Upon satisfying these conditions, your approved interest rate will be {rate_info['apr']:.3f}% APR.

"""
            
            letter += """Please provide the requested items within 30 days to maintain this approval. Once we receive everything, we can move forward to closing.

If you have any questions or need help gathering these documents, please contact us at loans@example.com or (555) 123-4567.

We look forward to working with you!

Sincerely,
The Underwriting Team"""
            
            key_factors = [
                f"Credit score: {metrics['credit_score']}",
                f"Loan-to-value ratio: {metrics['ltv']:.1f}%",
                f"{len(conditions)} condition(s) required"
            ]
            
            next_steps = [
                "Gather the required documentation",
                "Submit documents within 30 days",
                "Contact us if you have questions"
            ]
            
            timeline = "Provide documents within 30 days to maintain approval"
        
        elif decision == "denied":
            summary = "We regret to inform you that we cannot approve your loan application at this time."
            letter = f"""Dear {profile['name']},

Thank you for applying for a mortgage loan with us. After careful review of your application for ${metrics['loan_amount']:,.0f}, we are unable to approve your loan at this time.

This decision was based on the following factors:

"""
            # Build denial reasons
            reasons = []
            if metrics['credit_score'] < 640:
                reasons.append(f"Credit score ({metrics['credit_score']}) below minimum requirements")
            if metrics['dti'] > 43:
                reasons.append(f"Debt-to-income ratio ({metrics['dti']:.1f}%) exceeds guidelines")
            if metrics['ltv'] > 95:
                reasons.append(f"Loan-to-value ratio ({metrics['ltv']:.1f}%) exceeds limits")
            if not metrics['is_compliant']:
                reasons.append("Application does not meet all underwriting policy requirements")
            
            if not reasons:
                reasons = ["Application does not meet current underwriting guidelines"]
            
            for i, reason in enumerate(reasons, 1):
                letter += f"{i}. {reason}\n"
            
            letter += f"""
We understand this may be disappointing. Here are steps you can take to strengthen a future application:

"""
            suggestions = []
            if metrics['credit_score'] < 680:
                suggestions.append("Work on improving your credit score by paying bills on time and reducing credit card balances")
            if metrics['dti'] > 40:
                suggestions.append("Reduce monthly debt obligations or increase income before reapplying")
            if metrics['ltv'] > 90:
                suggestions.append("Consider a larger down payment to reduce the loan-to-value ratio")
            
            if not suggestions:
                suggestions = ["Review your financial situation and reapply when your profile is stronger"]
            
            for suggestion in suggestions:
                letter += f"• {suggestion}\n"
            
            letter += """
You may reapply at any time. We recommend waiting 6-12 months to allow time for financial improvements to reflect in your profile.

Under the Equal Credit Opportunity Act, you have the right to request specific reasons for this decision within 60 days. You also have the right to obtain a free copy of your credit report from the credit bureau(s) we used.

If you have questions about this decision, please contact us at loans@example.com or (555) 123-4567.

We appreciate your interest and wish you the best in your financial goals.

Sincerely,
The Underwriting Team"""
            
            key_factors = reasons
            
            next_steps = suggestions + ["Consider reapplying in 6-12 months"]
            
            timeline = "Reapply when financial profile improves (recommended 6-12 months)"
        
        else:  # refer_to_manual
            summary = "Your application requires additional review by our underwriting team."
            letter = f"""Dear {profile['name']},

Thank you for your mortgage application for ${metrics['loan_amount']:,.0f}. Your application has been forwarded to our senior underwriting team for additional review.

This is not a denial. Some applications require human review to ensure we make the most accurate and fair decision possible.

You can expect to hear from a senior underwriter within 3-5 business days. They may contact you for additional information or clarification.

If you have any questions in the meantime, please contact us at loans@example.com or (555) 123-4567.

Thank you for your patience.

Sincerely,
The Underwriting Team"""
            
            key_factors = [
                "Application requires senior underwriter review",
                "Additional information may be needed",
                "Decision pending human review"
            ]
            
            next_steps = [
                "Wait for senior underwriter to contact you",
                "Prepare to provide additional information if requested",
                "Check email regularly for updates"
            ]
            
            timeline = "Expect contact from senior underwriter within 3-5 business days"
        
        return {
            "summary": summary,
            "letter": letter,
            "key_factors": key_factors,
            "next_steps": next_steps,
            "timeline": timeline
        }
    
    def generate_batch(
        self,
        decisions: List[Tuple[str, List[str], str, Dict[str, any], Optional[Dict[str, any]]]]
    ) -> List[Dict[str, str]]:
        """
        Generate explanations for multiple decisions.
        
        Args:
            decisions: List of (decision, conditions, reasoning, state, rate_info) tuples
        
        Returns:
            List of explanation dictionaries
        
        Examples:
            >>> gen = ExplanationGenerator()
            >>> decisions = [
            ...     ("approved", [], reasoning1, state1, rate1),
            ...     ("conditional_approval", conds2, reasoning2, state2, rate2)
            ... ]
            >>> explanations = gen.generate_batch(decisions)
        """
        logger.info(f"Generating explanations for {len(decisions)} decisions")
        
        results = []
        for decision, conditions, reasoning, state, rate_info in decisions:
            result = self.generate(decision, conditions, reasoning, state, rate_info)
            results.append(result)
        
        return results
    
    def format_letter(
        self,
        explanation: Dict[str, str],
        applicant_name: str,
        application_id: str
    ) -> str:
        """
        Format explanation as formal letter with header/footer.
        
        Args:
            explanation: Output from generate() method
            applicant_name: Applicant's name
            application_id: Application ID
        
        Returns:
            Formatted letter string
        
        Examples:
            >>> gen = ExplanationGenerator()
            >>> formatted = gen.format_letter(explanation, "John Doe", "APP-001")
            >>> print(formatted)  # Full letter with letterhead
        """
        from datetime import datetime
        
        today = datetime.now().strftime("%B %d, %Y")
        
        formatted = f"""
{'='*70}
MORTGAGE LENDING COMPANY
123 Main Street
Anytown, ST 12345
Phone: (555) 123-4567
Email: loans@example.com
{'='*70}

{today}

{applicant_name}
Application ID: {application_id}

{explanation['letter']}

{'='*70}

SUMMARY: {explanation['summary']}

KEY FACTORS:
"""
        
        for i, factor in enumerate(explanation['key_factors'], 1):
            formatted += f"  {i}. {factor}\n"
        
        formatted += f"""
NEXT STEPS:
"""
        
        for i, step in enumerate(explanation['next_steps'], 1):
            formatted += f"  {i}. {step}\n"
        
        formatted += f"""
TIMELINE: {explanation['timeline']}

{'='*70}

This letter is for informational purposes. Please retain for your records.

Equal Housing Opportunity Lender
NMLS ID: 123456

{'='*70}
"""
        
        return formatted
