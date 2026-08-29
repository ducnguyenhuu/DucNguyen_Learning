# Requirements Gaps Analysis

**Date**: December 10, 2025  
**Source**: requirements-quality.md checklist review  
**Status**: 35/116 items completed (30%), 81 gaps/ambiguities remaining

---

## Executive Summary

**Good News**: ✅ Core requirements are well-defined
- All 4 challenges have complete input/output specs
- Azure service tiers and quotas documented
- Deliverable structure consistent across challenges
- Technical metrics measurable with formulas

**Critical Gaps**: ⚠️ Error handling and edge cases need attention
- 47 [Gap] markers: Missing requirements for failure scenarios
- 15 [Ambiguity] markers: Terms need quantification
- 3 [Conflict] markers: Scope vs timeline tensions

---

## Priority 1: CRITICAL Gaps (Blocking Implementation)

### Error Handling Requirements (8 gaps)

| ID | Gap | Impact | Recommendation |
|----|-----|--------|----------------|
| CHK058 | Azure API failure handling not defined | Implementation will crash on rate limits/timeouts | Add retry logic requirements (research.md R5 has details, need in spec) |
| CHK059 | Invalid image input requirements missing | No validation for corrupt files, wrong format | Add image validation requirements (JPEG/PNG check, size limits) |
| CHK060 | Dataset download failure scenarios not addressed | Setup will fail silently | Add retry/fallback requirements for dataset downloads |
| CHK061 | Azure quota exceeded scenarios not defined | Users hit quota with no guidance | Already documented in §10 quota table, but need recovery flow |
| CHK062 | Model training failure requirements missing | Training crashes with no recovery | Add checkpoint/resume requirements for YOLO training |
| CHK063 | Retry requirements for transient failures missing | Transient errors cause permanent failures | Reference research.md R5 (3-attempt exponential backoff) in spec |
| CHK064 | Checkpoint/resume requirements not defined | Long training restarts from scratch on failure | Add YOLO checkpoint saving every N epochs |
| CHK065 | Azure resource cleanup requirements missing | Forgotten resources incur costs | Add cleanup checklist to spec §10 |

**Action**: Add new §13 "Error Handling & Resilience" to SPECIFICATION.md with:
- Image validation requirements (format, size, corruption checks)
- Retry logic requirements (3-attempt exponential backoff for Azure APIs)
- Training resilience (checkpoint every 10 epochs, resume capability)
- Quota handling (monitor usage, fallback to YOLO when Custom Vision exhausted)
- Resource cleanup checklist (delete unused resources, stop compute)

---

## Priority 2: HIGH Gaps (Needed Before Implementation)

### Edge Case Requirements (11 gaps)

| ID | Gap | Scenario | Recommendation |
|----|-----|----------|----------------|
| CHK066 | Empty shelf images (zero products) | Store just opened, shelf cleared | Define behavior: Return empty list with confidence score |
| CHK067 | Extremely crowded shelves (>100 products) | Holiday rush, full restock | Define performance degradation limits (acceptable latency at 100+ products) |
| CHK068 | Poor lighting conditions | Store dimly lit, glare from windows | Define minimum lighting requirements or "quality too low" detection |
| CHK069 | Blurry or low-resolution images | Camera shake, low-quality phone camera | Define minimum quality thresholds (reject <480p, blur detection) |
| CHK070 | Price tags in multiple currencies/formats | Already partially addressed | ✅ Challenge 4 lists $X.XX, €X,XX formats - mark as SATISFIED |
| CHK072 | Maximum dataset size limits for Custom Vision F0 | Already documented | ✅ Spec §10 shows 5,000 image limit - mark as SATISFIED |
| CHK073 | Custom Vision training iteration limits | Already documented | ✅ Spec §10 shows 10 iterations limit - mark as SATISFIED |
| CHK074 | Document Intelligence page limits | Already documented | ✅ Spec §10 shows 500 pages/month - mark as SATISFIED |
| CHK075 | Challenge 3 depends on Challenge 2 failures | No detections from Challenge 2 | Define fallback: "0 products detected, stock count = 0" |
| CHK076 | Notebook kernel crashes mid-execution | Jupyter kernel dies during training | Add "use auto-save" note, save intermediate outputs |

**Action**: Add new §2.5 "Edge Cases & Boundary Conditions" subsection to each challenge with:
- Empty shelf handling (return empty list)
- Crowded shelf limits (define >100 products as out-of-scope for learning project)
- Image quality requirements (min 480p resolution, reject if blur >threshold)
- Dependency failures (Challenge 3 handles empty Challenge 2 output gracefully)

---

