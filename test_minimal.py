from utilities.source_analyzer import SourceAnalyzer, SourceFile
from pathlib import Path

def test_minimal_duplicate_detection():
    """Minimal test for duplicate code detection."""
    test_content = '''
def func1(x):
    if x > 0:
        return x * 2
    return x

def func2(y):
    if y > 0:
        return y * 2
    return y
'''
    test_file = Path("minimal_test.py")
    test_file.write_text(test_content)

    try:
        analyzer = SourceAnalyzer()
        source_file = analyzer.identify_source_file(test_file)
        patterns = analyzer.detect_patterns(source_file)

        # We expect exactly one duplicate pair
        duplicates = patterns.get_duplicate_blocks()
        assert len(duplicates) == 1

        # Verify the duplicate contains both functions
        duplicate = duplicates[0]
        assert "func1" in duplicate.function_names
        assert "func2" in duplicate.function_names

    finally:
        if test_file.exists():
            test_file.unlink()
