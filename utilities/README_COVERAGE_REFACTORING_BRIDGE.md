# Coverage Refactoring Bridge

This tool integrates the refactoring analyzer with the projected coverage tool to provide coverage-aware refactoring recommendations.

## Features

- Analyzes code for refactoring opportunities based on complexity metrics
- Correlates refactoring opportunities with test coverage data
- Calculates risk scores for each refactoring opportunity
- Prioritizes refactorings based on complexity and test coverage
- Provides test recommendations alongside refactoring suggestions
- Generates detailed reports with before/after code examples
- **Identifies potential premature optimizations** to help focus on high-impact refactorings

## Risk Assessment

The tool calculates a risk score for each refactoring opportunity based on:

- Cyclomatic complexity
- Cognitive complexity
- Test coverage percentage

The risk formula is:
```
risk_score = (cyclomatic_complexity * 0.4 + cognitive_complexity * 0.3) * (1 + (100 - coverage_percentage) / 100)
```

Risk levels:
- **HIGH**: risk_score >= 8.0
- **MEDIUM**: 5.0 <= risk_score < 8.0
- **LOW**: risk_score < 5.0

## Premature Optimization Assessment

The tool assesses whether a refactoring might be premature optimization based on:

- Function complexity and size
- Test coverage
- Risk score
- Function usage patterns (if available)
- Position in dependency graph (if available)

Optimization priority levels:
- **HIGH**: Critical refactoring with significant impact
- **MEDIUM**: Standard refactoring candidate
- **LOW**: Potential premature optimization

By default, the tool will show all refactoring opportunities but flag those that might be premature optimizations. You can use the `--show-all` flag to include all recommendations or omit it to hide potential premature optimizations.

## Requirements

- Python 3.8+
- Required packages (install via `pip install -r requirements.txt`):
  - radon>=4.1.0
  - astroid>=3.0.1
  - networkx>=3.0
  - complexipy>=1.2.0

## Usage

```bash
python coverage_refactoring_bridge.py --package your_package --path path/to/your/codebase
```

### Options

```
--package PACKAGE       Package to analyze
--path PATH             Path to the codebase to analyze
--stub-dir STUB_DIR     Directory containing test stubs (can be specified multiple times)
--format {text,json}    Output format (text or json)
--output OUTPUT         Output file (default: stdout)
--detailed              Include detailed refactoring recommendations
--show-all              Show all refactoring recommendations, including potential premature optimizations
```

## Example Output

```
=== Coverage-Aware Refactoring Analysis ===
Total files analyzed: 10
Total functions: 50
Total classes: 15
Average cyclomatic complexity: 5.20
Average cognitive complexity: 8.30
Average coverage: 75.50%
High risk refactorings: 3
Medium risk refactorings: 7
Low risk refactorings: 12
Potential premature optimizations: 5

=== Coverage-Aware Refactoring Recommendations ===

--- HIGH RISK REFACTORINGS ---

File: auth/rate_limiter.py
Function: check_rate_limit
Risk Score: 12.50
Coverage: 45.00%
Cyclomatic Complexity: 15
Cognitive Complexity: 20
Optimization Priority: HIGH
⚠️ Potential Premature Optimization

Reasons:
  - High cyclomatic complexity (15 > 10)
  - High cognitive complexity (20 > 15)
  - Function is too long (120 lines)

Refactoring Suggestions:
  - Extract complex conditions into separate functions
  - Break down large switch/if-else chains
  - Simplify nested control structures

Optimization Assessment:
  - High risk score indicates significant technical debt

Test Recommendations:
  - Increase test coverage before refactoring (current: 45.0%)
  - Write tests for 55 missing lines
  - Focus on testing error handling and edge cases

Detailed Recommendations:
  === Refactoring Recommendation for check_rate_limit ===
  File: auth/rate_limiter.py

  BEFORE:
  ```python
  def check_rate_limit(self, user_id, action_type):
      # ... existing code ...
  ```

  AFTER:
  ```python
  def check_rate_limit(self, user_id, action_type):
      # ... refactored code ...
  ```

  Instructions:
  1. Create a new method _check_user_limits
  2. Move the user limit checking code to the new method
  3. Replace the original code with a call to the new method
  4. Ensure all necessary variables are accessible in the new method
```

## Integration with Other Tools

The coverage refactoring bridge integrates with:

- **Source Analyzer**: Analyzes code for complexity metrics and refactoring opportunities
- **Refactoring Recommender**: Generates specific, actionable refactoring recommendations
- **Projected Coverage**: Analyzes test coverage and predicts future coverage

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
