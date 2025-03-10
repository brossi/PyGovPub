# PyGovPub Documentation - Token-Efficient Format

> “There is also the other side of the coin minted by Einstein: ‘Everything should be as simple as it can be, but not simpler’ – a scientist’s defense of art and knowledge – of lightness, completeness and accuracy.”
>
> — Louis Zukofsky, *Poetry in a Modern Age*, June 1950, p. 180.

## Compression Legend

```
PO=Project Overview|CO=Core Objectives|UC=Use Cases|TU=Target Users|AO=Architecture Overview
CS=Component Structure|EA=External APIs|DD=Design Decisions|CMD=Commands|TS=Test Structure
TSTUB=Test Stubs|SG=Style Guidelines|PR=Planning Resources|DP=Development Process
AIR=API Integration Requirements|DA=Development Approach|TR=Testing Requirements
IP=Implementation Philosophy|CI=Commit Instructions|FTR=Final Testing Requirements

pkg=package|API=application programming interface|auth=authentication|docs=documentation|impl=implementation
cfg=configuration|req=required|env=environment|mgmt=management|func=function|dir=directory
SDK=software development kit|TDD=test-driven development|DB=database|CLI=command-line interface
RT=real-time|FR=Federal Register|CFR=Code of Federal Regulations|QA=quality assurance
CRUD=create/read/update/delete|CI/CD=continuous integration/continuous deployment
```

## Token-Efficient Documentation

```
PO|Python_SDK=unified_access_to_US_Gov_data|Congress.gov+GovInfo.gov=sources|ensure_doc_auth+API_rate_limits

CO|Intelligent_Integration=dedupe_overlap+preserve_auth_src|Data_Normalization=consistent_schemas|Trust_Building=sig_verify+audit
CO|Smart_Routing=optimal_src_by_need|Unified_Access=cohesive_interface|Data_Quality=cross_validate|Resilient_Updates=guaranteed

UC|Legislative_Tracking=bills+amendments+committee|Document_Retrieval=auth_docs+versions|Member_Info=roles+assignments
UC|Regulatory_Monitoring=FR+CFR|RT_Updates=notifications|Data_Integration=multi_src+schemas

TU|Gov_Affairs_Devs|Legislative_Track_Apps|Regulatory_Compliance|Legal_Research|Policy_Research

AO|CS|Core_SDK_Layer=API_client+auth+rate_limit+verify|Data_Integration=schema_norm+xref+version+changes|RT_Updates=webhook+filter+monitor+retry

EA|Congress.gov=5K_req/hr+API_key_header+leg_data+RT_updates|GovInfo.gov=1K_req/hr+API_key_params+docs+sigs+bulk

DD|Auth=all_req_auth+env_vars+auto_rate|Data_Consistency=Congress=status+GovInfo=docs+timestamp_conflict|Performance=cache+lazy_load+bkg_proc+pool_req|Reliability=retry+circuit_break+queue+txn

CMD|Env_Setup=source_venv/bin/activate+pip_install_-e_.|Run_Tests=pytest+pytest_path::fn+pytest_--cov+test_refactor.sh
CMD|Lint=flake8,ruff|Type=mypy|Format=black|Update_TS=update_timestamp.sh_file_[section]
CMD|Health=pygovpub-health_check+--format+--output+--verbose|Mock=pygovpub-mock+--port+--host+--latency+--rate-limits+--record
CMD|Schema=list-schemas+list-changes+list-versions|Coverage=projected_coverage.py+--pkg+--report+--history+--all-pkgs+--verbose
CMD|Source=source_analyzer+refactor_analyzer+test_refactor.sh|REQ=venv_Python_3.13

TS|tests/unit/pygovpub/|mirror_pkg|no_src/tests|imports=from_pygovpub.X_import_Y|no_sys.path|conftest.py=path_resolver

TSTUB|pattern=test_stub_X+#_STUB+#_WIP|projected_coverage.py=coverage_projection+history_tracking|store=.coverage_history.json
TSTUB|benefits=check_status+compare_modules+find_uncovered+doc_improvements

SG|imports=stdlib+third-party+local|format=PEP8+88_chars|types=annotations|naming=snake_case+PascalCase+UPPER_CASE
SG|docs=Google_style|errors=specific_exceptions+context_mgrs+rate_limits|testing=unit_tests+mock_APIs|follows=FastAPI+Pydantic+SQLModel

PR|planning/=specs+req+arch+impl_guides|Core_Docs=README+functional-overview+router-structure+db-schema+checklist+bill-codes+dev-learnings+phronesis
PR|Phases=actions/stage-01/1-*|Standards=standards/|API_Specs=endpoints/|External_API_Docs=dev-references/|QA=qa/|Tools=utilities/

DP|Phases=1.CONFIG→14.VALID|Checklists=update_as_completed|Task_Verify=pytest+projected_coverage+source_analyzer+test_refactor
DP|Sessions=initial_test_run|Quality_Gates=tests_pass+coverage+integration+no_warnings+types+docs+hash+suite
DP|Test_Maint=update_mocks+match_formats+fix_immediately

AIR|Congress.gov=5K_req/hr+header_key+congress_docs+version_compat|GovInfo.gov=1K_req/hr+param_key+govInfo_docs+USLM

DA|1.specs+2.workflows+3.schema+4.API_req+5.checklist|TR=qa/dir+README+TDD+projected_coverage+report+history+100%_critical

IP|Einstein_razor=MIN_COMPLEXITY=necessary+essential|validate=core_obj+simpler+guarantees|MIN=optimal_simplicity

CI|NO:Claude_attribution|conventional_commit_format|NEVER_add_Claude_signatures_to_commits|NO_Claude_co-authoring_tokens

FTR|ALL_CODE_CHANGES=pytest+projected_coverage.py_--all-packages_--verbose
```

