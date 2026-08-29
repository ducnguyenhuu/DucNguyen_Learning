"""
Compliance Agent - RAG-powered policy compliance checking.

This module implements the ComplianceAgent that uses PolicyRetriever
to ground GPT-4o responses in actual lending policies, preventing
hallucination and ensuring compliance checks cite real policy sections.

Key Components:
- ComplianceAgent: Main agent integrating RAG retrieval + GPT-4o
- CitationExtractor: Parses GPT-4o responses for policy references
- ComplianceChecker: Validates against retrieved policy context

Based on spec.md FR-018: System MUST acknowledge when no relevant
policy found and avoid hallucinating policy requirements.
"""

import logging
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from openai import AzureOpenAI

from models import ComplianceReport, PolicyViolation, RiskAssessment
from rag.retriever import PolicyRetriever
from utils.config import Config

logger = logging.getLogger(__name__)


class CitationExtractor:
    """
    Extract policy citations from GPT-4o compliance responses.
    
    Parses structured responses to identify which policy sections
    were referenced in the compliance decision.
    
    Examples:
        >>> extractor = CitationExtractor()
        >>> text = "According to Underwriting Standards Policy Section 3.2..."
        >>> citations = extractor.extract_citations(text)
        >>> print(citations[0]['policy_name'])
        'Underwriting Standards Policy'
    """
    
    def __init__(self):
        """Initialize citation extractor with regex patterns."""
        # Pattern to match policy references
        self.policy_pattern = re.compile(
            r'(?:According to|Per|As stated in|Reference:|Policy:)\s+([^,\.;]+(?:Policy|Guidelines?|Requirements?|Standards?))',
            re.IGNORECASE
        )
        
        # Pattern to match section references
        self.section_pattern = re.compile(
            r'Section\s+(\d+\.?\d*\.?\d*)\s*:?\s*([^,\.;]+)',
            re.IGNORECASE
        )
        
        logger.info("CitationExtractor initialized")
    
    def extract_citations(
        self,
        text: str,
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, str]]:
        """
        Extract policy citations from compliance analysis text.
        
        Args:
            text: GPT-4o response text
            retrieved_chunks: Optional list of chunks from RAG retrieval
        
        Returns:
            List of citation dictionaries with policy_name, section, excerpt
        
        Examples:
            >>> extractor = CitationExtractor()
            >>> text = '''
            ... Per Underwriting Standards Policy Section 3.2,
            ... the maximum DTI is 36%. According to Credit Requirements
            ... Policy, minimum credit score is 620.
            ... '''
            >>> citations = extractor.extract_citations(text)
            >>> len(citations)
            2
        """
        citations = []
        
        # Extract policy names
        policy_matches = self.policy_pattern.findall(text)
        logger.debug(f"Found {len(policy_matches)} policy references")
        
        # Extract sections
        section_matches = self.section_pattern.findall(text)
        logger.debug(f"Found {len(section_matches)} section references")
        
        # Combine policy + section references
        for policy_name in set(policy_matches):
            citation = {
                "policy": policy_name.strip(),
                "excerpt": ""
            }
            
            # Try to find matching chunk
            if retrieved_chunks:
                for chunk in retrieved_chunks:
                    if policy_name.lower() in chunk.get('doc_title', '').lower():
                        citation["excerpt"] = chunk.get('content', '')[:200] + "..."
                        break
            
            citations.append(citation)
        
        # Add standalone section references
        for section_num, section_title in section_matches:
            if not any(section_num in c.get("policy", "") for c in citations):
                citation = {
                    "policy": f"Section {section_num}: {section_title.strip()}",
                    "excerpt": ""
                }
                citations.append(citation)
        
        logger.info(f"Extracted {len(citations)} unique citations")
        return citations
    
    def match_chunks_to_policies(
        self,
        retrieved_chunks: List[Dict[str, Any]]
    ) -> List[str]:
        """
        Extract unique policy document names from retrieved chunks.
        
        Args:
            retrieved_chunks: List of chunks from PolicyRetriever
        
        Returns:
            List of unique policy document titles
        """
        policies = set()
        
        for chunk in retrieved_chunks:
            doc_title = chunk.get('doc_title', '')
            if doc_title:
                policies.add(doc_title)
        
        return sorted(list(policies))