## Priority 3: MEDIUM Gaps (Clarifications Needed)

### Ambiguous Terms (15 ambiguities)

| ID | Ambiguity | Current Text | Recommended Clarification |
|----|-----------|--------------|---------------------------|
| CHK017 | Latency measurement conditions unclear | "< 500ms per image" | Add: "Measured on M1/M2 Mac or NVIDIA 6GB+ GPU, single image (batch=1)" |
| CHK019 | "Simple implementations" not quantified | Executive Summary | Add: "Simple = <200 LOC per module, cyclomatic complexity <10" |
| CHK021 | "Gap detection logic" insufficiently defined | Challenge 1 Phase 2 | Add algorithm: "Sort detections by x-coord, compute gaps, flag >100px width" |
| CHK022 | "Shelf depth estimation" methodology unclear | Challenge 3 Phase 2 | Add: "Depth = front-facing count × estimated rows (default: 3 rows deep)" |
| CHK023 | "Configurable parameters" scope undefined | Challenge 1 Phase 3 | Add: "Config: gap_threshold_px, confidence_threshold, nms_iou" |
| CHK025 | "Varying orientations" not quantified | Challenge 2 requirements | Add: "Rotation: ±15°, Occlusion: up to 30% of product" |
| CHK028 | Phase 2-4 requirements excluded or included? | §6 Weekly Schedule | Clarify: "Phase 1 only for MVP (weeks 1-6), Phases 2-4 optional extensions" |
| CHK029 | "Optional" Azure ML inclusion criteria | §10 Azure ML | Add: "Optional: Skip if budget <$5 or prefer local training only" |
| CHK046 | Learning metrics subjective | §7 Learning Metrics | Add rubric: "Can explain = write 3-paragraph summary of service" |
| CHK095 | Local GPU requirements unclear | §2.2 Hardware Specs | ✅ Already clarified in Challenge 2 - mark as SATISFIED |
| CHK102 | "Simple threshold-based" gap detection | Challenge 1 Phase 2 | Add: "Threshold = 100px minimum gap width (configurable in Phase 3)" |
| CHK103 | "Rapid prototyping" timeline not quantified | Challenge 2 Phase 1 | Add: "Rapid = <2 hours to upload data + train first iteration" |
| CHK104 | "Mock data" for price database unclear | Challenge 4 Phase 4 | Add: "Mock = 50-row CSV with SKU, expected_price, currency columns" |
| CHK105 | "Optional" trend tracking scope undefined | Challenge 3 Phase 3 | Add: "Optional: Skip if time limited, or implement simple time-series plot" |
| CHK109 | "Basic MLOps" scope unclear | §12 MLOps | Add: "Basic = model registry + simple pipeline (no monitoring/CI/CD)" |

**Action**: Update SPECIFICATION.md to quantify these 15 ambiguous terms with specific values, algorithms, or decision criteria.

---

## Priority 4: LOW Gaps (Nice-to-Have)

### Documentation & Traceability (8 gaps)

| ID | Gap | Impact | Recommendation |
|----|-----|--------|----------------|
| CHK012 | Python concepts not mapped to challenges | Learners don't know what they'll learn per challenge | Add table: Challenge 1 → type hints, dataclasses; Challenge 2 → decorators, generators |
| CHK013 | Azure concepts not mapped to challenges | Same as above for Azure services | Add table: Challenge 1 → Custom Vision API; Challenge 4 → Document Intelligence |
| CHK050 | Failure criteria not defined | No clear "done" vs "failed" distinction | Add: "Failed = metrics below target after 3 iterations with full dataset" |
| CHK078 | Performance degradation requirements missing | Don't know acceptable ranges | Add: "Acceptable degradation: 90-95% of target (e.g., 81-85% mAP still passing)" |
| CHK079 | Scalability requirements unclear | Single image or batch processing? | Add: "Phase 1: Single image only. Phase 4: Optional batch processing" |
| CHK115 | Requirement ID scheme not established | Hard to reference requirements | Add: "Use format FR-001, NFR-001 for functional/non-functional requirements" |
| CHK116 | Acceptance criteria not linked to requirements | Traceability gap | Add requirement IDs to checklist items in §11 |

**Action**: Enhance documentation with Python/Azure concept mapping table and establish FR-/NFR- requirement ID scheme.

---

## Conflicts Detected (3 items)

### CHK106: "Simple implementations" vs "Production-standard structure"
- **Conflict**: Executive Summary says "simple implementations" but §4 requires "production Python package structure"
- **Resolution**: ✅ Already resolved by Constitution §II: "Production-Standard Structure, Simple Implementation" - clarifies these are compatible
- **Action**: Add note to Executive Summary referencing Constitution §II

