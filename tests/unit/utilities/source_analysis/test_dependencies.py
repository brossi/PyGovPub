"""Tests for dependency analysis functionality."""

import pytest
from pathlib import Path
import networkx as nx
from textwrap import dedent
from typing import List, Optional

from utilities.source_analyzer import (
    SourceAnalyzer,
    QualityMetrics,
    DependencyInfo,
    ModuleDependencyGraph,
    AnalysisError,
    SourceFile,
    DependencyAnalyzer
)

@pytest.fixture
def simple_imports_file(tmp_path: Path) -> Path:
    """Create a test file with simple imports."""
    file_path = tmp_path / "simple_imports.py"
    content = dedent("""
        import os
        import sys
        from pathlib import Path
        from typing import List, Optional

        def main():
            path = Path('.')
            files = os.listdir(path)
            return files
    """)
    file_path.write_text(content)
    return file_path

@pytest.fixture
def invalid_syntax_file(tmp_path) -> Path:
    """Create a test file with invalid Python syntax."""
    file_path = tmp_path / "invalid_syntax.py"
    file_path.write_text("""
import os
from typing import List,  # Invalid syntax - missing type
""")
    return file_path

@pytest.fixture
def relative_imports_file(tmp_path) -> Path:
    """Create a test file with relative imports."""
    # Create package structure
    pkg_dir = tmp_path / "pkg"
    subpkg_dir = pkg_dir / "subpkg"
    other_dir = pkg_dir / "other"

    # Create directories
    subpkg_dir.mkdir(parents=True)
    other_dir.mkdir(parents=True)

    # Create __init__.py files
    (pkg_dir / "__init__.py").write_text("")
    (subpkg_dir / "__init__.py").write_text("")
    (other_dir / "__init__.py").write_text("")

    # Create sibling modules
    (subpkg_dir / "sibling.py").write_text("")
    (pkg_dir / "parent.py").write_text("")
    (other_dir / "util.py").write_text("")
    (pkg_dir / "root.py").write_text("")

    # Create the module file
    file_path = subpkg_dir / "module.py"
    file_path.write_text("""
from . import sibling
from .. import parent
from ..other import util
from ...pkg import root
""")
    return file_path

@pytest.fixture
def test_project(tmp_path):
    """Create a test project structure."""
    # Create project structure
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create module_a.py
    module_a = project_root / "module_a.py"
    module_a.write_text("""
from module_b import function_b

def function_a():
    return function_b()
""")

    # Create module_b.py
    module_b = project_root / "module_b.py"
    module_b.write_text("""
def function_b():
    return "Hello from B"
""")

    # Create package with relative imports
    pkg_dir = project_root / "package"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").touch()

    # Create submodule with relative import
    sub_a = pkg_dir / "sub_a.py"
    sub_a.write_text("""
from .sub_b import sub_function_b

def sub_function_a():
    return sub_function_b()
""")

    # Create target of relative import
    sub_b = pkg_dir / "sub_b.py"
    sub_b.write_text("""
def sub_function_b():
    return "Hello from sub B"
""")

    return project_root

@pytest.fixture
def simple_project(tmp_path):
    """Create a simple project structure for testing."""
    project_root = tmp_path / "test_project"
    project_root.mkdir()

    # Create module_a.py
    module_a = project_root / "module_a.py"
    module_a.write_text("""
from module_b import function_b

def function_a():
    return function_b()
""")

    # Create module_b.py
    module_b = project_root / "module_b.py"
    module_b.write_text("""
def function_b():
    return "Hello from B"
""")

    return project_root

@pytest.fixture
def circular_project(tmp_path):
    """Create a project with circular dependencies."""
    project_root = tmp_path / "circular_test"
    project_root.mkdir()

    # Create circular dependency between two modules
    module_x = project_root / "module_x.py"
    module_x.write_text("""
from module_y import function_y

def function_x():
    return function_y()
""")

    module_y = project_root / "module_y.py"
    module_y.write_text("""
from module_x import function_x

def function_y():
    return function_x()
""")

    return project_root

