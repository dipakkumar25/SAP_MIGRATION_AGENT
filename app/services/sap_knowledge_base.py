"""
SAP Migration Knowledge Base
Provides authoritative SAP S/4HANA migration documents for RAG ingestion.

Each document represents a self-contained knowledge chunk about a specific
SAP migration topic. Documents are tagged with metadata so retrieved
context can cite its source in the LLM prompt.
"""
from __future__ import annotations

from typing import List

from langchain.schema import Document


def get_sap_knowledge_documents() -> List[Document]:
    """Return the full list of SAP migration knowledge documents."""
    return (
        _ATC_FINDINGS_DOCS
        + _SIMPLIFICATION_LIST_DOCS
        + _CUSTOM_CODE_DOCS
        + _BUSINESS_PARTNER_DOCS
        + _UNIVERSAL_JOURNAL_DOCS
        + _MATERIAL_LEDGER_DOCS
        + _CUTOVER_DOCS
        + _RUNBOOK_BEST_PRACTICES_DOCS
        + _SECURITY_DOCS
        + _PERFORMANCE_DOCS
    )


# ── ATC Findings & Remediation ───────────────────────────────────────────────

_ATC_FINDINGS_DOCS = [
    Document(
        page_content=(
            "LIST_FROM_MEMORY is a function module removed in SAP S/4HANA. "
            "It was used in classic SAP ECC to retrieve list output. "
            "Migration fix: Replace all usages with CL_SALV_TABLE or cl_gui_alv_grid. "
            "The CL_SALV_TABLE class provides a modern OO-based ALV output that works "
            "in both SAP GUI and Fiori. Effort per occurrence: approximately 2 hours. "
            "SAP Note: 2127080. This is a CRITICAL ATC finding that causes runtime "
            "short dumps (CALL_FUNCTION_NOT_FOUND) after migration."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "LIST_FROM_MEMORY", "priority": "critical"},
    ),
    Document(
        page_content=(
            "WRITE_FORM and END_FORM function modules are removed in SAP S/4HANA. "
            "These were used for SAPscript-based output. "
            "Migration fix: Replace with Adobe Forms (FP_JOB_OPEN / FP_FUNCTION_MODULE_NAME) "
            "or SmartForms. For batch printing, use RSNAST00 successor programs. "
            "SAP Note: 1878944. Effort: 1–2 days per form."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "WRITE_FORM", "priority": "critical"},
    ),
    Document(
        page_content=(
            "REUSE_ALV_GRID_DISPLAY is deprecated in SAP S/4HANA. "
            "Classic ALV function modules (REUSE_ALV_*) still work but are not "
            "supported in Fiori Launchpad context. "
            "Migration fix: Migrate reports to CL_SALV_TABLE for SAP GUI, "
            "or build OData-backed Fiori apps using SAPUI5 for embedded analytics. "
            "SAP Note: 2285258. The ATC check SLIN_OBSOLETE_STATEMENT flags these. "
            "Effort: 1 day per report using CL_SALV_TABLE migration pattern."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "REUSE_ALV_GRID_DISPLAY", "priority": "high"},
    ),
    Document(
        page_content=(
            "Dynamic SQL (Open SQL with string concatenation) is flagged by ATC "
            "check SCI_DYNAMIC_ABAP as a security vulnerability in SAP S/4HANA. "
            "This allows SQL injection attacks against the HANA database. "
            "Migration fix: Replace string-concatenated WHERE clauses with parameterized "
            "queries using placeholder tokens (@variable). "
            "Use CL_ABAP_DYN_PRG=>CHECK_WHITELIST_STR for validating dynamic tokens. "
            "SAP Note: 1520356. Effort: 4 hours per occurrence."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "SQL_INJECTION", "priority": "critical"},
    ),
    Document(
        page_content=(
            "SELECT * with ORDER BY non-key fields on large tables causes "
            "full table scans on SAP HANA and is flagged by ATC check "
            "SLIN_DB_ACCESS_TOO_MANY_ROWS. "
            "Migration fix: Add explicit WHERE conditions, use proper HANA-optimised "
            "indexes, replace SELECT * with explicit field lists. "
            "For reporting queries, consider CDS views with @Analytics annotations. "
            "Effort: 2–4 hours per program depending on query complexity."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "Performance/SELECT*", "priority": "high"},
    ),
    Document(
        page_content=(
            "CALL TRANSACTION inside ABAP programs using classic submit/return patterns "
            "is deprecated for Fiori-based S/4HANA. "
            "ATC check SLIN_OBSOLETE_STATEMENT identifies these occurrences. "
            "Migration fix: Replace with proper RFC calls, BAPIs, or OData service calls. "
            "For background processing replace with Application Jobs (SAP_NEW_JOB_SUBMIT). "
            "Effort: 1 day per program."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "CALL_TRANSACTION", "priority": "medium"},
    ),
    Document(
        page_content=(
            "BSEG table direct access is flagged by ATC in S/4HANA because BSEG "
            "is now a compatibility view over ACDOCA (Universal Journal). "
            "Direct BSEG reads work but are significantly slower than ACDOCA. "
            "Migration fix: Replace all SELECT FROM BSEG with SELECT FROM ACDOCA. "
            "Map BSEG fields to ACDOCA equivalents: BSCHL→BLART, HKONT→RACCT, etc. "
            "Effort: 4–8 hours per program. SAP Note: 2219714."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "BSEG_to_ACDOCA", "priority": "high"},
    ),
    Document(
        page_content=(
            "AUTHORITY-CHECK OBJECT missing or incorrect is flagged by ATC "
            "security check SCI_AUTHORITY_CHECK. In S/4HANA's Fiori context "
            "authorization checks are enforced strictly. "
            "Migration fix: Add proper AUTHORITY-CHECK statements for all sensitive "
            "database operations. Use SAP standard authorization objects "
            "(F_BKPF_BUK for FI, M_MSEG_BWA for MM, etc.). "
            "Effort: 2–3 hours per program."
        ),
        metadata={"source": "ATC Remediation Guide", "topic": "AUTHORITY_CHECK", "priority": "high"},
    ),
]