### CHK107: "12-week timeline" vs "4 challenges + MLOps + documentation"
- **Conflict**: 12 weeks for 4 challenges (3 weeks each) + 2 weeks backend + MLOps seems tight
- **Analysis**: Weekly schedule shows weeks 5-10 cover all 4 challenges (1.5 weeks each) - feasible if Phase 1 only
- **Resolution**: Timeline is tight but achievable if focusing on Phase 1 implementations only
- **Action**: Add note to §6: "Timeline assumes Phase 1 implementations only; Phases 2-4 are optional extensions"

### CHK108: "Free tier only" vs "Azure ML for MLOps"
- **Conflict**: §10 says prioritize free tier, but Azure ML costs $5-20/month
- **Resolution**: Azure ML already marked "optional" in spec
- **Action**: ✅ No change needed - conflict already resolved by marking Azure ML optional

---

## Summary Statistics

| Category | Satisfied | Gaps | Ambiguities | Conflicts | Total |
|----------|-----------|------|-------------|-----------|-------|
| Challenge Requirements | 5/5 (100%) | 0 | 0 | 0 | 5 |
| Azure Service Requirements | 5/5 (100%) | 0 | 0 | 0 | 5 |
| Educational Requirements | 3/5 (60%) | 2 | 0 | 0 | 5 |
| Metric Clarity | 3/5 (60%) | 0 | 2 | 0 | 5 |
| Technical Term Clarity | 0/5 (0%) | 0 | 5 | 0 | 5 |
| Scope Boundaries Clarity | 1/4 (25%) | 1 | 2 | 0 | 4 |
| Cross-Challenge Consistency | 4/4 (100%) | 0 | 0 | 0 | 4 |
| Document Internal Consistency | 0/5 (0%) | 0 | 0 | 0 | 5 |
| Constitution Alignment | 0/3 (0%) | 0 | 0 | 0 | 3 |
| Measurability | 4/5 (80%) | 0 | 1 | 0 | 5 |
| Completeness of Success Criteria | 0/4 (0%) | 1 | 0 | 0 | 4 |
| Scenario Coverage | 0/15 (0%) | 8 | 0 | 0 | 15 |
| Edge Case Coverage | 4/11 (36%) | 7 | 0 | 0 | 11 |
| Non-Functional Requirements | 6/15 (40%) | 9 | 0 | 0 | 15 |
| Dependencies & Assumptions | 0/10 (0%) | 3 | 2 | 0 | 10 |
| Ambiguities & Conflicts | 1/9 (11%) | 0 | 5 | 3 | 9 |
| Traceability | 0/6 (0%) | 2 | 0 | 0 | 6 |

**Overall**: 35/116 items satisfied (30%)

---

## Recommended Action Plan

### Phase 1: Address CRITICAL Gaps (1-2 hours)
1. Add §13 "Error Handling & Resilience" to SPECIFICATION.md
   - Image validation requirements
   - Azure API retry logic (reference research.md R5)
   - Training resilience (checkpoints, resume)
   - Quota handling and fallback strategies
   - Resource cleanup checklist

### Phase 2: Address HIGH Gaps (2-3 hours)
2. Add §2.5 "Edge Cases & Boundary Conditions" to each challenge
   - Empty shelf handling
   - Crowded shelf limits (>100 products out-of-scope)
   - Image quality requirements
   - Dependency failure handling

### Phase 3: Clarify MEDIUM Ambiguities (1-2 hours)
3. Update existing sections to quantify 15 ambiguous terms
   - Add hardware specs to Challenge 1 latency requirement
   - Define "simple" with LOC/complexity limits
   - Add gap detection algorithm details
   - Quantify rotation/occlusion tolerances
   - Clarify Phase 1 vs Phase 2-4 scope

### Phase 4: Enhance LOW Priority Items (1 hour)
4. Add Python/Azure concept mapping table to §1
5. Establish FR-/NFR- requirement ID scheme
6. Add performance degradation acceptable ranges

**Total Effort**: 5-8 hours to address all gaps

---

## Checklist Update Status

After reviewing SPECIFICATION.md:
- ✅ **35 items marked complete** (satisfied by current spec)
- ⚠️ **47 gaps identified** (requirements missing from spec)
- ❓ **15 ambiguities flagged** (terms need quantification)
- ⚡ **3 conflicts detected** (2 resolved, 1 acknowledged as tight timeline)

**Next Step**: Proceed with Phase 1 (CRITICAL gaps) or begin implementation with current spec accepting gaps as technical debt.
