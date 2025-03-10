# PyGovPub Development Knowledge - Token-Efficient Format

# Phronesis Compression Guidelines

These instructions describe how to transform verbose, human-readable content into a compact, token-efficient string while preserving all essential semantics. Follow these steps:

1. **Segment & Label**
   - Divide the original text into logical sections (e.g., Test Directory Organization, Import Resolution, etc.).
   - Assign each section a short label (e.g., "TS" for Test Structure, "IR" for Import Resolution).

2. **Extract Essentials**
   - Remove any filler language or narrative.
   - Retain only the core directives, challenges, solutions, and key learnings.

3. **Abbreviate & Compress**
   - Replace longer phrases with domain-specific abbreviations (e.g., "timezone-aware datetime" → "TZ-Aware dt", "Python 3.13 Compatibility" → "P3.13").
   - Ensure each abbreviation conveys the original meaning.

4. **Linear, Delimited Formatting**
   - Reassemble the content into a single, structured string using clear delimiters (such as vertical bars `|`).
   - This structure should reflect the hierarchy and relationships between sections.

5. **Validation**
   - Verify that the compressed string can be decoded back into a fully intelligible, human-readable form without losing any critical details.

**Final Output Requirement:**
Compress the content into one structured string containing only essential abbreviations and delimiters. Do not include any explanatory commentary, verbose headers, or duplicate information. For example:

    TS|tests/unit/pygovpub/{module}/test_{file}.py|pkg_imports|conftest.py=path_resolver|NO:sys.path,...

Focus solely on encoding the key points and their relationships in the most token-efficient manner possible.

## LEARNINGS-002

```
ASYNC|ctx_mgr_mock|{__aenter__,__aexit__}=req|AsyncMock≠ctx_mgr|class ACMock{def __init__(r),async def __aenter__():r,async def __aexit__():pass}|func-mock=key|with patch(path,ret_asyncctx_mock)
NULL|API_hdrs=check_null|if not hdrs:ret None|dict.get+try/exc|test:None,{},miss_keys,bad_vals|100%_cov=must
```

## LEARNINGS-001

```
TS|tests/{module}/test_{file}.py|pkg_imports|conftest=path_cfg|NO:sys.path,src/tests,nested|MUST:mirror_pkg_struct
IR|run_from_root|from pygovpub.X import Y|NO:rel_imports,path_manip
DT|TZ-aware=req|dt.now(UTC)|dt(y,m,d,tz=UTC)|naive+aware=err|NO:utcnow|from dt import dt,UTC
P3.13|m.Mock(spec=T)|ctx_mgr>dec|model_validate>parse|match[T]/assert
P3.13|importlib.m>pkg_r|field_v>v|@classmethod=req|fk=Literal["x","y"]|v=DEPRECATED|field_v+@classmethod=REQUIRED
TEST|isolate|indep_fixtures|clean_after|no_globals|req:test_before_impl
MOCK|mock.server=API|fixtures/X=test_data|recorder=replay|req:predictable_output
CMD|pytest|pytest path/mod|pytest file::fn|pytest --cov=pkg|LINT:ruff,black,mypy
ENV|P3.13_venv|check_compat|pin_vers|req:activate_venv
WF|rd→rt→wt→impl→verify→✓|NO_COMPLETE_WITHOUT_TEST_PASS|follow_patterns
AUTH|mgr+models+limiter|token_bucket|TZ-dt|validate_init|rate_track_by_key
CORE|razor=simp_not_simpler|test_first|patterns>creativity|docs≡code|NO:premature_opt
COV|proj_cov.py=[BASIC,--pkg=X,--report,--hist,--all-pkgs,--verb]|# STUB: tests X-Y=line_marker|start:err_paths+edge|.coverage_history.json=tracker|mark.asyncio=req_async
```