# ── SAP Simplification List ───────────────────────────────────────────────────

_SIMPLIFICATION_LIST_DOCS = [
    Document(
        page_content=(
            "SAP S/4HANA Simplification List is the official document listing all "
            "functional, technical, and data model changes from SAP ECC to S/4HANA. "
            "It covers: removed transactions, merged tables, deprecated function modules, "
            "mandatory new processes (Business Partner, Material Ledger, Universal Journal). "
            "The Simplification List must be reviewed in full during the Prepare phase. "
            "Available at: SAP Launchpad > SAP S/4HANA > Simplification Item Catalog."
        ),
        metadata={"source": "SAP Simplification List", "topic": "overview"},
    ),
    Document(
        page_content=(
            "Table MARA/MARC/MARD consolidation: In S/4HANA, material management tables "
            "MARA, MARC, MARD, MARM, MEAN are still present but MBEW is merged with "
            "new table MATDOC and material ledger is mandatory. "
            "Custom programs reading MARA with joins to MBEW must be updated to also "
            "query CKMLHD and CKMVFM for valuation data. "
            "Simplification item: S4TWL-MATERIAL_LEDGER."
        ),
        metadata={"source": "SAP Simplification List", "topic": "Material_Management_Tables"},
    ),
    Document(
        page_content=(
            "SKA1/SKB1 (G/L Account) tables are replaced by SKAT/FAGL_SPLINFO in S/4HANA. "
            "Custom code reading account master data must be updated. "
            "New G/L uses a single chart of accounts per company code. "
            "Profit center and segment are now mandatory fields in ACDOCA. "
            "Simplification item: S4TWL-FIN_GENERAL_LEDGER."
        ),
        metadata={"source": "SAP Simplification List", "topic": "General_Ledger"},
    ),
    Document(
        page_content=(
            "HR/HCM in S/4HANA: SAP HCM (PA, OM, Payroll) is available in S/4HANA "
            "as side-by-side deployment with SAP SuccessFactors or as on-premise. "
            "Infotypes 0001-0999 are unchanged. PA40/PA30 transactions remain. "
            "However, HR Renewal 2.0 UI is replaced by SAP Fiori apps. "
            "PCR (Personnel Calculation Rules) and payroll schemas carry over unchanged."
        ),
        metadata={"source": "SAP Simplification List", "topic": "HR_HCM"},
    ),
]


# ── Custom Code Best Practices ────────────────────────────────────────────────