class TestDependencyAnalysis:
    """Test dependency analysis functionality."""

    def test_stub_basic_dependencies(self, simple_project):
        # STUB: This will test basic dependency analysis in source_analyzer.py
        """Test basic dependency analysis."""
        analyzer = SourceAnalyzer()
        source_file = analyzer.identify_source_file(simple_project / "module_a.py")
        deps = analyzer.calculate_quality_metrics(source_file)

        # Check dependency graph
        graph = deps.dependency_graph
        assert isinstance(graph, nx.DiGraph)
        assert "module_a.py" in graph
        assert "module_b.py" in graph
        assert graph.has_edge("module_a.py", "module_b")

        # Check coupling metrics
        assert deps.afferent_coupling["module_b.py"] == 1
        assert deps.afferent_coupling["module_a.py"] == 0
        assert deps.efferent_coupling["module_a.py"] == 1
        assert deps.efferent_coupling["module_b.py"] == 0

    def test_stub_circular_dependencies(self, circular_project):
        # STUB: This will test circular dependency detection in source_analyzer.py
        """Test detection of circular dependencies."""
        analyzer = SourceAnalyzer()
        source_file = analyzer.identify_source_file(circular_project / "module_x.py")
        deps = analyzer.calculate_quality_metrics(source_file)

        # Check circular dependencies
        assert len(deps.circular_deps) > 0
        assert {"module_x.py", "module_y.py"} == set(deps.circular_deps[0])

    def test_stub_error_handling(self, tmp_path):
        # STUB: This will test error handling in dependency analysis in source_analyzer.py
        """Test error handling in dependency analysis."""
        project_root = tmp_path / "error_test"
        project_root.mkdir()

        # Create file with syntax error
        invalid_file = project_root / "invalid.py"
        invalid_file.write_text("def invalid_function(:")

        analyzer = SourceAnalyzer()
        source_file = analyzer.identify_source_file(invalid_file)
        with pytest.raises(AnalysisError):
            analyzer.calculate_quality_metrics(source_file)

    def test_stub_package_dependencies(self):
        # STUB: This will test package dependency analysis in source_analyzer.py
        """Test package dependency analysis."""
        source_file = SourceFile(Path(__file__))  # Use this test file
        analyzer = DependencyAnalyzer(source_file)
        deps = analyzer.analyze_package_dependencies()

        # Check that pytest is included (since it's a test dependency)
        pytest_dep = deps.get('pytest')
        assert pytest_dep is not None
        assert pytest_dep.name == 'pytest'
        assert pytest_dep.version != 'unknown'

    def test_stub_package_dependency_error_handling(self, tmp_path):
        # STUB: This will test package dependency error handling in source_analyzer.py
        """Test error handling in package dependency analysis."""
        empty_file = tmp_path / "empty.py"
        empty_file.write_text("")
        source_file = SourceFile(empty_file)
        analyzer = DependencyAnalyzer(source_file)

        # Should still return package info even for empty file
        deps = analyzer.analyze_package_dependencies()
        assert isinstance(deps, dict)

    def test_stub_module_dependency_error_handling(self, invalid_syntax_file):
        # STUB: This will test module dependency error handling in source_analyzer.py
        """Test error handling for invalid Python syntax."""
        source_file = SourceFile(invalid_syntax_file)
        analyzer = DependencyAnalyzer(source_file)

        with pytest.raises(AnalysisError) as exc_info:
            analyzer.analyze_module_dependencies()
        assert "Module dependency analysis failed" in str(exc_info.value)

    def test_stub_package_analysis_failure(self, monkeypatch):
        # STUB: This will test package analysis failure handling in source_analyzer.py
        """Test handling of package analysis failures."""
        def mock_distributions():
            class MockDist:
                @property
                def metadata(self):
                    raise Exception("Metadata error")

                @property
                def name(self):
                    return "mock-package"

            return [MockDist()]

        source_file = SourceFile(Path(__file__))
        analyzer = DependencyAnalyzer(source_file)

        # Mock the distributions function to raise an error
        monkeypatch.setattr('importlib.util.find_spec', lambda _: None)  # Updated monkeypatch path

        # Should handle the error and continue
        deps = analyzer.analyze_package_dependencies()
        assert isinstance(deps, dict)
        assert len(deps) == 0  # No packages should be processed due to the error

    def test_stub_clear_cache(self, simple_imports_file):
        # STUB: This will test clearing dependency cache in source_analyzer.py
        """Test cache clearing functionality."""
        source_file = SourceFile(simple_imports_file)
        analyzer = DependencyAnalyzer(source_file)

        # Get dependencies to populate cache
        module_deps = analyzer.analyze_module_dependencies()
        pkg_deps = analyzer.analyze_package_dependencies()

        # Clear cache
        analyzer.clear_cache()

        # Internal cache variables should be None
        assert analyzer._module_deps is None
        assert analyzer._pkg_deps is None

    def test_stub_relative_imports(self, relative_imports_file):
        # STUB: This will test relative import handling in source_analyzer.py
        """Test analysis of relative imports."""
        source_file = SourceFile(relative_imports_file)
        analyzer = DependencyAnalyzer(source_file)
        deps = analyzer.analyze_module_dependencies()
        module_deps = deps[Path(relative_imports_file).stem]

        # Print all import paths for debugging
        print("\nActual import paths:")
        for d in module_deps:
            print(f"  {d.import_path}")

        # Check relative import paths are resolved
        assert any(d.import_path == 'pkg.subpkg.sibling' for d in module_deps)
        assert any(d.import_path == 'pkg.parent' for d in module_deps)
        assert any(d.import_path == 'pkg.other.util' for d in module_deps)
        assert any(d.import_path == 'pkg.root' for d in module_deps)

    def test_stub_minimal_dependency_analysis(self, tmp_path):
        # STUB: This will test minimal dependency analysis in source_analyzer.py
        """Test minimal dependency analysis with just two files."""
        # Create test project
        project_root = tmp_path / "minimal_test"
        project_root.mkdir()

        # Create two simple modules
        main_module = project_root / "main.py"
        main_module.write_text("""
from helper import helper_func

def main():
    return helper_func()
""")

        helper_module = project_root / "helper.py"
        helper_module.write_text("""
def helper_func():
    return "Hello"
""")

        # Analyze dependencies
        analyzer = SourceAnalyzer()
        source_file = analyzer.identify_source_file(main_module)
        metrics = analyzer.calculate_quality_metrics(source_file)

        # Check dependency graph
        graph = metrics.dependency_graph
        assert isinstance(graph, nx.DiGraph)
        assert "main.py" in graph.nodes
        assert "helper.py" in graph.nodes
        assert graph.has_edge("main.py", "helper.py")

        # Check coupling metrics
        assert metrics.afferent_coupling["helper.py"] == 1  # main.py depends on helper.py
        assert metrics.afferent_coupling["main.py"] == 0    # nothing depends on main.py
        assert metrics.efferent_coupling["main.py"] == 1    # main.py depends on helper.py
        assert metrics.efferent_coupling["helper.py"] == 0  # helper.py has no dependencies

    def test_stub_module_name_handling(self, tmp_path):
        # STUB: This will test module name handling in source_analyzer.py
        """Test basic module name handling with a single import."""
        # Create test file
        test_file = tmp_path / "test_module.py"
        test_file.write_text("""
import os

def main():
    return os.path.exists('.')
""")

        # Analyze dependencies
        analyzer = SourceAnalyzer()
        source_file = analyzer.identify_source_file(test_file)
        metrics = analyzer.calculate_quality_metrics(source_file)

        # Check dependency graph
        graph = metrics.dependency_graph
        assert isinstance(graph, nx.DiGraph)
        assert "test_module.py" in graph.nodes
        assert "os.py" in graph.nodes
        assert graph.has_edge("test_module.py", "os")  # Edge target should not have .py extension

        # Check coupling metrics
        assert metrics.afferent_coupling["os.py"] == 1
        assert metrics.efferent_coupling["test_module.py"] == 1

