"""
AI Agents Module

This module contains the intelligent agents for loan underwriting:
- DocumentAgent: Extract structured data from loan documents using Azure Document Intelligence
- RiskAgent: Analyze financial risk and calculate lending metrics (DTI, LTV, PTI)
- ComplianceAgent: Check policy compliance using RAG-powered semantic search
- DecisionAgent: Make final lending decisions with transparent reasoning

Task: T017 - Create agents package marker
Phase: 3 (User Story 1 - Document Processing & Extraction)

Note: DocumentType enum moved to src.models for better reusability
"""

from .document_agent import (
    DocumentIntelligenceExtractor,
    FieldNormalizer,
    DataValidator,
    CompletenessCalculator,
    CostTracker
)

__all__ = [
    'DocumentIntelligenceExtractor',
    'FieldNormalizer',
    'DataValidator',
    'CompletenessCalculator',
    'CostTracker',
]

