# Phase 09: CI/CD Pipeline Implementation

## Overview
This phase implements continuous integration and deployment automation, building upon the completed core phases. This is an enhancement phase that automates quality controls rather than a prerequisite for core functionality.

## Core Requirements
Automate the validation and deployment processes established in phases 01-08, ensuring comprehensive testing and validation across all components.

## Implementation Checklist

### 1. Test Suite Execution [TEST]
- [ ] Test: Unit test configuration
- [ ] Test: Integration test setup
- [ ] Implement: Test execution workflow
```yaml
steps:
  - name: Unit Tests
    run: |
      pytest tests/unit --cov=pygovpub --cov-fail-under=95 --cov-report=xml
      coverage report --fail-under=95

  - name: Integration Tests
    env:
      POSTGRES_HOST: localhost
      POSTGRES_PORT: 5432
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    run: |
      alembic upgrade head
      pytest tests/integration --cov=pygovpub --cov-append
      coverage report --fail-under=90
```

### 2. Code Quality Checks [QA]
- [ ] Test: Static type checking
- [ ] Test: Style validation
- [ ] Test: Complexity analysis
```yaml
steps:
  - name: Code Quality
    run: |
      mypy pygovpub
      pyright
      black --check .
      ruff check .
      radon cc pygovpub --min C
      xenon --max-absolute B --max-modules B --max-average A pygovpub
```

### 3. Database Validation [DB]
- [ ] Test: Schema validation
- [ ] Test: Migration testing
- [ ] Test: Data integrity checks
```yaml
steps:
  - name: Database Validation
    run: |
      # Schema validation
      alembic check
      alembic upgrade head
      alembic downgrade base
      alembic upgrade head

      # Model validation
      python -m pygovpub.db.validate_models

      # Migration testing with sample data
      python -m pygovpub.db.test_migrations
```

### 4. Documentation Checks [DOCS]
- [ ] Test: OpenAPI validation
- [ ] Test: Documentation coverage
- [ ] Test: Link checking
```yaml
steps:
  - name: Documentation Validation
    run: |
      # API documentation
      python -m planning.qa.openapi_validation

      # Markdown documentation
      markdownlint-cli2 "**/*.md"
      markdown-link-check **/*.md

      # README validation
      python -m readme_renderer README.md

      # API documentation coverage
      interrogate pygovpub -v -i --fail-under 95

      # Validate OpenAPI schema
      openapi-spec-validator pygovpub/openapi.json
```

### 5. Output Validation [DATA]
- [ ] Test: Response format validation
- [ ] Test: Payload schema checks
- [ ] Test: Data sanitization
```yaml
steps:
  - name: Output Validation
    run: |
      # Response format tests
      python -m pygovpub.validation.test_responses

      # Schema validation
      python -m pygovpub.validation.test_schemas

      # Payload sanitization checks
      python -m pygovpub.validation.test_sanitization
```

### 6. Security Scanning [SEC]
- [ ] Test: Dependency scanning
- [ ] Test: Code security analysis
- [ ] Test: Secret detection
- [ ] Test: SAST and container scanning
```yaml
steps:
  - name: Security Checks
    run: |
      # Dependency security
      safety check
      pip-audit

      # Code security
      bandit -r pygovpub -ll
      semgrep scan --config "p/owasp-top-ten"

      # Secret detection
      gitleaks protect --verbose
      detect-secrets scan

      # Container security
      trivy fs .
      dockle --ignore-unfixed pygovpub

      # SAST
      sonarqube-scanner

      # License compliance
      licensecheck --recursive .
      pip-licenses --format=json --with-urls
```

### 7. Performance Testing [PERF]
- [ ] Test: Response time benchmarks
- [ ] Test: Memory usage
- [ ] Test: Load testing
```yaml
steps:
  - name: Performance Checks
    run: |
      # Response time benchmarks
      python -m pytest tests/performance --benchmark-only

      # Memory profiling
      python -m memory_profiler tests/performance/memory_tests.py

      # Load testing
      locust -f tests/performance/locustfile.py --headless -u 10 -r 2 --run-time 1m

      # API performance checks
      artillery run tests/performance/api-load.yml

      # Resource usage limits
      python -m pygovpub.validation.test_resource_limits
```

### Performance Test Configuration

```yaml
# tests/performance/api-load.yml
config:
  target: "http://localhost:8000"
  phases:
    - duration: 60
      arrivalRate: 5
      rampTo: 20
  defaults:
    headers:
      X-API-Key: "{{ $processEnvironment.TEST_API_KEY }}"

scenarios:
  - name: "API Operations"
    flow:
      - get:
          url: "/api/v1/bills/search"
          expect:
            - statusCode: 200
            - maxResponseTime: 200
      - get:
          url: "/api/v1/bills/HR1234-117"
          expect:
            - statusCode: 200
            - maxResponseTime: 150
```

```python
# tests/performance/memory_tests.py
@profile
def test_memory_usage():
    """Test memory usage for core operations."""
    client = TestClient()

    # Test bill search memory
    results = client.get("/api/v1/bills/search")
    assert results.status_code == 200
    assert get_memory_usage() < MAX_MEMORY_THRESHOLD

    # Test document processing memory
    doc = client.get("/api/v1/documents/BILLS-117hr1234ih")
    assert doc.status_code == 200
    assert get_memory_usage() < MAX_MEMORY_THRESHOLD
```

