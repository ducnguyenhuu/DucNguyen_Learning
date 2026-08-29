"""
Rule-Based Validation Engine

This module implements a configurable rule engine that reads validation rules
from YAML configuration and applies them dynamically.

Benefits:
- Add new rules without modifying Python code
- Non-technical users can configure rules
- Easy to test and audit rule changes
- Version control for rule changes
- Support for multiple rule types (comparison, range, format, calculation)

Usage:
    engine = ValidationRuleEngine("src/validation_rules.yaml")
    is_valid, errors = engine.validate(data, DocumentType.PAY_STUB)
"""

import logging
import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class RuleSeverity(Enum):
    """Validation rule severity levels"""
    CRITICAL = "critical"  # Must pass for document to be valid
    WARNING = "warning"    # Should pass but doesn't block processing
    INFO = "info"          # Informational only


class ValidationRule:
    """Base class for validation rules"""
    
    def __init__(self, config: Dict[str, Any]):
        self.rule_id = config.get("rule_id", "UNKNOWN")
        self.name = config.get("name", "")
        self.type = config.get("type", "")
        self.error_message = config.get("error_message", "Validation failed")
        self.severity = RuleSeverity(config.get("severity", "critical"))
        self.optional = config.get("optional", False)
        self.config = config
    
    def validate(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Validate data against this rule.
        
        Args:
            data: Normalized document data
            
        Returns:
            Error message if validation fails, None if passes
        """
        raise NotImplementedError("Subclasses must implement validate()")
    
    def format_error(self, **kwargs) -> str:
        """Format error message with field values"""
        return self.error_message.format(**kwargs)


class ComparisonRule(ValidationRule):
    """Compare two fields (e.g., net <= gross)"""
    
    OPERATORS = {
        "<=": lambda a, b: a <= b,
        "<": lambda a, b: a < b,
        ">=": lambda a, b: a >= b,
        ">": lambda a, b: a > b,
        "==": lambda a, b: a == b,
        "!=": lambda a, b: a != b,
    }
    
    def validate(self, data: Dict[str, Any]) -> Optional[str]:
        field1 = self.config.get("field1")
        field2 = self.config.get("field2")
        operator = self.config.get("operator")
        
        val1 = data.get(field1)
        val2 = data.get(field2)
        
        # Skip if fields missing and rule is optional
        if self.optional and (val1 is None or val2 is None):
            return None
        
        # Skip if fields missing (let required field validation handle it)
        if val1 is None or val2 is None:
            return None
        
        try:
            val1_num = float(val1)
            val2_num = float(val2)
            
            op_func = self.OPERATORS.get(operator)
            if not op_func:
                logger.error(f"Unknown operator: {operator}")
                return None
            
            if not op_func(val1_num, val2_num):
                return self.format_error(
                    field1=val1_num,
                    field2=val2_num
                )
            
        except (ValueError, TypeError):
            logger.warning(f"Could not compare {field1}={val1} and {field2}={val2}")
            return None
        
        return None


class RangeRule(ValidationRule):
    """Check value is within range"""
    
    def validate(self, data: Dict[str, Any]) -> Optional[str]:
        fields = self.config.get("fields", [])
        min_value = self.config.get("min_value")
        max_value = self.config.get("max_value")
        
        errors = []
        
        for field in fields:
            value = data.get(field)
            
            # Skip if missing and optional
            if self.optional and value is None:
                continue
            
            if value is None:
                continue
            
            try:
                val_num = float(value)
                
                if min_value is not None and val_num < min_value:
                    errors.append(self.format_error(field=field, value=val_num))
                
                if max_value is not None and val_num > max_value:
                    errors.append(self.format_error(field=field, value=val_num))
                    
            except (ValueError, TypeError):
                logger.warning(f"Could not check range for {field}={value}")
                continue
        
        return errors[0] if errors else None


class DateOrderRule(ValidationRule):
    """Check dates are chronological"""
    
    SPECIAL_DATES = {
        "TODAY": lambda: datetime.now(),
        "ONE_YEAR_AGO": lambda: datetime.now() - timedelta(days=365),
        "ONE_YEAR_FROM_NOW": lambda: datetime.now() + timedelta(days=365),
    }
    
    def validate(self, data: Dict[str, Any]) -> Optional[str]:
        start_field = self.config.get("start_field")
        end_field = self.config.get("end_field")
        
        # Handle special date keywords
        if end_field in self.SPECIAL_DATES:
            end_date = self.SPECIAL_DATES[end_field]()
        else:
            end_value = data.get(end_field)
            if end_value is None:
                return None if self.optional else None
            end_date = self._parse_date(end_value)
        
        start_value = data.get(start_field)
        if start_value is None:
            return None if self.optional else None
        
        start_date = self._parse_date(start_value)
        
        if start_date is None or end_date is None:
            return None
        
        if start_date >= end_date:
            return self.format_error(
                start_field=start_date.date(),
                end_field=end_date.date() if not isinstance(end_date, str) else end_field
            )
        
        return None
    
    def _parse_date(self, value: Any) -> Optional[datetime]:
        """Parse date from string or datetime"""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None


class FormatRule(ValidationRule):
    """Validate format using regex patterns"""
    
    def validate(self, data: Dict[str, Any]) -> Optional[str]:
        field = self.config.get("field")
        patterns = self.config.get("patterns", [self.config.get("pattern")])
        negate = self.config.get("negate", False)
        case_insensitive = self.config.get("case_insensitive", False)
        
        # If specific field, validate that field
        if field:
            value = data.get(field)
            if value is None:
                return None if self.optional else None
            
            return self._validate_value(str(value), patterns, negate, case_insensitive, field)
        
        # Otherwise validate all string fields
        errors = []
        for key, value in data.items():
            if isinstance(value, str):
                error = self._validate_value(value, patterns, negate, case_insensitive, key)
                if error:
                    errors.append(error)
        
        return errors[0] if errors else None
    
    def _validate_value(
        self, 
        value: str, 
        patterns: List[str], 
        negate: bool,
        case_insensitive: bool,
        field_name: str
    ) -> Optional[str]:
        """Validate a single value against patterns"""
        flags = re.IGNORECASE if case_insensitive else 0
        
        matches = False
        for pattern in patterns:
            if pattern and re.match(pattern, value, flags):
                matches = True
                break
        
        # If negate=True, we want NO matches (pattern should NOT occur)
        # If negate=False, we want at least one match (pattern SHOULD occur)
        validation_failed = matches if negate else not matches
        
        if validation_failed:
            return self.format_error(field=field_name, value=value)
        
        return None


class CalculationRule(ValidationRule):
    """Verify calculations are correct"""
    
    def validate(self, data: Dict[str, Any]) -> Optional[str]:
        formula = self.config.get("formula", "")
        tolerance = self.config.get("tolerance", 0.01)
        fields = self.config.get("fields", {})
        
        # Check all required fields are present
        for field, requirement in fields.items():
            if requirement == "required" and data.get(field) is None:
                return None if self.optional else None
        
        # Handle specific calculation types
        if "ytd_gross ~= gross_monthly_income * months_worked" in formula:
            return self._validate_ytd_calculation(data, tolerance)
        
        elif "ending_balance = beginning_balance + total_deposits - total_withdrawals" in formula:
            return self._validate_balance_equation(data, tolerance)
        
        elif "wages_monthly = wages_annual / 12" in formula:
            return self._validate_monthly_calculation(
                data, 
                "wages_annual", 
                "wages_monthly", 
                tolerance
            )
        
        elif "monthly_salary = annual_salary / 12" in formula:
            return self._validate_monthly_calculation(
                data,
                "annual_salary",
                "monthly_salary",
                tolerance
            )
        
        return None
    
    def _validate_ytd_calculation(self, data: Dict[str, Any], tolerance: float) -> Optional[str]:
        """Validate YTD gross consistency"""
        ytd_gross = data.get("ytd_gross")
        monthly_gross = data.get("gross_monthly_income")
        end_date = data.get("pay_period_end")
        
        if not all([ytd_gross, monthly_gross, end_date]):
            return None
        
        try:
            ytd_val = float(ytd_gross)
            monthly_val = float(monthly_gross)
            
            if isinstance(end_date, str):
                end = datetime.fromisoformat(end_date)
                months_worked = end.month
                
                expected_ytd = monthly_val * months_worked
                tolerance_amount = expected_ytd * tolerance
                
                if abs(ytd_val - expected_ytd) > tolerance_amount:
                    return self.format_error(
                        ytd_gross=ytd_val,
                        gross_monthly_income=monthly_val,
                        months_worked=months_worked
                    )
        except (ValueError, TypeError, AttributeError):
            return None
        
        return None
    
    def _validate_balance_equation(self, data: Dict[str, Any], tolerance: float) -> Optional[str]:
        """Validate bank statement balance equation"""
        beginning = data.get("beginning_balance")
        deposits = data.get("total_deposits")
        withdrawals = data.get("total_withdrawals")
        ending = data.get("ending_balance")
        
        if not all(x is not None for x in [beginning, deposits, withdrawals, ending]):
            return None
        
        try:
            beg_val = float(beginning)
            dep_val = float(deposits)
            with_val = float(withdrawals)
            end_val = float(ending)
            
            calculated_ending = beg_val + dep_val - with_val
            
            if abs(end_val - calculated_ending) > tolerance:
                return self.format_error(
                    ending_balance=end_val,
                    beginning_balance=beg_val,
                    total_deposits=dep_val,
                    total_withdrawals=with_val
                )
        except (ValueError, TypeError):
            return None
        
        return None
    
    def _validate_monthly_calculation(
        self, 
        data: Dict[str, Any], 
        annual_field: str,
        monthly_field: str,
        tolerance: float
    ) -> Optional[str]:
        """Validate annual to monthly calculation"""
        annual = data.get(annual_field)
        monthly = data.get(monthly_field)
        
        if annual is None or monthly is None:
            return None
        
        try:
            annual_val = float(annual)
            monthly_val = float(monthly)
            expected_monthly = annual_val / 12
            
            if abs(monthly_val - expected_monthly) > tolerance:
                return self.format_error(**{
                    monthly_field: monthly_val,
                    annual_field: annual_val
                })
        except (ValueError, TypeError):
            return None
        
        return None


class ValidationRuleEngine:
    """
    Rule-based validation engine that reads rules from YAML config.
    
    This engine dynamically loads and executes validation rules without
    requiring code changes. Perfect for business users to configure rules.
    """
    
    RULE_TYPES = {
        "comparison": ComparisonRule,
        "range": RangeRule,
        "date_order": DateOrderRule,
        "format": FormatRule,
        "calculation": CalculationRule,
    }
    
    def __init__(self, rules_file: str = "src/validation_rules.yaml"):
        """
        Initialize rule engine with configuration file.
        
        Args:
            rules_file: Path to YAML rules configuration
        """
        self.rules_file = Path(rules_file)
        self.rules_config = self._load_rules()
        self.execution_config = self.rules_config.get("execution", {})
        
        logger.info(f"ValidationRuleEngine initialized with {self.rules_file}")
    
    def _load_rules(self) -> Dict[str, Any]:
        """Load rules from YAML file"""
        if not self.rules_file.exists():
            logger.error(f"Rules file not found: {self.rules_file}")
            return {}
        
        with open(self.rules_file, 'r') as f:
            config = yaml.safe_load(f)
        
        logger.info(f"Loaded validation rules from {self.rules_file}")
        return config
    
    def validate(
        self,
        normalized_data: Dict[str, Any],
        document_type: Any  # Can be DocumentType enum or string
    ) -> Tuple[bool, List[str]]:
        """
        Validate document data using configured rules.
        
        Args:
            normalized_data: Normalized document data
            document_type: Type of document (DocumentType enum or string value)
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        # Handle both DocumentType enum and string
        if hasattr(document_type, 'value'):
            doc_type_key = document_type.value
        else:
            doc_type_key = str(document_type)
        
        # Get rules for this document type
        doc_rules = self.rules_config.get(doc_type_key, {}).get("rules", [])
        common_rules = self.rules_config.get("common", {}).get("rules", [])
        
        all_rules = doc_rules + common_rules
        
        errors = []
        critical_errors = []
        warnings = []
        
        max_errors = self.execution_config.get("max_errors_per_document", 20)
        stop_on_critical = self.execution_config.get("stop_on_first_critical", False)
        
        for rule_config in all_rules:
            # Check if we've hit error limit
            if len(errors) >= max_errors:
                errors.append(f"... and more errors (limit: {max_errors})")
                break
            
            # Stop if critical error found and configured to do so
            if stop_on_critical and critical_errors:
                break
            
            # Create rule instance
            rule = self._create_rule(rule_config)
            if not rule:
                continue
            
            # Execute validation
            error = rule.validate(normalized_data)
            
            if error:
                if rule.severity == RuleSeverity.CRITICAL:
                    critical_errors.append(f"[{rule.rule_id}] {error}")
                elif rule.severity == RuleSeverity.WARNING:
                    warnings.append(f"[{rule.rule_id}] {error}")
                else:  # INFO
                    errors.append(f"[{rule.rule_id}] {error}")
        
        # Combine errors
        skip_warnings = self.execution_config.get("skip_warnings_if_critical", False)
        
        all_errors = critical_errors
        if not (skip_warnings and critical_errors):
            all_errors.extend(warnings)
        
        is_valid = len(critical_errors) == 0
        
        if is_valid:
            logger.info(f"Validation passed for {document_type.value}")
        else:
            logger.warning(
                f"Validation failed for {document_type.value}: "
                f"{len(critical_errors)} critical, {len(warnings)} warnings"
            )
        
        return is_valid, all_errors
    
    def _create_rule(self, config: Dict[str, Any]) -> Optional[ValidationRule]:
        """Create rule instance from configuration"""
        rule_type = config.get("type")
        rule_class = self.RULE_TYPES.get(rule_type)
        
        if not rule_class:
            logger.warning(f"Unknown rule type: {rule_type}")
            return None
        
        try:
            return rule_class(config)
        except Exception as e:
            logger.error(f"Failed to create rule {config.get('rule_id')}: {e}")
            return None
    
    def reload_rules(self):
        """Reload rules from file (useful for hot-reloading in production)"""
        self.rules_config = self._load_rules()
        logger.info("Rules reloaded")