_CUSTOM_CODE_DOCS = [
    Document(
        page_content=(
            "SAP Custom Code Migration Worklist (CCMW) is the recommended tool to "
            "analyse all Z/Y namespace objects before S/4HANA migration. "
            "It classifies objects as: 'Cannot be migrated', 'Must be adapted', "
            "'Can be used without changes'. "
            "Use transaction SCMG or the SAP Readiness Check output to get the CCMW. "
            "Focus first on objects classified 'Cannot be migrated' — these are "
            "go-live blockers."
        ),
        metadata={"source": "Custom Code Migration Guide", "topic": "CCMW"},
    ),
    Document(
        page_content=(
            "ABAP Unit Tests are mandatory for all adapted custom code in S/4HANA. "
            "Each adapted Z-program must have at least one ABAP Unit test class "
            "(CLASS ltcl_test DEFINITION FOR TESTING). "
            "Run ATC with check variant ABAP_UNIT to verify test coverage. "
            "Target: minimum 60% statement coverage for critical programs. "
            "Use transaction SE80 > Test > Unit Test to execute."
        ),
        metadata={"source": "Custom Code Migration Guide", "topic": "Unit_Testing"},
    ),
    Document(
        page_content=(
            "Classic ABAP patterns to modernise during S/4HANA migration: "
            "1. Replace FORM routines with methods in local/global classes. "
            "2. Replace FIELD-SYMBOLS with typed DATA references where possible. "
            "3. Replace SELECT .. ENDSELECT loops with SELECT INTO TABLE. "
            "4. Replace MOVE-CORRESPONDING with VALUE #( ) constructor expressions. "
            "5. Use inline declarations (DATA(lv_var)) for improved readability. "
            "These changes reduce future ATC findings and improve HANA performance."
        ),
        metadata={"source": "Custom Code Migration Guide", "topic": "ABAP_Modernisation"},
    ),
]


# ── Business Partner ──────────────────────────────────────────────────────────

_BUSINESS_PARTNER_DOCS = [
    Document(
        page_content=(
            "Business Partner (BP) is mandatory in SAP S/4HANA — Customer and Vendor "
            "master data must be converted to BP before go-live. "
            "Migration steps: "
            "1. Execute FLBP report to assign BP to existing customers/vendors. "
            "2. Verify BP roles: FLVN00 (Vendor) and FLCU00 (Customer). "
            "3. Check for duplicate business partners (transaction BP). "
            "4. Run consistency check via program BUPA_ONLINE_CHECK. "
            "SAP Note: 2265093. This step is a hard go-live prerequisite."
        ),
        metadata={"source": "Business Partner Migration Guide", "topic": "BP_Conversion"},
    ),
    Document(
        page_content=(
            "CVI (Customer-Vendor Integration) synchronisation must be activated "
            "before Business Partner conversion. "
            "Use transaction CVISETUP to check the synchronisation configuration. "
            "Custom code accessing KNA1 (customer) or LFA1 (vendor) tables directly "
            "should be updated to query BUT000 (BP header) and BUT020 (BP addresses). "
            "Existing KNA1/LFA1 data is still available via compatibility views in S/4HANA."
        ),
        metadata={"source": "Business Partner Migration Guide", "topic": "CVI_Sync"},
    ),
]


# ── Universal Journal ─────────────────────────────────────────────────────────

_UNIVERSAL_JOURNAL_DOCS = [
    Document(
        page_content=(
            "Universal Journal (table ACDOCA) is the single source of truth for all "
            "financial postings in SAP S/4HANA. It replaces the separate tables: "
            "BSEG (FI document segments), COEP (CO line items), BSIS/BSAS (index tables), "
            "FAGLFLEXA (new G/L). "
            "Field mapping: BSEG.HKONT → ACDOCA.RACCT, BSEG.BUKRS → ACDOCA.RBUKRS, "
            "BSEG.WRBTR → ACDOCA.WRBTR_LOC. "
            "All custom FI reports must be validated against ACDOCA after migration."
        ),
        metadata={"source": "Universal Journal Guide", "topic": "ACDOCA_Migration"},
    ),
    Document(
        page_content=(
            "CO-PA (Controlling Profitability Analysis) in S/4HANA is replaced by "
            "Margin Analysis based on ACDOCA. "
            "Account-based CO-PA is the only supported variant in S/4HANA. "
            "Costing-based CO-PA can run in parallel but is not recommended for new setups. "
            "Custom reports reading CE1XXXX tables must be rewritten to use ACDOCA "
            "with profit centre and segment fields. "
            "Simplification item: S4TWL-COPA."
        ),
        metadata={"source": "Universal Journal Guide", "topic": "COPA_Migration"},
    ),
]


# ── Material Ledger ───────────────────────────────────────────────────────────