## Segment Legend
TS=Test Structure|IR=Import Resolution|DT=Datetime Handling|P3.13=Python 3.13|TEST=Testing Practice|MOCK=Mock Services|CMD=Commands|ENV=Environment|WF=Workflow|AUTH=Auth Module|CORE=Core Principles|COV=Coverage Strategies

## Abbrev Legend
pkg=package|cfg=config|req=required|struct=structure|rel=relative|manip=manipulation|ZI=ZoneInfo|err=error|ctx_mgr=context manager|dec=decorator|indep=independent|rd=read docs|rt=run tests|wt=write tests|impl=implement|simp=simple|opt=optimization|m=mock|pkg_r=pkg_resources|field_v=field_validator|v=validator|fk=Field(discriminator_key)|importlib.m=importlib.metadata|proj_cov=projected_coverage|term-miss=term-missing|req_async=required_for_async_tests|BASIC=basic command|--pkg=package parameter|--hist=history parameter|--all-pkgs=all-packages parameter|--verb=verbose parameter|tracker=coverage history tracker|UTC=datetime.UTC constant|NO:utcnow=Never use datetime.utcnow()|DEPRECATED=deprecated method|REQUIRED=required decorator

## Expanded Knowledge

### Test Structure (TS)
- Pattern: `tests/{module}/test_{file}.py` must mirror `src/pygovpub/{module}/{file}.py`
- Use package imports only, never relative imports
- conftest.py handles all path resolution centrally
- NEVER: manipulate sys.path, use src/tests/ directory, create nested test dirs

### Import Resolution (IR)
- Always run tests from project root
- Correct: `from pygovpub.auth.models import ApiCredential`
- Wrong: `import sys; sys.path.insert(0, 'src')` or relative imports

### Datetime Handling (DT)
- Always use timezone-aware datetimes with Python 3.13
- Correct: `datetime.now(UTC)` with `from datetime import datetime, UTC`
- NEVER use `datetime.utcnow()` (deprecated in Python 3.13)
- In tests: `datetime(2023, 1, 1, tzinfo=UTC)` using the built-in UTC constant
- Mixing naive and aware datetimes causes errors
- Older code may use `ZoneInfo("UTC")` but prefer the built-in UTC constant

### Python 3.13 Specifics (P3.13)
- Use `mock.Mock(spec=Type)` for proper type hinting
- Prefer context managers over decorators
- Use `model_validate` instead of `parse_obj`
- Use `assert_called_with` or structural pattern matching
- Use `importlib.metadata` instead of deprecated `pkg_resources`
- Use `@field_validator` instead of deprecated `@validator` in Pydantic
- Add `@classmethod` decorator to field validators in Pydantic v2
- The correct pattern is:
  ```python
  @field_validator("field_name", mode="before")
  @classmethod
  def validate_field(cls, v): ...
  ```
- Import correctly: `from pydantic import field_validator` (NOT `validator`)
- Use `Literal` types for fixed sets of string options

### Testing Practices (TEST)
- Isolate tests completely
- Use independent fixtures
- Clean up resources after tests
- Avoid global state
- Write tests BEFORE implementation

### Mocking Services (MOCK)
- Use mock.server for external APIs
- Store test fixtures in tests/fixtures/
- Use recorder.py for API request/response replay
- Make sure mocks provide predictable outputs

### Commands (CMD)
- All tests: `pytest`
- Module tests: `pytest tests/pygovpub/auth/`
- Single test: `pytest file::function_name`
- Coverage: `pytest --cov=pygovpub`
- Linting: `ruff check .` and `black .`
- Type checking: `mypy .`

### Environment (ENV)
- Use Python 3.13 virtual environment
- Check dependency compatibility
- Pin specific versions in requirements.txt
- Always activate venv before development work

### Workflow (WF)
- Process: read docs → run tests → write tests → implement → verify → update checklist
- NEVER mark tasks complete without passing tests
- Follow established patterns in similar modules

