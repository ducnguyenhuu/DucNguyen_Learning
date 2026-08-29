"""
Document Agent - Extract structured data from loan documents.

This module implements the Document Agent which uses Azure Document Intelligence
to extract structured data from loan documents (pay stubs, bank statements, tax
returns, IDs).

Components:
- DocumentIntelligenceExtractor: Azure Document Intelligence client wrapper
- DocumentType: Enum for supported document types
- FieldNormalizer: GPT-4o text normalization (T019)
- DataValidator: Validation rules (T020)
- CompletenessCalculator: Completeness scoring (T021)

Task: T018 - Implement Azure Document Intelligence client wrapper
Phase: 3 (User Story 1 - Document Processing & Extraction)
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient, AnalyzeResult

from utils import config
from models import ExtractedDocument, DocumentType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DocumentIntelligenceExtractor:
    """
    Azure Document Intelligence client wrapper for document extraction.
    
    This class handles document analysis using Azure's prebuilt models:
    - Invoice model: Pay stubs, bank statements
    - Tax W-2 model: Tax returns
    - ID Document model: Driver's licenses, passports
    - Read model: Employment letters (OCR only)
    
    Per research.md decision:
    - Use Document Intelligence for all document extraction
    - No GPT-4 Vision fallback needed for digital PDFs
    - Use prebuilt-invoice model for pay stubs and bank statements
    """
    
    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None, cost_tracker: Optional['CostTracker'] = None):
        """
        Initialize Document Intelligence client.
        
        Args:
            endpoint: Azure Document Intelligence endpoint (uses config if None)
            api_key: Azure Document Intelligence API key (uses config if None)
            cost_tracker: Optional CostTracker instance for logging costs
            
        Raises:
            ValueError: If credentials are missing
        """
        self.endpoint = endpoint or config.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
        self.api_key = api_key or config.AZURE_DOCUMENT_INTELLIGENCE_KEY
        self.cost_tracker = cost_tracker
        
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure Document Intelligence credentials not configured. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY "
                "in your .env file."
            )
        
        # Create Document Analysis client
        self.client = DocumentAnalysisClient(
            endpoint=self.endpoint,
            credential=AzureKeyCredential(self.api_key)
        )
        
        logger.info(f"DocumentIntelligenceExtractor initialized with endpoint: {self.endpoint}")
    
    def analyze_document(
        self, 
        document_path: str, 
        document_type: DocumentType = DocumentType.PAY_STUB,
        application_id: str = "UNKNOWN"
    ) -> ExtractedDocument:
        """
        Analyze a document using Azure Document Intelligence.
        
        This method:
        1. Selects appropriate prebuilt model based on document_type
        2. Sends document to Azure Document Intelligence
        3. Extracts structured data from results
        4. Returns ExtractedDocument with confidence scores
        
        Args:
            document_path: Path to PDF file
            document_type: Type of document (use DocumentType enum)
            application_id: Parent application ID for tracking
            
        Returns:
            ExtractedDocument with extracted data and metadata
            
        Raises:
            FileNotFoundError: If document file doesn't exist
            ValueError: If document type is unsupported
            Exception: If Document Intelligence API call fails
            
        Per spec.md FR-002: Use Azure Document Intelligence with appropriate prebuilt models
        Per research.md: Use invoice model for pay stubs and bank statements
        """
        # Validate file exists
        doc_path = Path(document_path)
        if not doc_path.exists():
            raise FileNotFoundError(f"Document not found: {document_path}")
        
        # Convert enum to string value
        doc_type_str = document_type.value
        
        logger.info(f"Analyzing document: {doc_path.name} (type: {doc_type_str})")
        
        # Select appropriate model based on document type
        model_id = self._select_model(doc_type_str)
        
        try:
            # Read document file
            with open(doc_path, "rb") as f:
                document_data = f.read()
            
            # Call Azure Document Intelligence
            logger.info(f"Calling Document Intelligence with model: {model_id}")
            poller = self.client.begin_analyze_document(
                model_id=model_id,
                document=document_data
            )
            
            # Wait for analysis to complete
            result: AnalyzeResult = poller.result()
            
            logger.info(f"Analysis complete. Found {len(result.documents)} document(s)")
            
            # Log detailed extraction information
            logger.info("="*80)
            logger.info("DOCUMENT INTELLIGENCE EXTRACTION RESULTS")
            logger.info("="*80)
            logger.info(f"Document: {doc_path.name}")
            logger.info(f"Type: {doc_type_str}")
            logger.info(f"Model: {model_id}")
            logger.info(f"Pages: {len(result.pages) if hasattr(result, 'pages') and result.pages else 'N/A'}")
            
            # Log raw content preview
            if hasattr(result, 'content') and result.content:
                content_preview = result.content[:500].replace('\n', ' ')
                logger.info(f"Content Preview: {content_preview}...")
            
            # Extract structured data based on document type
            structured_data, confidence = self._extract_fields(result, doc_type_str)
            
            # Log extracted structured data
            logger.info(f"\nExtracted Structured Data ({len(structured_data)} fields):")
            for key, value in structured_data.items():
                # Truncate long values for readability
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                logger.info(f"  - {key}: {value_str}")
            
            logger.info(f"\nOverall Confidence Score: {confidence:.2%}")
            logger.info("="*80)
            
            # Generate document ID
            document_id = f"DOC-{application_id}-{doc_path.stem}"
            
            # Log Document Intelligence cost (estimate page count from result)
            if self.cost_tracker:
                # Get page count from result (or default to 1)
                page_count = len(result.pages) if hasattr(result, 'pages') and result.pages else 1
                self.cost_tracker.log_document_intelligence_cost(
                    document_id=document_id,
                    document_type=doc_type_str,
                    page_count=page_count,
                    model_id=model_id,
                    confidence_score=confidence
                )
            
            # Create ExtractedDocument
            extracted_doc = ExtractedDocument(
                document_id=document_id,
                application_id=application_id,
                document_type=doc_type_str,
                file_path=str(document_path),
                extraction_method="document_intelligence",
                confidence_score=confidence,
                extracted_at=datetime.utcnow(),
                structured_data=structured_data,
                raw_text=result.content if hasattr(result, 'content') else None,
                validation_errors=[],
                is_valid=confidence >= 0.7  # Track quality, not for fallback trigger
            )
            
            logger.info(
                f"Extraction complete. Confidence: {confidence:.2f}, "
                f"Valid: {extracted_doc.is_valid}"
            )
            
            return extracted_doc
            
        except Exception as e:
            logger.error(f"Document Intelligence analysis failed: {str(e)}")
            
            # Return failed extraction document
            return ExtractedDocument(
                document_id=f"DOC-{application_id}-{doc_path.stem}",
                application_id=application_id,
                document_type=doc_type_str,
                file_path=str(document_path),
                extraction_method="document_intelligence",
                confidence_score=0.0,
                extracted_at=datetime.utcnow(),
                structured_data={},
                raw_text=None,
                validation_errors=[f"Extraction failed: {str(e)}"],
                is_valid=False
            )
    
    def _select_model(self, document_type: str) -> str:
        """
        Select appropriate Document Intelligence prebuilt model.
        Mapping:
        - Pay stubs → Invoice model
        - Bank statements → Invoice model
        - Tax returns → Tax W-2 model
        - Driver's licenses → ID Document model
        - Employment letters → Read model (OCR only)
        
        Args:
            document_type: Type of document (DocumentType enum)
            
        Returns:
            Model ID string for Document Intelligence API
            
        Raises:
            ValueError: If document type is unsupported
        """
        model_map = {
            "pay_stub": "prebuilt-read",  # Use OCR for pay stubs, let GPT-4o extract fields
            "bank_statement": "prebuilt-invoice",
            "tax_return": "prebuilt-tax.us.w2",
            "drivers_license": "prebuilt-idDocument",
            "employment_letter": "prebuilt-read"
        }
        
        model_id = model_map.get(document_type)
        
        if not model_id:
            raise ValueError(
                f"Unsupported document type: {document_type}. "
                f"Supported types: {', '.join(model_map.keys())}"
            )
        
        return model_id
    
    def _extract_fields(
        self, 
        result: AnalyzeResult, 
        document_type: str
    ) -> Tuple[Dict[str, Any], float]:
        """
        Extract structured fields from Document Intelligence result.
        
        This method extracts relevant fields based on document type and
        calculates overall confidence score.
        
        Args:
            result: Document Intelligence analysis result
            document_type: Type of document being processed
            
        Returns:
            Tuple of (structured_data dict, average confidence score)
        """
        # For read model (OCR-only), skip document check and extract text directly
        if document_type in ["pay_stub", "employment_letter"]:
            return self._extract_text_only(result)
        
        if not result.documents or len(result.documents) == 0:
            logger.warning("No documents found in analysis result")
            return {}, 0.0
        
        # Get first document (most documents are single-page or primary document)
        document = result.documents[0]
        
        # Extract fields based on document type
        if document_type == "bank_statement":
            return self._extract_invoice_fields(document)
        elif document_type == "tax_return":
            return self._extract_tax_fields(document)
        elif document_type == "drivers_license":
            return self._extract_id_fields(document)
        else:
            return {}, 0.0
    
    def _extract_invoice_fields(self, document) -> Tuple[Dict[str, Any], float]:
        """
        Extract fields from invoice model (used for pay stubs and bank statements).
        
        Invoice model provides fields like:
        - VendorName (employer/bank name)
        - CustomerName (employee/account holder)
        - InvoiceTotal (gross pay/account balance)
        - InvoiceDate (pay period end/statement date)
        - Items (line items for deductions/transactions)
        
        Args:
            document: Analyzed document from result
            
        Returns:
            Tuple of (structured_data dict, average confidence)
        """
        structured_data = {}
        confidences = []
        
        # Extract available fields
        if hasattr(document, 'fields') and document.fields:
            logger.info(f"\nInvoice Model Fields (Total: {len(document.fields)}):")
            for field_name, field_value in document.fields.items():
                if field_value:
                    # Get value and confidence
                    value = field_value.value if hasattr(field_value, 'value') else None
                    confidence = field_value.confidence if hasattr(field_value, 'confidence') else 0.0
                    
                    if value is not None:
                        structured_data[field_name] = value
                        confidences.append(confidence)
                        
                        # Truncate long values
                        value_str = str(value)
                        if len(value_str) > 80:
                            value_str = value_str[:80] + "..."
                        
                        logger.info(
                            f"  [{confidence:.2%}] {field_name}: {value_str}"
                        )
        
        # Calculate average confidence
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return structured_data, avg_confidence
    
    def _extract_tax_fields(self, document) -> Tuple[Dict[str, Any], float]:
        """
        Extract fields from tax W-2 model.
        
        W-2 model provides fields like:
        - EmployerEIN
        - EmployeeSSN
        - WagesAmount
        - FederalTaxWithheld
        
        Args:
            document: Analyzed document from result
            
        Returns:
            Tuple of (structured_data dict, average confidence)
        """
        structured_data = {}
        confidences = []
        
        if hasattr(document, 'fields') and document.fields:
            logger.info(f"\nTax W-2 Model Fields (Total: {len(document.fields)}):")
            for field_name, field_value in document.fields.items():
                if field_value:
                    value = field_value.value if hasattr(field_value, 'value') else None
                    confidence = field_value.confidence if hasattr(field_value, 'confidence') else 0.0
                    
                    if value is not None:
                        structured_data[field_name] = value
                        confidences.append(confidence)
                        logger.info(f"  [{confidence:.2%}] {field_name}: {value}")
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return structured_data, avg_confidence
    
    def _extract_id_fields(self, document) -> Tuple[Dict[str, Any], float]:
        """
        Extract fields from ID document model (driver's license, passport).
        
        ID model provides fields like:
        - FirstName
        - LastName
        - DateOfBirth
        - DocumentNumber
        - Address
        - ExpirationDate
        
        Args:
            document: Analyzed document from result
            
        Returns:
            Tuple of (structured_data dict, average confidence)
        """
        structured_data = {}
        confidences = []
        
        if hasattr(document, 'fields') and document.fields:
            logger.info(f"\nID Document Model Fields (Total: {len(document.fields)}):")
            for field_name, field_value in document.fields.items():
                if field_value:
                    value = field_value.value if hasattr(field_value, 'value') else None
                    confidence = field_value.confidence if hasattr(field_value, 'confidence') else 0.0
                    
                    if value is not None:
                        structured_data[field_name] = value
                        confidences.append(confidence)
                        logger.info(f"  [{confidence:.2%}] {field_name}: {value}")
        
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return structured_data, avg_confidence
    
    def _extract_text_only(self, result: AnalyzeResult) -> Tuple[Dict[str, Any], float]:
        """
        Extract plain text from read model (OCR only, no structured extraction).
        
        Used for employment letters and other custom documents where
        we'll use GPT-4 for structured extraction in a later step.
        
        Args:
            result: Document Intelligence analysis result
            
        Returns:
            Tuple of (structured_data with raw_content, confidence 1.0)
        """
        # Log OCR extraction
        content = result.content if hasattr(result, 'content') else ""
        logger.info(f"\nRead Model (OCR) Extraction:")
        logger.info(f"  Content Length: {len(content)} characters")
        logger.info(f"  Lines: {len(content.splitlines())}")
        
        # Log first 1000 characters as preview
        if content:
            preview = content[:1000].replace('\n', '\n  ')
            logger.info(f"  Content Preview:\n  {preview}")
            if len(content) > 1000:
                logger.info(f"  ... (truncated, total {len(content)} characters)")
        
        structured_data = {
            "raw_content": content
        }
        
        # Read model doesn't provide confidence scores, assume 1.0 for OCR success
        return structured_data, 1.0


class FieldNormalizer:
    """
    GPT-4o text normalization for extracted fields.
    
    This class uses GPT-4o to intelligently normalize messy extraction outputs
    into consistent, standardized schemas. It handles:
    - Field name unification across document types
    - Date format standardization (ISO 8601)
    - Monetary value cleaning (remove $, commas)
    - Annual to monthly income calculation
    - Text case normalization
    - Missing field inference
    
    Why GPT-4o instead of hardcoded rules?
    - Adapts to variations in field names ("VendorName" vs "Employer" vs "Company")
    - Handles edge cases (bi-weekly pay, YTD calculations)
    - Understands context (same field name means different things in different docs)
    
    Task: T019 - Implement GPT-4o text normalization
    Per spec.md FR-003: Normalize extracted field names and infer derived values
    Per research.md: Use GPT-4o text mode (~$0.005 per application)
    """
    
    def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None, cost_tracker: Optional['CostTracker'] = None):
        """
        Initialize GPT-4o normalizer.
        
        Args:
            endpoint: Azure OpenAI endpoint (uses config if None)
            api_key: Azure OpenAI API key (uses config if None)
            cost_tracker: Optional CostTracker instance for logging costs
            
        Raises:
            ValueError: If credentials are missing
        """
        from openai import AzureOpenAI
        
        self.endpoint = endpoint or config.AZURE_OPENAI_ENDPOINT
        self.api_key = api_key or config.AZURE_OPENAI_API_KEY
        self.deployment = config.AZURE_OPENAI_DEPLOYMENT_GPT4
        self.cost_tracker = cost_tracker
        
        if not self.endpoint or not self.api_key:
            raise ValueError(
                "Azure OpenAI credentials not configured. "
                "Set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY in your .env file."
            )
        
        # Create OpenAI client
        self.client = AzureOpenAI(
            api_key=self.api_key,
            api_version=config.AZURE_OPENAI_API_VERSION,
            azure_endpoint=self.endpoint
        )
        
        logger.info(f"FieldNormalizer initialized with deployment: {self.deployment}")
    
    def normalize(
        self,
        raw_data: Dict[str, Any],
        document_type: DocumentType,
        document_id: str = "UNKNOWN"
    ) -> Tuple[Dict[str, Any], int, int]:
        """
        Normalize extracted fields using GPT-4o.
        
        This method sends raw extraction output to GPT-4o with a specialized
        prompt that instructs it to:
        1. Map fields to standard schema for the document type
        2. Calculate derived values (monthly from annual)
        3. Standardize formats (dates, names, amounts)
        4. Handle missing or unclear fields gracefully
        
        Args:
            raw_data: Raw fields from DocumentIntelligenceExtractor
            document_type: Type of document (determines target schema)
            document_id: Document ID for logging
            
        Returns:
            Tuple of (normalized_data dict, prompt_tokens, completion_tokens)
            
        Example:
            raw = {
                "VendorName": "ACME CORP",
                "InvoiceTotal": "$5,000.00",
                "InvoiceDate": "01/15/25"
            }
            
            normalized, prompt_tok, compl_tok = normalizer.normalize(
                raw, DocumentType.PAY_STUB
            )
            
            # Result:
            {
                "employer_name": "Acme Corp",
                "gross_monthly_income": 5000.00,
                "pay_date": "2025-01-15"
            }
        """
        import json
        
        logger.info(f"Normalizing {document_type.value} fields for {document_id}")
        logger.info("="*80)
        logger.info("GPT-4O FIELD NORMALIZATION")
        logger.info("="*80)
        
        # Log raw input data
        logger.info(f"\nRaw Extracted Data ({len(raw_data)} fields):")
        for key, value in raw_data.items():
            value_str = str(value)
            if len(value_str) > 100:
                value_str = value_str[:100] + "..."
            logger.info(f"  - {key}: {value_str}")
        
        # Build prompt with document-type-specific schema
        prompt = self._build_normalization_prompt(raw_data, document_type)
        
        try:
            # Call GPT-4o
            logger.info(f"\nCalling GPT-4o for normalization...")
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data normalization specialist for loan underwriting. "
                                   "Convert messy extracted document data into clean, standardized JSON schemas."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.0,  # Deterministic for data processing
                max_tokens=1000,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            # Extract normalized data
            content = response.choices[0].message.content
            normalized_data = json.loads(content)
            
            # Get token usage
            prompt_tokens = response.usage.prompt_tokens
            completion_tokens = response.usage.completion_tokens
            
            # Log normalized output
            logger.info(f"\nNormalized Data ({len(normalized_data)} fields):")
            for key, value in normalized_data.items():
                value_str = str(value)
                if len(value_str) > 100:
                    value_str = value_str[:100] + "..."
                logger.info(f"  - {key}: {value_str}")
            
            logger.info(f"\nTokens Used: {prompt_tokens} prompt + {completion_tokens} completion = {prompt_tokens + completion_tokens} total")
            logger.info("="*80)
            
            # Log GPT-4o cost
            if self.cost_tracker:
                self.cost_tracker.log_gpt4o_cost(
                    document_id=document_id,
                    operation="normalization",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens
                )
            
            logger.info(
                f"Normalization complete. "
                f"Fields: {len(normalized_data)}, "
                f"Tokens: {prompt_tokens + completion_tokens}"
            )
            
            return normalized_data, prompt_tokens, completion_tokens
            
        except json.JSONDecodeError as e:
            logger.error(f"GPT-4o returned invalid JSON: {str(e)}")
            # Return raw data as fallback
            return raw_data, 0, 0
            
        except Exception as e:
            logger.error(f"Normalization failed: {str(e)}")
            # Return raw data as fallback
            return raw_data, 0, 0
    
    def _build_normalization_prompt(
        self,
        raw_data: Dict[str, Any],
        document_type: DocumentType
    ) -> str:
        """
        Build document-type-specific normalization prompt.
        
        Args:
            raw_data: Raw extracted fields
            document_type: Type of document
            
        Returns:
            Formatted prompt string
        """
        import json
        from datetime import date, datetime
        
        # Custom JSON encoder to handle date/datetime objects
        def json_serial(obj):
            """JSON serializer for objects not serializable by default json code"""
            if isinstance(obj, (datetime, date)):
                return obj.isoformat()
            # Handle Azure Document Intelligence special types
            if hasattr(obj, 'amount') and hasattr(obj, 'symbol'):
                # CurrencyValue object
                return f"{obj.symbol}{obj.amount}"
            if hasattr(obj, '__dict__'):
                # Generic object with attributes - convert to dict
                return str(obj)
            raise TypeError(f"Type {type(obj)} not serializable")
        
        # Define target schemas for each document type
        schemas = {
            DocumentType.PAY_STUB: {
                "required_fields": [
                    "employer_name",
                    "employee_name",
                    "gross_monthly_income",
                    "net_monthly_income",
                    "pay_period_start",
                    "pay_period_end"
                ],
                "optional_fields": [
                    "employer_address",
                    "employee_ssn",
                    "ytd_gross",
                    "ytd_taxes",
                    "ytd_deductions",
                    "deductions_breakdown"
                ],
                "instructions": (
                    "- If you see 'VendorName', map it to 'employer_name'\n"
                    "- If you see 'CustomerName' or 'EmployeeName', map to 'employee_name'\n"
                    "- If you see 'InvoiceTotal' or 'GrossPay', map to 'gross_monthly_income'\n"
                    "- If amounts are annual (or YTD with date context), divide by 12 for monthly\n"
                    "- If pay is bi-weekly, multiply by 26 and divide by 12 for monthly\n"
                    "- Clean monetary values: remove '$', commas, convert to float\n"
                    "- Standardize dates to ISO 8601 format (YYYY-MM-DD)\n"
                    "- Title case for names (not ALL CAPS)"
                )
            },
            DocumentType.BANK_STATEMENT: {
                "required_fields": [
                    "bank_name",
                    "account_holder_name",
                    "account_number",
                    "statement_start_date",
                    "statement_end_date",
                    "ending_balance"
                ],
                "optional_fields": [
                    "beginning_balance",
                    "total_deposits",
                    "total_withdrawals",
                    "average_balance"
                ],
                "instructions": (
                    "- If you see 'VendorName', map it to 'bank_name' (NOT employer!)\n"
                    "- If you see 'CustomerName', map to 'account_holder_name'\n"
                    "- If you see 'InvoiceTotal' or 'Balance', map to 'ending_balance'\n"
                    "- Account numbers: keep last 4 digits visible, mask rest\n"
                    "- Clean monetary values: remove '$', commas, convert to float\n"
                    "- Standardize dates to ISO 8601 format (YYYY-MM-DD)"
                )
            },
            DocumentType.TAX_RETURN: {
                "required_fields": [
                    "tax_year",
                    "taxpayer_name",
                    "taxpayer_ssn",
                    "wages_annual",
                    "federal_tax_withheld"
                ],
                "optional_fields": [
                    "employer_ein",
                    "employer_name",
                    "state_tax_withheld",
                    "social_security_wages",
                    "medicare_wages"
                ],
                "instructions": (
                    "- Map W-2 fields: 'WagesAmount' → 'wages_annual'\n"
                    "- Calculate monthly: wages_annual / 12 → 'wages_monthly'\n"
                    "- If you see 'EmployerEIN', map to 'employer_ein'\n"
                    "- If you see 'EmployeeSSN', map to 'taxpayer_ssn'\n"
                    "- Tax year should be 4-digit integer\n"
                    "- Clean monetary values: remove '$', commas, convert to float"
                )
            },
            DocumentType.DRIVERS_LICENSE: {
                "required_fields": [
                    "first_name",
                    "last_name",
                    "date_of_birth",
                    "license_number",
                    "expiration_date"
                ],
                "optional_fields": [
                    "address",
                    "city",
                    "state",
                    "zip_code",
                    "issue_date"
                ],
                "instructions": (
                    "- Separate 'FirstName' and 'LastName' if combined\n"
                    "- Map 'DocumentNumber' to 'license_number'\n"
                    "- Standardize dates to ISO 8601 format (YYYY-MM-DD)\n"
                    "- Verify DOB is in the past, expiration in future\n"
                    "- Title case for names"
                )
            },
            DocumentType.EMPLOYMENT_LETTER: {
                "required_fields": [
                    "employer_name",
                    "employee_name",
                    "job_title",
                    "employment_start_date",
                    "annual_salary"
                ],
                "optional_fields": [
                    "employment_status",
                    "employer_contact",
                    "letter_date",
                    "monthly_salary"
                ],
                "instructions": (
                    "- Extract from 'raw_content' field (OCR text)\n"
                    "- Look for salary mentions: '$X per year', '$X annually'\n"
                    "- Calculate monthly: annual_salary / 12 → 'monthly_salary'\n"
                    "- Extract dates from phrases like 'employed since...'\n"
                    "- Standardize dates to ISO 8601 format (YYYY-MM-DD)"
                )
            }
        }
        
        schema = schemas.get(document_type, schemas[DocumentType.PAY_STUB])
        
        prompt = f"""You are normalizing extracted data from a **{document_type.value}** document.

**Raw Extracted Data** (from Azure Document Intelligence):
```json
{json.dumps(raw_data, indent=2, default=json_serial)}
```

**Your Task**:
Convert the raw data into this standardized schema:

**Required Fields** (must attempt to extract):
{json.dumps(schema["required_fields"], indent=2)}

**Optional Fields** (include if available):
{json.dumps(schema["optional_fields"], indent=2)}

**Normalization Rules**:
{schema["instructions"]}

**Output Format**:
Return ONLY a JSON object with normalized fields. Use `null` for missing required fields.

**Example**:
{{
  "employer_name": "Acme Corporation",
  "employee_name": "John Doe",
  "gross_monthly_income": 5000.00,
  "net_monthly_income": 3800.00,
  "pay_period_start": "2025-01-01",
  "pay_period_end": "2025-01-15"
}}

**Important**:
- Be smart about field mappings based on document type context
- Calculate derived values when possible
- Clean all monetary values (no $, commas)
- Use ISO 8601 dates (YYYY-MM-DD)
- Return valid JSON only (no markdown, no explanations)
"""
        
        return prompt


class DataValidator:
    """
    Validation rules for extracted document data using ValidationRuleEngine.
    
    This class validates normalized document data against business logic rules
    defined in YAML configuration (src/validation_rules.yaml):
    - Net income <= Gross income (pay stubs)
    - Dates are chronological (start < end)
    - Amounts are non-negative
    - Required fields are present
    - SSN/EIN format validation
    - Date range reasonableness
    
    All validation rules are configured in YAML for easy maintenance by business users.
    
    Per spec.md FR-004: Validate extracted data against consistency rules
    Task: T020 - Implement validation rules
    """
    
    def __init__(self, rules_file: str = "src/validation_rules.yaml"):
        """
        Initialize DataValidator with ValidationRuleEngine.
        
        Args:
            rules_file: Path to validation rules YAML configuration
            
        Raises:
            ImportError: If ValidationRuleEngine cannot be imported
            FileNotFoundError: If rules file doesn't exist
        """
        from utils import ValidationRuleEngine
        
        self.rules_engine = ValidationRuleEngine(rules_file)
        logger.info(f"DataValidator initialized with ValidationRuleEngine (rules: {rules_file})")
    
    def validate(
        self,
        normalized_data: Dict[str, Any],
        document_type: DocumentType
    ) -> Tuple[bool, List[str]]:
        """
        Validate normalized document data against business rules.
        
        This method uses ValidationRuleEngine to apply document-type-specific
        validation rules defined in YAML configuration.
        
        Args:
            normalized_data: Normalized fields from FieldNormalizer
            document_type: Type of document being validated
            
        Returns:
            Tuple of (is_valid bool, list of error messages)
            
        Example:
            validator = DataValidator()
            is_valid, errors = validator.validate(
                {
                    "gross_monthly_income": 5000.00,
                    "net_monthly_income": 6000.00  # Invalid!
                },
                DocumentType.PAY_STUB
            )
            # is_valid = False
            # errors = ["[PAY_001] Net income (6000.00) exceeds gross income (5000.00)"]
        """
        return self.rules_engine.validate(normalized_data, document_type)


class CompletenessCalculator:
    """
    Calculate completeness score for extracted documents.
    
    This class calculates how complete a document extraction is by comparing
    extracted fields against required field schemas for each document type.
    
    Completeness metrics:
    - Percentage of required fields present (0-100%)
    - List of missing critical fields
    - Overall quality assessment
    
    Per spec.md FR-005: Calculate extraction completeness
    Task: T021 - Implement completeness scoring
    """
    
    # Define required fields for each document type
    REQUIRED_FIELDS = {
        DocumentType.PAY_STUB: [
            "employer_name",
            "employee_name",
            "gross_monthly_income",
            "net_monthly_income",
            "pay_period_start",
            "pay_period_end"
        ],
        DocumentType.BANK_STATEMENT: [
            "bank_name",
            "account_holder_name",
            "account_number",
            "statement_start_date",
            "statement_end_date",
            "ending_balance"
        ],
        DocumentType.TAX_RETURN: [
            "tax_year",
            "taxpayer_name",
            "taxpayer_ssn",
            "wages_annual",
            "federal_tax_withheld"
        ],
        DocumentType.DRIVERS_LICENSE: [
            "first_name",
            "last_name",
            "date_of_birth",
            "license_number",
            "expiration_date"
        ],
        DocumentType.EMPLOYMENT_LETTER: [
            "employer_name",
            "employee_name",
            "job_title",
            "employment_start_date",
            "annual_salary"
        ]
    }
    
    def calculate_completeness(
        self,
        normalized_data: Dict[str, Any],
        document_type: DocumentType
    ) -> Tuple[float, List[str], str]:
        """
        Calculate completeness score for extracted document.
        
        This method:
        1. Gets required fields for document type
        2. Checks which required fields are present and non-null
        3. Calculates percentage completeness
        4. Identifies missing critical fields
        5. Provides quality assessment
        
        Args:
            normalized_data: Normalized document data from FieldNormalizer
            document_type: Type of document being assessed
            
        Returns:
            Tuple of (completeness_percentage, missing_fields, quality_label)
            
        Example:
            calculator = CompletenessCalculator()
            score, missing, quality = calculator.calculate_completeness(
                {
                    "employer_name": "Acme Corp",
                    "employee_name": "John Doe",
                    "gross_monthly_income": 5000.00,
                    "net_monthly_income": 3800.00,
                    # Missing: pay_period_start, pay_period_end
                },
                DocumentType.PAY_STUB
            )
            # score = 66.67 (4 out of 6 required fields)
            # missing = ["pay_period_start", "pay_period_end"]
            # quality = "partial"
        """
        # Get required fields for this document type
        required_fields = self.REQUIRED_FIELDS.get(document_type, [])
        
        if not required_fields:
            logger.warning(f"No required fields defined for {document_type.value}")
            return 0.0, [], "unknown"
        
        # Check which required fields are present and have non-null values
        present_fields = []
        missing_fields = []
        
        for field in required_fields:
            value = normalized_data.get(field)
            
            # Field is present if it exists and is not None/empty
            if value is not None and value != "":
                # For strings, check it's not just whitespace
                if isinstance(value, str) and value.strip() == "":
                    missing_fields.append(field)
                else:
                    present_fields.append(field)
            else:
                missing_fields.append(field)
        
        # Calculate percentage completeness
        total_required = len(required_fields)
        total_present = len(present_fields)
        completeness_percentage = (total_present / total_required * 100) if total_required > 0 else 0.0
        
        # Determine quality label
        quality_label = self._get_quality_label(completeness_percentage)
        
        logger.info(
            f"Completeness for {document_type.value}: {completeness_percentage:.1f}% "
            f"({total_present}/{total_required} fields) - {quality_label}"
        )
        
        if missing_fields:
            logger.warning(f"Missing fields: {', '.join(missing_fields)}")
        
        return completeness_percentage, missing_fields, quality_label
    
    def _get_quality_label(self, percentage: float) -> str:
        """
        Convert completeness percentage to quality label.
        
        Quality thresholds:
        - excellent: 100% complete
        - good: 80-99% complete
        - partial: 50-79% complete
        - poor: <50% complete
        
        Args:
            percentage: Completeness percentage (0-100)
            
        Returns:
            Quality label string
        """
        if percentage >= 100.0:
            return "excellent"
        elif percentage >= 80.0:
            return "good"
        elif percentage >= 50.0:
            return "partial"
        else:
            return "poor"
    
    def get_required_fields(self, document_type: DocumentType) -> List[str]:
        """
        Get list of required fields for a document type.
        
        Useful for displaying expectations to users or for validation.
        
        Args:
            document_type: Type of document
            
        Returns:
            List of required field names
            
        Example:
            calculator = CompletenessCalculator()
            fields = calculator.get_required_fields(DocumentType.PAY_STUB)
            # ["employer_name", "employee_name", ...]
        """
        return self.REQUIRED_FIELDS.get(document_type, [])


class CostTracker:
    """
    Cost tracking for Document Intelligence and GPT-4o usage.
    
    This class logs per-document costs for:
    - Azure Document Intelligence extraction ($0.001-0.0015 per page)
    - GPT-4o text normalization (token-based pricing)
    
    Enables cost analysis and optimization for production deployments.
    
    Task: T024 - Implement cost logging
    Per spec.md FR-007: Track Document Intelligence usage and log per-document cost
    Per research.md: Document Intelligence ~$0.001/page, GPT-4o ~$0.005/application
    """
    
    # Pricing constants (as of Nov 2025)
    DOCUMENT_INTELLIGENCE_COST_PER_PAGE = 0.0015  # USD per page
    GPT4O_PROMPT_COST_PER_1K_TOKENS = 0.005  # USD per 1K prompt tokens
    GPT4O_COMPLETION_COST_PER_1K_TOKENS = 0.015  # USD per 1K completion tokens
    
    def __init__(self):
        """Initialize cost tracker with empty log."""
        self.cost_log = []
        logger.info("CostTracker initialized")
    
    def log_document_intelligence_cost(
        self,
        document_id: str,
        document_type: str,
        page_count: int,
        model_id: str,
        confidence_score: float,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Log Document Intelligence extraction cost.
        
        Args:
            document_id: Unique document identifier
            document_type: Type of document processed
            page_count: Number of pages analyzed
            model_id: Azure DI model used (e.g., prebuilt-invoice)
            confidence_score: Extraction confidence score
            timestamp: When extraction occurred (defaults to now)
            
        Returns:
            Cost in USD for this extraction
            
        Example:
            tracker = CostTracker()
            cost = tracker.log_document_intelligence_cost(
                document_id="DOC-001-pay_stub",
                document_type="pay_stub",
                page_count=2,
                model_id="prebuilt-invoice",
                confidence_score=0.85
            )
            # Returns: 0.003 (2 pages × $0.0015)
        """
        cost_usd = page_count * self.DOCUMENT_INTELLIGENCE_COST_PER_PAGE
        
        log_entry = {
            "timestamp": timestamp or datetime.utcnow(),
            "service": "document_intelligence",
            "document_id": document_id,
            "document_type": document_type,
            "page_count": page_count,
            "model_id": model_id,
            "confidence_score": confidence_score,
            "cost_usd": round(cost_usd, 6)
        }
        
        self.cost_log.append(log_entry)
        
        logger.info(
            f"Document Intelligence cost: ${cost_usd:.6f} "
            f"({page_count} pages × ${self.DOCUMENT_INTELLIGENCE_COST_PER_PAGE})"
        )
        
        return cost_usd
    
    def log_gpt4o_cost(
        self,
        document_id: str,
        operation: str,
        prompt_tokens: int,
        completion_tokens: int,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Log GPT-4o normalization cost.
        
        Args:
            document_id: Document being processed
            operation: Operation type (e.g., "normalization", "validation")
            prompt_tokens: Number of prompt tokens used
            completion_tokens: Number of completion tokens generated
            timestamp: When operation occurred (defaults to now)
            
        Returns:
            Cost in USD for this operation
            
        Example:
            tracker = CostTracker()
            cost = tracker.log_gpt4o_cost(
                document_id="DOC-001-pay_stub",
                operation="normalization",
                prompt_tokens=500,
                completion_tokens=200
            )
            # Returns: 0.0055 (prompt + completion costs)
        """
        prompt_cost = (prompt_tokens / 1000) * self.GPT4O_PROMPT_COST_PER_1K_TOKENS
        completion_cost = (completion_tokens / 1000) * self.GPT4O_COMPLETION_COST_PER_1K_TOKENS
        total_cost = prompt_cost + completion_cost
        
        log_entry = {
            "timestamp": timestamp or datetime.utcnow(),
            "service": "gpt4o",
            "document_id": document_id,
            "operation": operation,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost_usd": round(total_cost, 6)
        }
        
        self.cost_log.append(log_entry)
        
        logger.info(
            f"GPT-4o cost: ${total_cost:.6f} "
            f"({prompt_tokens + completion_tokens} tokens)"
        )
        
        return total_cost
    
    def get_total_cost(self) -> float:
        """
        Calculate total cost across all logged operations.
        
        Returns:
            Total cost in USD
            
        Example:
            tracker = CostTracker()
            # ... process multiple documents ...
            total = tracker.get_total_cost()
            # Returns: 0.452 (sum of all operations)
        """
        return sum(entry["cost_usd"] for entry in self.cost_log)
    
    def get_cost_by_document(self, document_id: str) -> float:
        """
        Calculate total cost for a specific document.
        
        Args:
            document_id: Document to calculate cost for
            
        Returns:
            Total cost in USD for this document
            
        Example:
            tracker = CostTracker()
            cost = tracker.get_cost_by_document("DOC-001-pay_stub")
            # Returns: 0.008 (DI + GPT-4o costs for this doc)
        """
        return sum(
            entry["cost_usd"]
            for entry in self.cost_log
            if entry["document_id"] == document_id
        )
    
    def get_cost_breakdown(self) -> Dict[str, Any]:
        """
        Get detailed cost breakdown by service and operation.
        
        Returns:
            Dictionary with cost analysis:
            - total_cost: Total USD across all operations
            - document_intelligence_cost: Total DI extraction cost
            - gpt4o_cost: Total GPT-4o cost
            - document_count: Number of documents processed
            - avg_cost_per_document: Average cost per document
            - cost_by_service: Breakdown by service type
            
        Example:
            tracker = CostTracker()
            breakdown = tracker.get_cost_breakdown()
            print(f"Total: ${breakdown['total_cost']:.4f}")
            print(f"Avg per doc: ${breakdown['avg_cost_per_document']:.4f}")
        """
        di_cost = sum(
            entry["cost_usd"]
            for entry in self.cost_log
            if entry["service"] == "document_intelligence"
        )
        
        gpt4o_cost = sum(
            entry["cost_usd"]
            for entry in self.cost_log
            if entry["service"] == "gpt4o"
        )
        
        document_ids = set(
            entry["document_id"]
            for entry in self.cost_log
        )
        
        total_cost = di_cost + gpt4o_cost
        doc_count = len(document_ids)
        avg_cost = total_cost / doc_count if doc_count > 0 else 0.0
        
        return {
            "total_cost": round(total_cost, 6),
            "document_intelligence_cost": round(di_cost, 6),
            "gpt4o_cost": round(gpt4o_cost, 6),
            "document_count": doc_count,
            "avg_cost_per_document": round(avg_cost, 6),
            "cost_by_service": {
                "document_intelligence": round(di_cost, 6),
                "gpt4o": round(gpt4o_cost, 6)
            }
        }
    
    def get_cost_log(self) -> List[Dict[str, Any]]:
        """
        Get complete cost log with all entries.
        
        Returns:
            List of cost log entries (chronological order)
            
        Example:
            tracker = CostTracker()
            log = tracker.get_cost_log()
            for entry in log:
                print(f"{entry['timestamp']}: {entry['service']} - ${entry['cost_usd']}")
        """
        return self.cost_log.copy()
    
    def reset(self):
        """
        Clear cost log (useful for starting new analysis session).
        
        Example:
            tracker = CostTracker()
            # ... process batch 1 ...
            batch1_cost = tracker.get_total_cost()
            tracker.reset()
            # ... process batch 2 ...
            batch2_cost = tracker.get_total_cost()
        """
        self.cost_log = []
        logger.info("Cost log reset")