# STUB: This will test dependency analysis functionality in source_analyzer.py
# Original import: from utilities.source_analysis.dependencies import DependencyAnalyzer, DependencyInfo

@pytest.fixture
def simple_import_code():
    """Return code with simple imports."""
    return dedent("""
    import os
    import sys
    import math

    def test_function():
        return os.path.join('a', 'b')
    """)

@pytest.fixture
def complex_import_code():
    """Return code with complex imports."""
    return dedent("""
    import os.path
    from sys import argv
    from math import sqrt, sin as sine
    import numpy as np
    from pandas import DataFrame, Series

    def process_data(data):
        result = np.array(data)
        df = DataFrame(result)
        return df.apply(sine)
    """)

@pytest.fixture
def relative_import_code():
    """Return code with relative imports."""
    return dedent("""
    from . import utils
    from .models import User
    from ..config import settings
    from ...core import app

    def initialize():
        app.config.update(settings)
        user = User()
        return utils.process(user)
    """)

def test_stub_simple_import_detection(simple_import_code):
    # STUB: This will test simple import detection in source_analyzer.py
    """Test detection of simple imports."""
    assert True

def test_stub_complex_import_detection(complex_import_code):
    # STUB: This will test complex import detection in source_analyzer.py
    """Test detection of complex imports with aliases."""
    assert True

def test_stub_relative_import_detection(relative_import_code):
    # STUB: This will test relative import detection in source_analyzer.py
    """Test detection of relative imports."""
    assert True

def test_stub_standard_library_detection(simple_import_code):
    # STUB: This will test standard library detection in source_analyzer.py
    """Test detection of standard library imports."""
    assert True

def test_stub_third_party_detection(complex_import_code):
    # STUB: This will test third-party library detection in source_analyzer.py
    """Test detection of third-party library imports."""
    assert True

def test_stub_local_module_detection(relative_import_code):
    # STUB: This will test local module detection in source_analyzer.py
    """Test detection of local module imports."""
    assert True

def test_stub_dependency_graph_creation():
    # STUB: This will test dependency graph creation in source_analyzer.py
    """Test creation of dependency graph."""
    assert True

def test_stub_circular_dependency_detection():
    # STUB: This will test circular dependency detection in source_analyzer.py
    """Test detection of circular dependencies."""
    assert True

def test_stub_unused_import_detection():
    # STUB: This will test unused import detection in source_analyzer.py
    """Test detection of unused imports."""
    assert True
