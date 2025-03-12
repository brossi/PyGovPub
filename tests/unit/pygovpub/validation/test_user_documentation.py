"""
Tests for user and installation documentation.

These tests verify that user documentation and installation guides
meet quality standards, including completeness, accuracy, and clarity.
"""

import re
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestReadmeDocumentation:
    """Test README documentation."""
    
    def test_readme_exists(self):
        """Test that README.md exists."""
        readme_path = Path('README.md')
        assert readme_path.exists(), "README.md not found"
    
    def test_readme_sections(self):
        """Test that README.md has required sections."""
        readme_path = Path('README.md')
        with open(readme_path, 'r') as f:
            content = f.read()
            
            # Check for required sections
            assert "# " in content, "README should have a title"
            
            required_sections = [
                "installation", "install",
                "usage", "example",
                "documentation", "docs",
                "contributing", "license"
            ]
            
            # At least 4 of these sections should be present
            section_count = sum(1 for section in required_sections if section in content.lower())
            assert section_count >= 4, f"README only has {section_count} of the required sections"
    
    def test_readme_code_examples(self):
        """Test that README.md has code examples."""
        readme_path = Path('README.md')
        with open(readme_path, 'r') as f:
            content = f.read()
            
            # Check for code blocks
            code_blocks = re.findall(r'```[a-z]*\n(.*?)```', content, re.DOTALL)
            assert len(code_blocks) > 0, "README should have code examples"
            
            # Some code blocks should have Python code
            python_blocks = re.findall(r'```(?:python|py)\n(.*?)```', content, re.DOTALL)
            assert len(python_blocks) > 0, "README should have Python code examples"


class TestInstallationDocumentation:
    """Test installation documentation."""
    
    def test_pyproject_toml(self):
        """Test pyproject.toml completeness."""
        pyproject_path = Path('pyproject.toml')
        assert pyproject_path.exists(), "pyproject.toml not found"
        
        with open(pyproject_path, 'r') as f:
            content = f.read()
            
            # Check for essential fields
            assert "[project]" in content, "pyproject.toml should have [project] section"
            assert "name" in content, "pyproject.toml should specify package name"
            assert "version" in content, "pyproject.toml should specify version"
            assert "description" in content, "pyproject.toml should have description"
            
            # Check for dependencies
            assert "[project.dependencies]" in content or "dependencies" in content, \
                "pyproject.toml should list dependencies"
    
    def test_requirements_txt(self):
        """Test requirements.txt completeness."""
        req_path = Path('requirements.txt')
        assert req_path.exists(), "requirements.txt not found"
        
        with open(req_path, 'r') as f:
            content = f.readlines()
            
            # Should have multiple dependencies
            assert len(content) > 5, "requirements.txt should list all dependencies"
            
            # Check for core dependencies
            core_deps = ["fastapi", "pydantic", "sqlmodel", "httpx", "aiohttp", "typer"]
            found_deps = sum(1 for dep in core_deps if any(dep in line for line in content))
            assert found_deps >= 3, f"requirements.txt only includes {found_deps} of the core dependencies"
    
    def test_setup_documentation(self):
        """Test setup documentation."""
        setup_doc_path = Path('docs/setup.md')
        if not setup_doc_path.exists():
            pytest.skip("No dedicated setup docs found")
        
        with open(setup_doc_path, 'r') as f:
            content = f.read().lower()
            
            # Check for essential setup instructions
            assert "install" in content, "Setup docs should cover installation"
            assert "requirements" in content or "prerequisite" in content, \
                "Setup docs should cover prerequisites"
            assert "configuration" in content or "configure" in content, \
                "Setup docs should cover configuration"