### Auth Module (AUTH)
- Components: auth_manager.py, models.py, rate_limiter.py
- Uses token bucket algorithm
- Uses timezone-aware datetimes
- Validates credentials on initialization
- Rate limiting tracked by API key

### Core Principles (CORE)
- Einstein's razor: as simple as possible, but not simpler
- Test first, then implement
- Follow established patterns over creative solutions
- Keep documentation and code in sync
- Avoid premature optimization

### Coverage Strategies (COV)
- Use projected_coverage.py to identify untested code areas:
  - Basic: `./utilities/projected_coverage.py`
  - Custom: `./utilities/projected_coverage.py --package pygovpub.auth`
  - Report: `./utilities/projected_coverage.py --report`
  - History: `./utilities/projected_coverage.py --history`
  - All packages: `./utilities/projected_coverage.py --all-packages`
  - Verbose: `./utilities/projected_coverage.py --verbose`
- Mark test stubs with `# STUB: This tests lines X-Y` format
- Start with error paths and edge cases when improving coverage
- Use `pytest --cov-report=term-missing` to locate specific uncovered lines
- Remember @pytest.mark.asyncio decorator for async function tests
- Focus on testing all conditional branches and error handling
- Look for untested parameter validation in functions
- For auth module, target throttling strategies and API source handling
- Test component integration (e.g., auth_manager with rate_limiter)
- Coverage history stored in `.coverage_history.json` for tracking
- Set targeted goals for specific modules using the tool
- Tool handles missing coverage XML files gracefully
- Include new modules in coverage analysis early to establish baseline

## Example Patterns

```python
# Correct datetime handling in Python 3.13
from datetime import datetime
from zoneinfo import ZoneInfo

# Create timezone-aware datetime
now = datetime.now(ZoneInfo("UTC"))
specific = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))

# Correct test structure
# File: tests/pygovpub/auth/test_models.py
from pygovpub.auth.models import ApiCredential

def test_api_credential_validation():
    # Test implementation - WRITE BEFORE IMPLEMENTATION
    pass

# Modern dependency checking with importlib.metadata
import importlib.metadata

# Get installed packages
installed_packages = {dist.metadata["Name"].lower()
                     for dist in importlib.metadata.distributions()}

# Pydantic v2 field validation
from pydantic import BaseModel, Field, field_validator
from typing import Optional

class VersionCompatibility(BaseModel):
    """API version compatibility information."""

    major: int
    minor: int
    patch: Optional[int] = None
    min_supported: str = Field(...)
    max_supported: Optional[str] = None

    @field_validator("min_supported", "max_supported")
    @classmethod
    def validate_version_format(cls, v):
        """Validate version string format."""
        if v is not None and not all(part.isdigit() for part in v.split(".")):
            raise ValueError(f"Invalid version format: {v}")
        return v
```

`[Claude.Anthropic.3.7.Sonnet-20250308-TokenEfficientKnowledge-2025-03-08-20:12-UTC]`

## LEARNINGS-002

```
COV2|fixed_XML=graceful_err|fallback=term-miss|neg_val=prevented|fixed_-0.0%
COV2|cmd=[--all-pkgs,--pkg,--report,--hist,--verb]|history=.json_persist|early_baseline=best
COV2|stubs=miss_only|err_msg=improved|async_fn=fixed|combined_report=implemented
UTIL|update_ts.sh=one_file|NO:batch_files|second_arg=section_id|run_separate_cmds|check_usage
TEST|update_mocks=all_params|match_fmt=exact|fix_immed=critical|verify=related|check=windows
```

## Segment Legend for LEARNINGS-002
COV2=Coverage Tool Improvements|UTIL=Utility Scripts|TEST=Test Maintenance