_MATERIAL_LEDGER_DOCS = [
    Document(
        page_content=(
            "Material Ledger (ML) activation is mandatory in SAP S/4HANA for all plants. "
            "ML provides multi-currency and multi-valuation inventory accounting. "
            "Migration steps: "
            "1. Transaction CKMVFM: Define valuation variants. "
            "2. Transaction CKMSTART: Activate ML per plant. "
            "3. Run initial stock valuation with transaction MR21 if needed. "
            "4. Validate CKMLHD (ML header) and CKMVFM entries. "
            "This step must be completed before financial period close cutover."
        ),
        metadata={"source": "Material Ledger Guide", "topic": "ML_Activation"},
    ),
    Document(
        page_content=(
            "Actual Costing with Material Ledger in S/4HANA: "
            "All price differences are settled to materials at period end via CKMLCP. "
            "Custom programs using MBEW for price lookups must be updated to use "
            "the ML price from CKMLHD.STPRS or CK11N standard price. "
            "Moving average price (MAP) in MBEW.VERPR is updated in real time "
            "through ML postings in MATDOC."
        ),
        metadata={"source": "Material Ledger Guide", "topic": "Actual_Costing"},
    ),
]


# ── Cutover Planning ──────────────────────────────────────────────────────────

_CUTOVER_DOCS = [
    Document(
        page_content=(
            "SAP S/4HANA cutover planning best practices: "
            "1. Plan for minimum 2 full mock cutover rehearsals before production. "
            "2. Define go/no-go decision criteria (max outstanding P1 defects: 0, P2: <5). "
            "3. Freeze source system transports 2 weeks before cutover weekend. "
            "4. Use SUM (Software Update Manager) for the system conversion — allow "
            "   60–90 hours of downtime for large ECC systems (>5TB). "
            "5. Run SPDD/SPAU adjustments for all modified SAP standard objects. "
            "6. Take a full system backup (BRBACKUP) immediately before SUM execution."
        ),
        metadata={"source": "Cutover Best Practices", "topic": "Cutover_Planning"},
    ),
    Document(
        page_content=(
            "SUM (Software Update Manager) is the tool used to perform the technical "
            "system conversion from SAP ECC to S/4HANA. "
            "Key SUM phases: Extraction → Checks → ShadowRepo → Downtime → Post-processing. "
            "Pre-requisites: SAP kernel 7.89+, ABAP stack, HANA DB certified for target release. "
            "The downtime window starts at the 'Downtime' phase. "
            "Run SUM with parameter ABAP=YES DMO=YES for database migration option "
            "if converting from non-HANA DB simultaneously."
        ),
        metadata={"source": "Cutover Best Practices", "topic": "SUM_Tool"},
    ),
    Document(
        page_content=(
            "Rollback plan for SAP S/4HANA cutover: "
            "A rollback is only possible before SUM's point of no return (tenant conversion). "
            "Before cutover: Take OS-level backup and SAP HANA backup. "
            "Rollback trigger criteria: SUM failure after 50% of downtime elapsed, "
            "or critical data inconsistencies detected in post-conversion checks. "
            "Rollback steps: Restore HANA backup, restore filesystems, restart ECC instance, "
            "re-open business systems. Total rollback time: typically 4–6 hours."
        ),
        metadata={"source": "Cutover Best Practices", "topic": "Rollback_Plan"},
    ),
]


# ── Runbook Best Practices ────────────────────────────────────────────────────