class TestApiDocumentation:
    """Test API documentation."""
    
    def test_api_endpoints_documentation(self):
        """Test API endpoints documentation."""
        # Look for endpoint docs
        endpoint_docs = list(Path('planning/endpoints').glob('**/*.md'))
        assert len(endpoint_docs) > 0, "No API endpoint documentation found"
        
        # Check content of a few docs
        endpoint_types = set()
        for doc_path in endpoint_docs[:5]:  # Check first 5 docs
            with open(doc_path, 'r') as f:
                content = f.read().lower()
                
                # Categorize the endpoint type
                if "authentication" in doc_path.parts:
                    endpoint_types.add("authentication")
                elif "documents" in doc_path.parts:
                    endpoint_types.add("documents")
                elif "legislative" in doc_path.parts:
                    endpoint_types.add("legislative")
                elif "regulatory" in doc_path.parts:
                    endpoint_types.add("regulatory")
                elif "updates" in doc_path.parts:
                    endpoint_types.add("updates")
                
                # Check for endpoint details
                assert "endpoint" in content or "api" in content, \
                    f"{doc_path} should describe endpoints"
                assert "parameter" in content or "request" in content, \
                    f"{doc_path} should describe request parameters"
                assert "response" in content or "return" in content, \
                    f"{doc_path} should describe responses"
        
        # Should have multiple endpoint types
        assert len(endpoint_types) >= 2, f"Only found {len(endpoint_types)} endpoint types"
    
    def test_api_standards_documentation(self):
        """Test API standards documentation."""
        standards_doc = Path('planning/standards/api-documentation.md')
        assert standards_doc.exists(), "API standards documentation not found"
        
        with open(standards_doc, 'r') as f:
            content = f.read().lower()
            
            # Check for API standards topics
            standards_topics = [
                "version", "format", "endpoint", "parameter", "response", "error", 
                "convention", "status", "http"
            ]
            
            topic_count = sum(1 for topic in standards_topics if topic in content)
            assert topic_count >= 5, f"API standards only covers {topic_count} of the expected topics"


class TestUsageDocumentation:
    """Test usage documentation."""
    
    def test_core_usage_examples(self):
        """Test core usage examples documentation."""
        # Look for example code in various docs
        readme_path = Path('README.md')
        example_count = 0
        
        if readme_path.exists():
            with open(readme_path, 'r') as f:
                content = f.read()
                
                # Count code examples in README
                python_blocks = re.findall(r'```(?:python|py)\n(.*?)```', content, re.DOTALL)
                example_count += len(python_blocks)
        
        # Look in docs directory
        doc_files = list(Path('docs').glob('**/*.md'))
        for doc_path in doc_files:
            with open(doc_path, 'r') as f:
                content = f.read()
                
                # Count code examples in docs
                python_blocks = re.findall(r'```(?:python|py)\n(.*?)```', content, re.DOTALL)
                example_count += len(python_blocks)
        
        # Should have multiple usage examples
        assert example_count >= 3, f"Only found {example_count} code examples in documentation"
    
    def test_cli_documentation(self):
        """Test CLI documentation."""
        # Check if CLI documentation exists
        cli_doc_found = False
        doc_files = list(Path('docs').glob('**/*.md')) + list(Path('planning').glob('**/*.md'))
        
        for doc_path in doc_files:
            with open(doc_path, 'r') as f:
                content = f.read().lower()
                
                # Look for CLI documentation
                if "cli" in content and "command" in content:
                    cli_command_examples = re.findall(r'```(?:bash|sh|console)\n.*?(?:pygovpub|--help).*?```', 
                                                   content, re.DOTALL)
                    if cli_command_examples:
                        cli_doc_found = True
                        break
        
        assert cli_doc_found, "No CLI documentation found"
    
    def test_configuration_documentation(self):
        """Test configuration documentation."""
        # Check if configuration documentation exists
        config_doc_path = Path('docs/configuration.md')
        
        if config_doc_path.exists():
            with open(config_doc_path, 'r') as f:
                content = f.read().lower()
                
                # Check for configuration topics
                config_topics = [
                    "environment", "variable", "setting", "option", 
                    "config", "parameter", "value"
                ]
                
                topic_count = sum(1 for topic in config_topics if topic in content)
                assert topic_count >= 3, f"Configuration docs only cover {topic_count} of the expected topics"
        else:
            # Look for configuration docs elsewhere
            config_doc_found = False
            doc_files = list(Path('docs').glob('**/*.md')) + list(Path('planning').glob('**/*.md'))
            
            for doc_path in doc_files:
                with open(doc_path, 'r') as f:
                    content = f.read().lower()
                    
                    # Look for configuration documentation
                    if "configuration" in doc_path.name.lower() or \
                       ("config" in content and "setting" in content):
                        config_doc_found = True
                        break
            
            assert config_doc_found, "No configuration documentation found"