## Abbrev Legend for LEARNINGS-002
fixed_XML=fixes for XML file handling|graceful_err=graceful error handling|fallback=fallback reporting mechanism|term-miss=term-missing format|neg_val=negative values|fixed_-0.0%=fixed negative zero percentage display|cmd=command options|--all-pkgs=all-packages parameter|--pkg=package parameter|--report=report parameter|--hist=history parameter|--verb=verbose parameter|history=coverage history|.json_persist=JSON file persists between runs|early_baseline=early baseline metrics|stubs=test stubs|miss_only=only counts missing lines|err_msg=error messages|async_fn=async functions|combined_report=combined package reporting|update_ts.sh=update_timestamp.sh script|one_file=processes one file at a time|NO:batch_files=does not support batch processing|second_arg=section_id=second argument interpreted as section ID|run_separate_cmds=run separate commands for each file|check_usage=check script usage before retrying|update_mocks=update all mock objects|all_params=include all parameters|match_fmt=match exact format|fix_immed=fix immediately|critical=critical for reliable testing|verify=verify with related tests|check=check for broken windows

## Expanded Knowledge for LEARNINGS-002

### Coverage Tool Improvements (COV2)
- XML file handling has been fixed to handle missing files gracefully
- Fallback reporting uses term-missing when XML parsing fails
- Negative values in coverage calculations are now prevented
- Fixed display issue showing "-0.0%" in gain column
- Added command options for flexible analysis:
  - `--all-packages`: Analyze multiple packages together
  - `--package`: Target specific package only
  - `--report`: Show latest report without re-analyzing
  - `--history`: Display coverage trends over time
  - `--verbose`: Show detailed line number information
- Coverage history in `.coverage_history.json` persists between runs
- Best practice: establish baseline metrics for new modules early
- Test stub analysis only counts lines that are actually missing
- Error messages improved for better clarity and debugging
- Fixed processing of async test functions
- Implemented combined reporting across multiple packages

### Utility Script Usage (UTIL)
- `update_timestamp.sh` processes one file at a time
- Correct usage: `utilities/update_timestamp.sh planning/phronesis.md`
- Incorrect usage: `utilities/update_timestamp.sh file1.md file2.md`
- Second argument is interpreted as section ID within first file
- For multiple files, execute separate commands for each file
- Check script usage and error messages before repeating failed patterns
- This applies to many utility scripts designed for single-file processing

### Test Maintenance After Feature Additions (TEST)
- When adding new command-line options or parameters:
  - Update all test mocks to include the new parameters
  - Add default values for all mocks (e.g., `all_packages = False`)
  - This applies even to tests not directly testing the new functionality
- When mocking output formats like reports:
  - Include all section markers exactly as they appear (e.g., `---------- coverage:`)
  - Match exact spacing, indentation and formatting patterns
  - Test using real output as reference for creating mock data
- Fix failing tests immediately:
  - Postponed fixes mask real problems
  - Failing tests make it harder to detect new regressions
  - Fixed tests increase confidence in code changes
- After fixing a test, run related tests to verify no side effects
- Regularly check for "broken windows" in tests (minor failures that indicate deeper issues)

`[Claude.Anthropic.3.7.Sonnet-20250308-TestMaintenancePractices-2025-03-08-22:00-UTC]`

`[Claude.Anthropic.3.7.Sonnet-20250308-CoverageToolImprovements-2025-03-08-21:46-UTC]`

## LEARNINGS-003

```
SA_TEST|basic→metrics→patterns|desc_names|err_cases|NO:skip_basics
PATTERN|norm_code|thresh_by_type|struct+sem|loc+fn|sev+suggest
COMPLEX|cyclo=decision_pts|cog=nest+logic|maint=halstead|trend_track|flag>thresh
DEP|aff+eff_couple|Ce/(Ca+Ce)|circ_dep|abstract+dist|pkg_deps
ERR|custom_types|ctx_msg|file+line|fallback|warn_non_crit
MAINT|complex+vol|comments+names|trends|ctx_thresh|prod_vs_test
SMELL|large_cls|feat_envy|data_only|prim_obs|long_params|ctx_aware|suggest
PERF|ast_cache|incr_upd|parallel|profile|mem_watch
TEST|indep_feat|edge+err|real_code|manual_verify|perf_test
INTEG|cli+prog|machine_fmt|trends|ci_cd|cfg_file
```