```python
# tests/performance/locustfile.py
from locust import HttpUser, task, between

class APIUser(HttpUser):
    wait_time = between(1, 2)

    @task(3)
    def search_bills(self):
        self.client.get("/api/v1/bills/search")

    @task(2)
    def get_bill(self):
        self.client.get("/api/v1/bills/HR1234-117")

    @task(1)
    def verify_document(self):
        self.client.get("/api/v1/documents/BILLS-117hr1234ih/verify")
```

### Complete GitHub Actions Workflow
```yaml
name: PyGovPub CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
  release:
    types: [ published ]

jobs:
  validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.13"]

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_USER: test
          POSTGRES_DB: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0  # Required for some checks

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev,test,docs]"

    - name: Unit Tests
      run: |
        pytest tests/unit --cov=pygovpub --cov-fail-under=95 --cov-report=xml
        coverage report --fail-under=95

    - name: Integration Tests
      env:
        POSTGRES_HOST: localhost
        POSTGRES_PORT: 5432
      run: |
        alembic upgrade head
        pytest tests/integration --cov=pygovpub --cov-append
        coverage report --fail-under=90

    - name: Code Quality
      run: |
        mypy pygovpub
        pyright
        black --check .
        ruff check .
        radon cc pygovpub --min C
        xenon --max-absolute B --max-modules B --max-average A pygovpub

    - name: Database Validation
      run: |
        alembic check
        python -m pygovpub.db.validate_models
        python -m pygovpub.db.test_migrations

    - name: Documentation
      run: |
        python -m planning.qa.openapi_validation
        sphinx-build -W -b html docs/ docs/_build
        sphinx-build -W -b linkcheck docs/ docs/_build
        python -m readme_renderer README.md
        interrogate pygovpub -v -i --fail-under 95
        markdownlint-cli2 "**/*.md"

    - name: Output Validation
      run: |
        python -m pygovpub.validation.test_responses
        python -m pygovpub.validation.test_schemas
        python -m pygovpub.validation.test_sanitization

    - name: Security
      run: |
        safety check
        bandit -r pygovpub -ll
        pip-audit
        gitleaks protect --verbose
        trivy fs .

    - name: Build
      run: |
        python -m build
        twine check dist/*

    - name: Upload Coverage
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        fail_ci_if_error: true

    - name: Deploy
      if: github.event_name == 'release'
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
      run: |
        twine upload dist/*

## Additional Configuration Files

### pyproject.toml additions
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "--cov=pygovpub --cov-report=term-missing"

[tool.coverage.run]
branch = true
source = ["pygovpub"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
    "pass",
]

[tool.interrogate]
ignore-init-method = true
ignore-init-module = true
ignore-magic = true
ignore-semiprivate = true
ignore-private = true
ignore-property-decorators = true
ignore-module = true
fail-under = 95
exclude = ["tests", "docs", "build"]

[tool.ruff]
select = ["E", "F", "B", "I"]
ignore = ["E501"]
```

### .markdownlint.yaml
```yaml
default: true
MD013: false  # Line length
MD033: false  # Inline HTML
MD041: false  # First line h1
```

## Completion Criteria
- All test suites pass consistently
- Code coverage meets requirements
- Database migrations validate
- Documentation is complete and valid
- All output formats validate
- Security scans pass
- Build artifacts verify

## Dependencies
- GitHub Actions or equivalent CI platform
- PostgreSQL for integration tests
- Python 3.13+ with all dev dependencies
- Documentation tools installed

## Notes
1. Pipeline can run partially during development
2. Full pipeline required for releases
3. Local pre-commit hooks mirror CI checks
4. Coverage requirements strictly enforced

## Configuration Examples

### pytest.ini
```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = --cov=pygovpub --cov-report=term-missing
```

### mypy.ini
```ini
[mypy]
python_version = 3.13
warn_return_any = True
warn_unused_configs = True
disallow_untyped_defs = True
```

### .bandit
```yaml
skips: ['B101', 'B601']
exclude_dirs: ['tests', 'docs']
```

## Integration Points

### Pre-commit Hooks
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.12.1
    hooks:
      - id: black

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [types-all]
```

### GitHub Actions Workflow
```yaml
name: PyGovPub CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]
  release:
    types: [ published ]

jobs:
  validate:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.13"]

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
        cache: 'pip'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev,test]"

    - name: Quality Gates
      run: |
        pytest --cov=pygovpub --cov-fail-under=95
        mypy pygovpub
        pyright
        black --check .
        bandit -r pygovpub

    - name: Documentation
      run: |
        python -m planning.qa.openapi_validation
        sphinx-build -W -b html docs/ docs/_build

    - name: Security
      run: |
        safety check
        pip-audit

    - name: Build
      run: |
        python -m build
        twine check dist/*

    - name: Deploy
      if: github.event_name == 'release'
      env:
        TWINE_USERNAME: __token__
        TWINE_PASSWORD: ${{ secrets.PYPI_TOKEN }}
      run: |
        twine upload dist/*
```

## Future Enhancements
1. Matrix testing across Python versions
2. Performance regression testing
3. Integration test automation
4. Deployment environment management
5. Automated changelog generation