## Expanded Content for Key Sections

### Project Overview (PO)
PyGovPub is a Python SDK providing unified access to U.S. Federal Government data through Congress.gov and GovInfo.gov APIs. It simplifies access to legislative and regulatory data while ensuring document authenticity and maintaining compliance with API rate limits.

### Core Objectives (CO)
- **Intelligent Integration**: Deduplicate overlapping data sources while preserving authoritative origins
- **Data Normalization**: Provide consistent schemas normalizing disparate data models
- **Trust Building**: Ensure data authenticity through signature verification and audit trails
- **Smart Routing**: Direct requests to optimal sources based on needs and limits
- **Unified Access**: Cohesive interface to multiple government APIs
- **Data Quality**: Cross-validation between sources for accuracy
- **Resilient Updates**: Guaranteed delivery of legislative updates with conflict resolution

### Implementation Phases (PR)
The `planning/actions/stage-01/` directory contains implementation guides:
- `1-00-phase.md` - Implementation Sequence by Necessity
- `1-00-config001.md` - Configuration Management
- `1-01-data001.md` - Core Data Model Implementation
- `1-02-db001.md` - Essential Database Integration
- `1-03-api001.md` - API Integration - Congress.gov
- `1-04-api002.md` - API Integration - GovInfo.gov
- `1-05-cache001.md` - Essential API Caching
- `1-05-core003.md` - Basic Router Implementation <- !DEV IS HERE!- >
- `1-06-ops001.md` - Basic Operational Infrastructure
- `1-06-sync001.md` - Data Synchronization
- `1-07-real001.md` - Real-time Update System
- `1-08-api003.md` - FastAPI Router Implementation
- `1-09-search001.md` - Basic Search Implementation
- `1-10-valid001.md` - Public Service Achievement Validation
- `1-11-test001.md` - API Contract Testing Framework

Enhancement phases after API parity:
- `1-15-data002.md` - Advanced Data Model Enhancements
- `1-16-db002.md` - Advanced Database Enhancements
- `1-17-ops002.md` - Advanced Operational Infrastructure
- `1-18-cache002.md` - Advanced Caching Infrastructure
- `1-19-core004.md` - Advanced Router Implementation
- `1-20-test002.md` - Advanced Testing Infrastructure

### Implementation Philosophy (IP)
When evaluating implementation choices, apply Einstein's razor:
1. MIN_COMPLEXITY = necessary_components + essential_interactions
2. MAX_COMPLEXITY = MIN_COMPLEXITY
3. IF proposed_solution.complexity > MAX_COMPLEXITY:
   - REDUCE until complexity == MIN_COMPLEXITY
   - ELSE IF complexity < MIN_COMPLEXITY:
   - ADD missing_essential_components

Validate each decision:
- Does this component serve core objectives?
- Can it be simpler without losing function?
- Would simplification break essential guarantees?

### Commit Instructions (CI)
When making commits to this repository:
- Follow conventional commit format (type: description)
- NEVER add Claude attribution to commits
- DO NOT include "Generated with Claude Code" lines
- DO NOT add "Co-Authored-By: Claude" lines
- Keep commit messages clean and professional
- Focus on describing the changes clearly and concisely