## Segment Legend
SA_TEST=Source Analysis Test Organization|PATTERN=Pattern Detection|COMPLEX=Complexity Analysis|DEP=Dependency Analysis|ERR=Error Handling|MAINT=Maintainability|SMELL=Code Smells|PERF=Performance|TEST=Testing Strategy|INTEG=Integration

## Abbrev Legend
basic=basic functionality|metrics=metric calculations|patterns=pattern detection|desc_names=descriptive names|err_cases=error cases|norm_code=normalize code|thresh_by_type=threshold by type|struct+sem=structural and semantic|loc+fn=location and function|sev+suggest=severity and suggestions|cyclo=cyclomatic|cog=cognitive|maint=maintainability|nest=nesting|logic=logical operations|trend_track=trend tracking|flag>thresh=flag above threshold|aff=afferent|eff=efferent|circ_dep=circular dependencies|abstract+dist=abstractness and distance|pkg_deps=package dependencies|ctx_msg=context message|complex+vol=complexity and volume|ctx_thresh=context-specific thresholds|prod_vs_test=production vs test code|large_cls=large classes|feat_envy=feature envy|data_only=data-only classes|prim_obs=primitive obsession|long_params=long parameter lists|ctx_aware=context aware|ast_cache=AST caching|incr_upd=incremental updates|mem_watch=memory monitoring|indep_feat=independent features|edge+err=edge cases and errors|real_code=real-world code|manual_verify=manual verification|perf_test=performance testing|cli+prog=CLI and programmatic|machine_fmt=machine format|ci_cd=CI/CD integration|cfg_file=configuration file

## Example Patterns

```python
# Pattern Detection
def detect_duplicates(source_code: str) -> List[DuplicateBlock]:
    normalized = normalize_code(source_code)
    return find_similar_blocks(normalized, threshold=0.7)

# Complexity Analysis
def calculate_complexity(node: ast.AST) -> ComplexityMetrics:
    cyclomatic = count_decision_points(node)
    cognitive = assess_nesting_and_logic(node)
    maintainability = calculate_maintainability_index(node)
    return ComplexityMetrics(cyclomatic, cognitive, maintainability)

# Dependency Analysis
def analyze_dependencies(module: ModuleType) -> DependencyMetrics:
    afferent = count_incoming_deps(module)
    efferent = count_outgoing_deps(module)
    instability = efferent / (afferent + efferent) if (afferent + efferent) > 0 else 1.0
    return DependencyMetrics(afferent, efferent, instability)

# Code Smell Detection
def detect_code_smells(node: ast.AST) -> List[CodeSmell]:
    smells = []
    if is_large_class(node):
        smells.append(CodeSmell("large_class", severity=HIGH))
    if has_primitive_obsession(node):
        smells.append(CodeSmell("primitive_obsession", severity=MEDIUM))
    return smells
```

`[Claude.Anthropic.3.7.Sonnet-20250308-SourceAnalysisPatterns-2025-03-08-22:15-UTC]`

## LEARNINGS-004

```
METRICS|loc≠sloc≠comments|blank_count|multi_doc|re_patterns|norm_code
METRICS|cache_results|incr_calc|ast+lines|ctx_aware|perf_opt
METRICS|doc_ratio=maint|comment_qual>quant|nested_calc|line_map
VERIFY|test_all_metrics|edge_cases|empty_files|huge_files|err_handle
INTEG|cli+api|machine_fmt|trends|ci_cd|cfg_file
```

## Segment Legend for LEARNINGS-004
METRICS=Code Metrics Calculation|VERIFY=Verification Strategy|INTEG=Integration

