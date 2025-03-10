# Refactoring Opportunity Analyzer

This tool analyzes Python code to identify refactoring opportunities based on complexity metrics including cyclomatic complexity and cognitive complexity.

## Features

- Analyzes individual files or entire codebases
- Identifies functions and classes that might benefit from refactoring
- Provides specific refactoring suggestions based on detected issues
- Generates detailed refactoring recommendations with code examples
- Calculates various code quality metrics:
  - Cyclomatic complexity
  - Cognitive complexity
  - Lines of code
  - Maintainability index
  - Halstead metrics

## Requirements

- Python 3.8+
- Required packages (install via `pip install -r requirements.txt`):
  - radon>=4.1.0
  - astroid>=3.0.1
  - networkx>=3.0
  - complexipy>=1.2.0

## Usage

### Analyzing a Single File

```bash
python refactor_analyzer.py --file path/to/your/file.py
```

### Analyzing an Entire Codebase

```bash
python refactor_analyzer.py --path path/to/your/codebase
```

### Excluding Directories

```bash
python refactor_analyzer.py --path path/to/your/codebase --exclude "**/tests/**" --exclude "**/venv/**"
```

### Output Formats

By default, the tool outputs results in text format to the console. You can change this behavior:

```bash
# Output as JSON
python refactor_analyzer.py --file path/to/your/file.py --format json

# Save output to a file
python refactor_analyzer.py --file path/to/your/file.py --output results.txt
```

### Customizing Thresholds

You can customize the thresholds for identifying refactoring opportunities:

```bash
python refactor_analyzer.py --file path/to/your/file.py \
  --threshold-cc 15 \  # Cyclomatic complexity threshold (default: 10)
  --threshold-cog 20 \  # Cognitive complexity threshold (default: 15)
  --threshold-lines 50  # Function length threshold (default: 30)
```

### Detailed Refactoring Recommendations

The tool can provide detailed refactoring recommendations with before/after code examples:

```bash
# Include detailed recommendations
python refactor_analyzer.py --file path/to/your/file.py --detailed

# Specify the type of recommendations to include
python refactor_analyzer.py --file path/to/your/file.py --detailed --recommendation-type extract-method
```

Available recommendation types:
- `extract-method`: Recommendations for extracting methods from long functions
- `extract-conditional`: Recommendations for extracting complex conditionals
- `guard-clauses`: Recommendations for replacing nested conditionals with guard clauses
- `all`: Include all recommendation types (default)

## Understanding the Results

The tool provides a summary of the analysis and a list of refactoring opportunities:

### Summary

- Total files analyzed
- Total lines of code
- Total functions and classes
- Average cyclomatic and cognitive complexity
- Number of files needing refactoring

### Refactoring Opportunities

For each function or class that might benefit from refactoring, the tool provides:

- File path and line numbers
- Cyclomatic and cognitive complexity values
- Specific reasons why refactoring is recommended
- Suggested refactoring approaches

### Detailed Recommendations

When using the `--detailed` flag, the tool also provides:

- Before/after code examples showing how to implement the refactoring
- Step-by-step instructions for implementing the refactoring
- Explanations of why the refactored code is better

## Example Output

```
=== Codebase Analysis Summary ===
Total files analyzed: 1
Total lines of code: 781
Total functions: 32
Total classes: 18
Average cyclomatic complexity: 23.00
Average cognitive complexity: 190.00
Files needing refactoring: 1

=== Refactoring Opportunities ===
File: source_analyzer.py
  FunctionDef: _compute_metrics (lines 319-459)
  Cyclomatic complexity: 23
  Cognitive complexity: 0
  Reasons:
    - High cyclomatic complexity (23 > 10)
    - Function is too long (140 lines)
  Suggestions:
    - Extract complex conditions into separate functions
    - Break down large switch/if-else chains
    - Break down into smaller, focused functions

  Detailed Recommendations:
  === Refactoring Recommendation for _compute_metrics ===
  File: source_analyzer.py

  BEFORE:
  ```python
  def _compute_metrics(self) -> None:
      # ... existing code ...

      # Compute Halstead metrics
      try:
          # First try using h_visit for complete metrics
          h = rm.h_visit(self.source_code)
          if h and hasattr(h, 'total'):
              total = h.total
              self.halstead_metrics.update({
                  'h1': total.h1,
                  'h2': total.h2,
                  # ... more metrics ...
              })
          else:
              # Fallback to using HalsteadVisitor directly
              visitor = HalsteadVisitor.from_code(self.source_code)
              # ... more code ...
      except Exception as e:
          logger.error(f"Failed to compute Halstead metrics: {e}")
          self.halstead_metrics = self.DEFAULT_METRICS['halstead_metrics'].copy()
  ```

  AFTER:
  ```python
  def _compute_metrics(self) -> None:
      # ... existing code ...

      # Compute Halstead metrics
      self._compute_halstead_metrics()

  def _compute_halstead_metrics(self) -> None:
      """Compute Halstead metrics for the source code."""
      try:
          # First try using h_visit for complete metrics
          h = rm.h_visit(self.source_code)
          if h and hasattr(h, 'total'):
              total = h.total
              self.halstead_metrics.update({
                  'h1': total.h1,
                  'h2': total.h2,
                  # ... more metrics ...
              })
          else:
              # Fallback to using HalsteadVisitor directly
              visitor = HalsteadVisitor.from_code(self.source_code)
              # ... more code ...
      except Exception as e:
          logger.error(f"Failed to compute Halstead metrics: {e}")
          self.halstead_metrics = self.DEFAULT_METRICS['halstead_metrics'].copy()
  ```

  Instructions:
  1. Create a new method _compute_halstead_metrics
  2. Move the Halstead metrics calculation code to the new method
  3. Replace the original code with a call to the new method
  4. Ensure all necessary variables are accessible in the new method
```

## Integration with Other Tools

The refactoring analyzer is part of the UnCover tool suite, which includes:

- Source code analysis
- Dependency tracking
- Coverage analysis
- Quality metrics calculation

You can use the refactoring analyzer as a standalone tool or as part of the larger UnCover ecosystem.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