_RUNBOOK_BEST_PRACTICES_DOCS = [
    Document(
        page_content=(
            "SAP S/4HANA migration project phases (SAP Activate methodology): "
            "1. Discover — Business case, system landscape review, SAP Readiness Check. "
            "2. Prepare — Project setup, sandbox conversion, tool installation. "
            "3. Explore — Fit-gap analysis, custom code scan, simplification review. "
            "4. Realize — Custom code adaptation, configuration, data migration. "
            "5. Deploy — UAT, integration testing, cutover rehearsals. "
            "6. Run — Go-live, hypercare, BAU transition. "
            "Typical timeline for a mid-size ECC: 12–18 months."
        ),
        metadata={"source": "SAP Activate Methodology", "topic": "Migration_Phases"},
    ),
    Document(
        page_content=(
            "SAP Readiness Check 2.0 is the starting point for every S/4HANA migration. "
            "It analyses the source ECC system and produces: "
            "- Custom code impact (CCMW) "
            "- Simplification item relevance "
            "- Add-on compatibility check "
            "- Business function status "
            "- Sizing recommendation for HANA hardware "
            "Run the Readiness Check at least 6 months before planned go-live. "
            "Available via SAP Launchpad or embedded in SAP Solution Manager."
        ),
        metadata={"source": "SAP Activate Methodology", "topic": "Readiness_Check"},
    ),
    Document(
        page_content=(
            "Integration testing for S/4HANA migration should cover: "
            "1. All RFC destinations (SM59) — verify connectivity post-migration. "
            "2. IDoc interfaces — test inbound and outbound message types. "
            "3. BAPIs — run regression tests for all custom BAPI wrappers. "
            "4. Web Services / REST APIs — re-test all external API consumers. "
            "5. SAP Process Integration / Integration Suite — update endpoints for new host. "
            "Use SAP Solution Manager Test Suite or HP ALM for test management."
        ),
        metadata={"source": "Integration Testing Guide", "topic": "Integration_Testing"},
    ),
    Document(
        page_content=(
            "Hypercare support model for SAP S/4HANA go-live: "
            "Week 1–2: 24/7 war room with BASIS, ABAP, functional leads on-site. "
            "Week 3–4: Business hours extended support (07:00–22:00). "
            "Week 5–8: Standard SLA with accelerated P1/P2 response times. "
            "Key activities: daily system health checks (SM21, SM58, SMLG), "
            "batch job monitoring (SM37), HANA performance monitoring (HANA Studio). "
            "Escalation path: Project Manager → SAP Premium Engagement → SAP Support."
        ),
        metadata={"source": "Hypercare Guide", "topic": "Hypercare"},
    ),
]


# ── Security ──────────────────────────────────────────────────────────────────

_SECURITY_DOCS = [
    Document(
        page_content=(
            "SAP S/4HANA security hardening during migration: "
            "1. Review all critical authorisation objects (SU24 upgrade). "
            "2. Disable SAP* and DDIC users in production after go-live. "
            "3. Activate SAP HANA user management — no DB passwords in plain text. "
            "4. Enable SAL (SAP Application Log) for all sensitive RFC calls. "
            "5. Run Security Audit Log (SM19) for all privileged users. "
            "6. Remove all custom authorisation bypasses (AUTHORITY-CHECK DUMMY). "
            "SAP Note: 1616121 (Security Baseline Recommendations)."
        ),
        metadata={"source": "S/4HANA Security Guide", "topic": "Security_Hardening"},
    ),
    Document(
        page_content=(
            "RFC security in SAP S/4HANA: "
            "All RFC connections must use TLS 1.2 or higher (SAP Note 510007). "
            "Trusted RFC connections (login/no password) should be minimised and audited. "
            "Use SAP Connection Security tool (transaction SMGW) to review RFC gateways. "
            "Remove all RFC destinations with type 3 (ABAP) using generic user IDs. "
            "Replace with specific technical users with minimum authorisations."
        ),
        metadata={"source": "S/4HANA Security Guide", "topic": "RFC_Security"},
    ),
]


# ── Performance ───────────────────────────────────────────────────────────────

_PERFORMANCE_DOCS = [
    Document(
        page_content=(
            "HANA performance optimisation for custom ABAP code in S/4HANA: "
            "1. Use HANA-specific SQL features: SERIES_GENERATE, STRING_AGG, RANK(). "
            "2. Push calculations to HANA using CDS views with @Analytics.query. "
            "3. Avoid ABAP-side loops over large result sets — use GROUP BY in SQL. "
            "4. Use AMDP (ABAP Managed Database Procedures) for complex HANA logic. "
            "5. Use secondary indexes for custom Z-tables based on query patterns. "
            "6. Monitor with SAP HANA Performance Analysis cockpit (transaction /SDF/SMON)."
        ),
        metadata={"source": "HANA Performance Guide", "topic": "HANA_Performance"},
    ),
    Document(
        page_content=(
            "CDS (Core Data Services) views in S/4HANA replace many classic transparent table "
            "accesses and cluster table joins. "
            "Key CDS annotations for migration: "
            "@AbapCatalog.sqlViewName: physical SQL view on HANA "
            "@Analytics.query: true — creates an analytical query for embedded analytics "
            "@VDM.viewType: #BASIC / #COMPOSITE / #CONSUMPTION layer architecture. "
            "Custom reports should be converted to consume VDM CDS views "
            "rather than querying raw tables for better upgrade stability."
        ),
        metadata={"source": "HANA Performance Guide", "topic": "CDS_Views"},
    ),
]