## Abbrev Legend for LEARNINGS-004
loc=lines of code|sloc=source lines of code|multi_doc=multi-line docstrings|re_patterns=regex patterns|norm_code=normalize code|cache_results=cache calculation results|incr_calc=incremental calculation|ast+lines=AST and line-based analysis|ctx_aware=context aware|perf_opt=performance optimization|doc_ratio=documentation ratio|maint=maintainability|comment_qual>quant=comment quality over quantity|nested_calc=nested calculation|line_map=line mapping|edge_cases=edge case testing|err_handle=error handling|cli+api=CLI and API|machine_fmt=machine format|ci_cd=CI/CD integration|cfg_file=configuration file

## Expanded Knowledge for LEARNINGS-004

### Code Metrics Calculation (METRICS)
- Different line count metrics serve different purposes:
  - `loc`: Total lines of code (all lines in file)
  - `sloc`: Source lines of code (excluding comments and blank lines)
  - `comments`: Comment lines (including docstrings)
  - `blank`: Blank lines
  - `multi`: Multi-line string/docstring lines
- Use regex patterns to accurately identify different line types:
  - Comment pattern: `r'^\s*#'`
  - Docstring start: `r'^\s*(\'\'\'|""")'`
  - Docstring end: `r'(\'\'\'|""")$'`
- Track multi-line constructs with state variables (e.g., `in_multiline = True/False`)
- Cache calculation results for frequently analyzed files
- Implement incremental calculation for changed files only
- Combine AST-based and line-based analysis for comprehensive metrics
- Consider context (module type, function purpose) when interpreting metrics
- Optimize performance for large files with efficient algorithms
- Calculate documentation ratio as a maintainability indicator
- Focus on comment quality over quantity in analysis
- Implement nested calculations for complex metrics
- Maintain line mapping between source and normalized code

### Verification Strategy (VERIFY)
- Test all metrics with diverse code samples
- Include edge cases in testing:
  - Empty files
  - Files with only comments
  - Single-line docstrings
  - Multi-line docstrings
  - Mixed comment styles
- Test with extremely large files to verify performance
- Implement comprehensive error handling for malformed files
- Verify metrics against manual calculations

### Integration Considerations (INTEG)
- Support both command-line and API usage
- Provide machine-readable output formats (JSON, CSV)
- Include trend analysis capabilities
- Support CI/CD integration
- Allow configuration via config files

## Example Patterns

```python
# Line Counting Implementation
def count_code_lines(source_code: str) -> Dict[str, int]:
    """Count different types of lines in source code."""
    lines = source_code.splitlines()

    # Initialize counters
    metrics = {
        "loc": len(lines),  # Total lines of code
        "blank": 0,         # Blank lines
        "comments": 0,      # Comment lines
        "multi": 0,         # Multi-line string/docstring lines
    }

    # Regex patterns for line type detection
    comment_pattern = re.compile(r'^\s*#')
    docstring_start = re.compile(r'^\s*(\'\'\'|""")')
    docstring_end = re.compile(r'(\'\'\'|""")$')

    # Track multi-line docstring state
    in_multiline = False

    # Analyze each line
    for line in lines:
        stripped = line.strip()
        if not stripped:
            metrics["blank"] += 1
        elif comment_pattern.match(line):
            metrics["comments"] += 1
        elif docstring_start.match(stripped) and docstring_end.search(stripped) and len(stripped) > 3:
            # Single line docstring
            metrics["comments"] += 1
        elif docstring_start.match(stripped):
            in_multiline = True
            metrics["comments"] += 1
            metrics["multi"] += 1
        elif in_multiline:
            metrics["comments"] += 1
            metrics["multi"] += 1
            if docstring_end.search(stripped):
                in_multiline = False

    # Calculate source lines of code
    metrics["sloc"] = metrics["loc"] - metrics["comments"] - metrics["blank"]

    return metrics
```

`[Claude.Anthropic.3.7.Sonnet-20250309-CodeMetricsCalculation-2025-03-09-06:00-UTC]`