class ComplianceAgent:
    """
    Check loan application compliance against lending policies using RAG.
    
    This agent:
    1. Receives application data (risk assessment, extracted documents)
    2. Generates compliance queries
    3. Retrieves relevant policy chunks via PolicyRetriever
    4. Prompts GPT-4o with policy context
    5. Returns structured ComplianceReport
    
    Key Features:
    - RAG-grounded responses (no hallucination)
    - Policy citation extraction
    - Severity classification (critical/warning/info)
    - Handles no-result scenarios gracefully
    
    Examples:
        >>> agent = ComplianceAgent()
        >>> risk_assessment = RiskAssessment(...)
        >>> report = agent.check_compliance(
        ...     application_id="APP-001",
        ...     risk_assessment=risk_assessment
        ... )
        >>> print(report.is_compliant)
        True
    """
    
    def __init__(
        self,
        retriever: Optional[PolicyRetriever] = None,
        model: Optional[str] = None,
        temperature: float = 0.1
    ):
        """
        Initialize ComplianceAgent with RAG retriever and GPT-4 client.
        
        Args:
            retriever: PolicyRetriever instance (creates default if None)
            model: Azure OpenAI model deployment name (defaults to Config.AZURE_OPENAI_DEPLOYMENT_GPT4)
            temperature: Sampling temperature (0.0-1.0, lower = more deterministic)
        
        Raises:
            ValueError: If Azure OpenAI credentials missing
        """
        # Initialize PolicyRetriever
        if retriever is None:
            self.retriever = PolicyRetriever(top_k=5, min_similarity=0.01)
            logger.info("Created default PolicyRetriever")
        else:
            self.retriever = retriever
        
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
        
        # Initialize citation extractor
        self.citation_extractor = CitationExtractor()
        
        logger.info(
            f"ComplianceAgent initialized: model={model}, "
            f"temperature={temperature}"
        )
    
    def _generate_compliance_queries(
        self,
        risk_assessment: RiskAssessment
    ) -> List[str]:
        """
        Generate targeted policy queries based on risk assessment.
        
        Args:
            risk_assessment: RiskAssessment with calculated metrics
        
        Returns:
            List of natural language queries for policy retrieval
        """
        queries = []
        
        # DTI query
        dti = risk_assessment.debt_to_income_ratio
        queries.append(f"What is the maximum debt-to-income ratio allowed? DTI of {dti:.1f}%")
        
        # Credit score query (if available in risk assessment)
        # Note: credit_score is not in RiskAssessment model, skip this query
        
        # LTV query
        ltv = risk_assessment.loan_to_value_ratio
        queries.append(f"What is the maximum loan-to-value ratio allowed? LTV of {ltv:.1f}%")
        
        # Risk level query
        risk_level = risk_assessment.risk_level
        queries.append(f"What are the requirements for {risk_level} risk applications?")
        
        # Income and debt query
        monthly_income = risk_assessment.monthly_gross_income
        monthly_debt = risk_assessment.monthly_debt_payments
        queries.append(f"What are income verification and debt payment requirements for ${monthly_income:,.0f} monthly income with ${monthly_debt:,.0f} debt payments?")
        
        # General compliance query
        queries.append("What are the general underwriting standards and approval criteria?")
        
        logger.info(f"Generated {len(queries)} compliance queries")
        return queries
    
    def _retrieve_policy_context(
        self,
        queries: List[str]
    ) -> tuple[List[Dict[str, Any]], str]:
        """
        Retrieve relevant policy chunks for multiple queries.
        
        Args:
            queries: List of compliance queries
        
        Returns:
            Tuple of (all_chunks, formatted_context_string)
        """
        all_chunks = []
        seen_chunk_ids = set()
        
        logger.info(f"Retrieving policy context for {len(queries)} queries...")
        
        for i, query in enumerate(queries, 1):
            logger.info(f"   Query {i}/{len(queries)}: '{query[:50]}...'")
            results = self.retriever.search(query, top_k=3)
            
            # Deduplicate chunks
            for chunk in results:
                chunk_id = chunk.get('chunk_id')
                if chunk_id and chunk_id not in seen_chunk_ids:
                    all_chunks.append(chunk)
                    seen_chunk_ids.add(chunk_id)
        
        logger.info(f"✅ Retrieved {len(all_chunks)} unique policy chunks")
        
        # Format context string for GPT-4o
        if not all_chunks:
            context_str = "⚠️ No relevant policy guidance found in indexed documents."
        else:
            context_parts = []
            for i, chunk in enumerate(all_chunks, 1):
                part = (
                    f"[Policy {i}: {chunk['doc_title']} - Chunk {chunk['chunk_index']}]\n"
                    f"Category: {chunk['doc_category']}\n"
                    f"Relevance Score: {chunk.get('score', 0):.4f}\n\n"
                    f"{chunk['content']}\n"
                )
                context_parts.append(part)
            
            context_str = "\n" + ("="*80) + "\n\n".join(context_parts)
        
        return all_chunks, context_str
    
    def _build_compliance_prompt(
        self,
        application_id: str,
        risk_assessment: RiskAssessment,
        policy_context: str
    ) -> str:
        """
        Build GPT-4o prompt for compliance analysis.
        
        Args:
            application_id: Application ID
            risk_assessment: Risk assessment results
            policy_context: Retrieved policy chunks
        
        Returns:
            Complete prompt string
        """
        prompt = f"""You are a lending compliance expert analyzing loan application {application_id}.

Your task: Evaluate the application against lending policies and identify any compliance violations.

**Application Financial Metrics:**
- Debt-to-Income (DTI): {risk_assessment.debt_to_income_ratio:.2f}%
- Loan-to-Value (LTV): {risk_assessment.loan_to_value_ratio:.2f}%
- Monthly Debt Payments: ${risk_assessment.monthly_debt_payments:,.2f}
- Monthly Gross Income: ${risk_assessment.monthly_gross_income:,.2f}
- Risk Level: {risk_assessment.risk_level}
- Risk Score: {risk_assessment.risk_score:.1f}/100

**Risk Factors Identified:**
{chr(10).join('- ' + factor for factor in risk_assessment.risk_factors)}

**Mitigating Factors:**
{chr(10).join('- ' + factor for factor in risk_assessment.mitigating_factors)}

**Relevant Lending Policies:**
{policy_context}

**Instructions:**
1. Review the policy excerpts above carefully
2. Identify any violations or concerns based ONLY on the provided policies
3. If no relevant policy is found for a metric, state "Insufficient policy guidance" - DO NOT make up requirements
4. Classify violations as: critical (must reject), warning (needs review), info (note for file)
5. Provide specific policy citations when identifying violations
6. Calculate an overall compliance score (0-100)

**Output Format (JSON):**
{{
    "is_compliant": boolean,
    "compliance_score": float (0-100),
    "violations": [
        {{
            "policy_name": "Policy Name",
            "policy_section": "Section X.Y",
            "severity": "critical|warning|info",
            "description": "What was violated and why",
            "recommendation": "How to remediate"
        }}
    ],
    "compliance_summary": "Overall assessment with key findings",
    "policy_gaps": ["Any areas where policy guidance was insufficient"]
}}

**Critical Rules:**
- Only cite policies that appear in the "Relevant Lending Policies" section above
- If a policy is not found, acknowledge the gap - never fabricate policy requirements
- Be specific about which policy and section supports each finding
- Consider compensating factors when evaluating borderline cases

Provide your compliance analysis:"""
        
        return prompt
    
    def check_compliance(
        self,
        application_id: str,
        risk_assessment: RiskAssessment,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> ComplianceReport:
        """
        Perform comprehensive compliance check using RAG + GPT-4o.
        
        Args:
            application_id: Unique application identifier
            risk_assessment: Risk assessment results
            additional_context: Optional extra context (extracted docs, etc.)
        
        Returns:
            ComplianceReport with violations, citations, and reasoning
        
        Raises:
            ValueError: If risk_assessment invalid
            Exception: If GPT-4o call fails
        
        Examples:
            >>> agent = ComplianceAgent()
            >>> risk = RiskAssessment(
            ...     application_id="APP-001",
            ...     debt_to_income_ratio=38.5,
            ...     loan_to_value_ratio=82.0,
            ...     monthly_debt_payments=2700.0,
            ...     monthly_gross_income=7000.0,
            ...     risk_level="medium",
            ...     risk_score=65.0,
            ...     risk_factors=["DTI above 36%", "LTV above 80%"],
            ...     mitigating_factors=["Good credit score"],
            ...     reasoning="Borderline case",
            ...     recommendation="review"
            ... )
            >>> report = agent.check_compliance("APP-001", risk)
            >>> print(report.compliance_score)
            75.0
        """
        logger.info(f"🔍 Starting compliance check for {application_id}")
        
        # Step 1: Generate policy queries
        logger.info("   Step 1/4: Generating compliance queries...")
        queries = self._generate_compliance_queries(risk_assessment)
        
        # Step 2: Retrieve policy context
        logger.info("   Step 2/4: Retrieving relevant policies...")
        retrieved_chunks, policy_context = self._retrieve_policy_context(queries)
        
        # Step 3: Build GPT-4o prompt
        logger.info("   Step 3/4: Building compliance prompt...")
        prompt = self._build_compliance_prompt(
            application_id,
            risk_assessment,
            policy_context
        )
        
        # Step 4: Call GPT-4o for analysis
        logger.info(f"   Step 4/4: Analyzing with {self.model}...")
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a lending compliance expert. Analyze applications against policies and return structured JSON."
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
            response_text = response.choices[0].message.content
            compliance_data = json.loads(response_text)
            
            logger.info("   ✅ GPT-4o analysis complete")
            
        except Exception as e:
            logger.error(f"   ❌ GPT-4o call failed: {e}")
            raise
        
        # Extract policy names
        policies_evaluated = self.citation_extractor.match_chunks_to_policies(
            retrieved_chunks
        )
        
        # Extract citations
        citations = self.citation_extractor.extract_citations(
            compliance_data.get('compliance_summary', ''),
            retrieved_chunks
        )
        
        # Build PolicyViolation objects
        violations = []
        for v in compliance_data.get('violations', []):
            violations.append(PolicyViolation(
                policy_name=v.get('policy_name', 'Unknown Policy'),
                policy_section=v.get('policy_section', 'Unknown Section'),
                severity=v.get('severity', 'info'),
                description=v.get('description', ''),
                recommendation=v.get('recommendation', '')
            ))
        
        # Create ComplianceReport
        report = ComplianceReport(
            application_id=application_id,
            checked_at=datetime.utcnow(),
            is_compliant=compliance_data.get('is_compliant', False),
            compliance_score=compliance_data.get('compliance_score', 0.0),
            violations=violations,
            policies_evaluated=policies_evaluated,
            rag_chunks_used=len(retrieved_chunks),
            compliance_summary=compliance_data.get('compliance_summary', ''),
            relevant_policy_excerpts=citations
        )
        
        logger.info(
            f"✅ Compliance check complete: "
            f"is_compliant={report.is_compliant}, "
            f"score={report.compliance_score:.1f}, "
            f"violations={len(violations)}"
        )
        
        return report
    
    def explain_decision(
        self,
        report: ComplianceReport,
        include_policy_excerpts: bool = True
    ) -> str:
        """
        Generate human-readable explanation of compliance decision.
        
        Args:
            report: ComplianceReport to explain
            include_policy_excerpts: Include policy excerpts in explanation
        
        Returns:
            Plain-language explanation string
        """
        explanation_parts = []
        
        # Header
        explanation_parts.append(
            f"📋 Compliance Report for {report.application_id}\n"
            f"{'='*70}"
        )
        
        # Overall status
        status_emoji = "✅" if report.is_compliant else "⚠️"
        explanation_parts.append(
            f"\n{status_emoji} Overall Status: "
            f"{'COMPLIANT' if report.is_compliant else 'NON-COMPLIANT'}"
        )
        explanation_parts.append(f"Compliance Score: {report.compliance_score:.1f}/100")
        
        # Violations
        if report.violations:
            explanation_parts.append(f"\n📌 Violations Found: {len(report.violations)}")
            for i, v in enumerate(report.violations, 1):
                severity_emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(v.severity, "⚪")
                explanation_parts.append(
                    f"\n{i}. {severity_emoji} {v.severity.upper()}: {v.policy_name}"
                )
                explanation_parts.append(f"   Section: {v.policy_section}")
                explanation_parts.append(f"   Issue: {v.description}")
                explanation_parts.append(f"   Recommendation: {v.recommendation}")
        else:
            explanation_parts.append("\n✅ No violations found")
        
        # Summary
        explanation_parts.append(f"\n📝 Summary:\n{report.compliance_summary}")
        
        # Policies consulted
        explanation_parts.append(
            f"\n📚 Policies Evaluated ({len(report.policies_evaluated)}):"
        )
        for policy in report.policies_evaluated:
            explanation_parts.append(f"   • {policy}")
        
        # Policy excerpts
        if include_policy_excerpts and report.relevant_policy_excerpts:
            explanation_parts.append(f"\n📖 Key Policy Excerpts:")
            for excerpt in report.relevant_policy_excerpts:
                explanation_parts.append(f"\n   Policy: {excerpt['policy']}")
                if excerpt['excerpt']:
                    explanation_parts.append(f"   Excerpt: {excerpt['excerpt']}")
        
        # RAG metrics
        explanation_parts.append(
            f"\n📊 RAG System Metrics:"
            f"\n   • Policy chunks retrieved: {report.rag_chunks_used}"
            f"\n   • Timestamp: {report.checked_at.isoformat()}"
        )
        
        explanation_parts.append(f"\n{'='*70}")
        
        return "\n".join(explanation_parts)
