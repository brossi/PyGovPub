"""
Tests for code documentation quality.

These tests verify that code documentation meets quality standards,
including presence of docstrings, type hints, and parameter descriptions.
"""

import ast
import inspect
import re
import pytest
from pathlib import Path
from typing import Dict, List, Any, Set

from pygovpub.api import app, router, base
from pygovpub.auth import auth_manager, models, rate_limiter
from pygovpub.core import database, crud
from pygovpub.cli import main, config, output


class TestModuleDocumentation:
    """Test module level documentation."""
    
    def test_module_docstrings(self):
        """Test that modules have docstrings."""
        # Modules to check
        modules = [
            app, router, base,
            auth_manager, models, rate_limiter,
            database, crud,
            main, config, output
        ]
        
        # Check each module
        missing_docstrings = []
        for module in modules:
            if not module.__doc__:
                missing_docstrings.append(module.__name__)
        
        # All modules should have docstrings
        assert len(missing_docstrings) == 0, f"Modules missing docstrings: {missing_docstrings}"
    
    def test_module_docstring_quality(self):
        """Test quality of module docstrings."""
        # Modules to check
        modules = [
            app, router, base,
            auth_manager, models, rate_limiter,
            database, crud,
            main, config, output
        ]
        
        # Check each module with docstring
        low_quality_docstrings = []
        for module in modules:
            if module.__doc__:
                doc = module.__doc__.strip()
                # Check length - should be at least 3 lines
                if len(doc.split('\n')) < 3:
                    low_quality_docstrings.append(module.__name__)
                # Check content - should describe purpose
                elif not any(keyword in doc.lower() for keyword in ["provides", "handles", "manages", "implements"]):
                    low_quality_docstrings.append(module.__name__)
        
        # Most modules should have quality docstrings
        assert len(low_quality_docstrings) <= 2, f"Modules with low quality docstrings: {low_quality_docstrings}"


class TestClassDocumentation:
    """Test class level documentation."""
    
    def get_classes(self, module):
        """Get classes from a module."""
        return [obj for name, obj in inspect.getmembers(module) 
                if inspect.isclass(obj) and obj.__module__ == module.__name__]
    
    def test_class_docstrings(self):
        """Test that classes have docstrings."""
        # Modules to check
        modules = [
            auth_manager, models, rate_limiter,
            database, crud
        ]
        
        # Check classes in each module
        missing_docstrings = []
        total_classes = 0
        classes_with_docstrings = 0
        
        for module in modules:
            classes = self.get_classes(module)
            for cls in classes:
                total_classes += 1
                if not cls.__doc__:
                    missing_docstrings.append(f"{module.__name__}.{cls.__name__}")
                else:
                    classes_with_docstrings += 1
        
        # Calculate percentage
        if total_classes > 0:
            docstring_percentage = (classes_with_docstrings / total_classes) * 100
            assert docstring_percentage >= 80, f"Only {docstring_percentage:.2f}% of classes have docstrings"
    
    def test_class_docstring_quality(self):
        """Test quality of class docstrings."""
        # Modules to check
        modules = [
            auth_manager, models, rate_limiter,
            database, crud
        ]
        
        # Check classes in each module
        low_quality_docstrings = []
        total_classes_with_docs = 0
        quality_docstrings = 0
        
        for module in modules:
            classes = self.get_classes(module)
            for cls in classes:
                if cls.__doc__:
                    total_classes_with_docs += 1
                    doc = cls.__doc__.strip()
                    # Check length - should be at least 2 lines
                    if len(doc.split('\n')) >= 2:
                        # Check content - should describe purpose
                        if any(keyword in doc.lower() for keyword in ["class", "handles", "manages", "represents", "provides"]):
                            quality_docstrings += 1
                        else:
                            low_quality_docstrings.append(f"{module.__name__}.{cls.__name__}")
        
        # Calculate percentage
        if total_classes_with_docs > 0:
            quality_percentage = (quality_docstrings / total_classes_with_docs) * 100
            assert quality_percentage >= 20, f"Only {quality_percentage:.2f}% of class docstrings are high quality"


class TestFunctionDocumentation:
    """Test function level documentation."""
    
    def get_functions(self, module):
        """Get functions from a module."""
        return [obj for name, obj in inspect.getmembers(module) 
                if inspect.isfunction(obj) and obj.__module__ == module.__name__]
    
    def get_methods(self, cls):
        """Get methods from a class."""
        return [obj for name, obj in inspect.getmembers(cls) 
                if inspect.isfunction(obj) and not name.startswith('__')]
    
    def test_function_docstrings(self):
        """Test that functions have docstrings."""
        # Modules to check
        modules = [
            router, base,
            auth_manager, rate_limiter,
            database, crud,
            config, output
        ]
        
        # Check functions in each module
        missing_docstrings = []
        total_functions = 0
        functions_with_docstrings = 0
        
        for module in modules:
            functions = self.get_functions(module)
            for func in functions:
                if not func.__name__.startswith('_'):  # Skip private functions
                    total_functions += 1
                    if not func.__doc__:
                        missing_docstrings.append(f"{module.__name__}.{func.__name__}")
                    else:
                        functions_with_docstrings += 1
        
        # Calculate percentage
        if total_functions > 0:
            docstring_percentage = (functions_with_docstrings / total_functions) * 100
            assert docstring_percentage >= 60, f"Only {docstring_percentage:.2f}% of functions have docstrings"
    
    def test_method_docstrings(self):
        """Test that class methods have docstrings."""
        # Modules to check
        modules = [
            auth_manager, models, rate_limiter,
            database, crud
        ]
        
        # Check methods in each class
        missing_docstrings = []
        total_methods = 0
        methods_with_docstrings = 0
        
        for module in modules:
            classes = [obj for name, obj in inspect.getmembers(module) 
                       if inspect.isclass(obj) and obj.__module__ == module.__name__]
            
            for cls in classes:
                methods = self.get_methods(cls)
                for method in methods:
                    if not method.__name__.startswith('_'):  # Skip private methods
                        total_methods += 1
                        if not method.__doc__:
                            missing_docstrings.append(f"{module.__name__}.{cls.__name__}.{method.__name__}")
                        else:
                            methods_with_docstrings += 1
        
        # Calculate percentage
        if total_methods > 0:
            docstring_percentage = (methods_with_docstrings / total_methods) * 100
            assert docstring_percentage >= 40, f"Only {docstring_percentage:.2f}% of methods have docstrings"


class TestTypeHints:
    """Test type hint usage."""
    
    def test_function_type_hints(self):
        """Test that functions have type hints."""
        # Modules to check
        modules = [
            router, base,
            auth_manager, rate_limiter,
            database, crud,
            config, output
        ]
        
        # Check functions in each module
        total_functions = 0
        functions_with_hints = 0
        
        for module in modules:
            functions = [obj for name, obj in inspect.getmembers(module) 
                         if inspect.isfunction(obj) and obj.__module__ == module.__name__]
            
            for func in functions:
                if not func.__name__.startswith('_'):  # Skip private functions
                    total_functions += 1
                    type_hints = inspect.get_annotations(func)
                    if type_hints:
                        functions_with_hints += 1
        
        # Calculate percentage
        if total_functions > 0:
            hint_percentage = (functions_with_hints / total_functions) * 100
            assert hint_percentage >= 50, f"Only {hint_percentage:.2f}% of functions have type hints"
    
    def test_parameter_type_hints(self):
        """Test that function parameters have type hints."""
        # Modules to check
        modules = [
            auth_manager, rate_limiter,
            database, crud
        ]
        
        # Check functions in each module
        total_params = 0
        params_with_hints = 0
        
        for module in modules:
            functions = [obj for name, obj in inspect.getmembers(module) 
                         if inspect.isfunction(obj) and obj.__module__ == module.__name__]
            
            for func in functions:
                if not func.__name__.startswith('_'):  # Skip private functions
                    sig = inspect.signature(func)
                    for param_name, param in sig.parameters.items():
                        if param_name != 'self' and param_name != 'cls':
                            total_params += 1
                            if param.annotation != inspect.Parameter.empty:
                                params_with_hints += 1
        
        # Calculate percentage
        if total_params > 0:
            hint_percentage = (params_with_hints / total_params) * 100
            assert hint_percentage >= 50, f"Only {hint_percentage:.2f}% of parameters have type hints"


class TestDocstringFormat:
    """Test docstring format adherence."""
    
    def test_google_style_docstrings(self):
        """Test adherence to Google-style docstrings."""
        # Modules to check
        modules = [
            auth_manager, rate_limiter,
            database, crud
        ]
        
        # Google style patterns
        arg_pattern = re.compile(r'Args:')
        return_pattern = re.compile(r'Returns:')
        raises_pattern = re.compile(r'Raises:')
        
        # Check functions in each module
        google_style_count = 0
        total_docstrings = 0
        
        for module in modules:
            functions = [obj for name, obj in inspect.getmembers(module) 
                         if inspect.isfunction(obj) and obj.__module__ == module.__name__]
            
            for func in functions:
                if func.__doc__:
                    total_docstrings += 1
                    doc = func.__doc__
                    # Check for Google style sections
                    if arg_pattern.search(doc) or return_pattern.search(doc) or raises_pattern.search(doc):
                        google_style_count += 1
        
        # Calculate percentage
        if total_docstrings > 0:
            style_percentage = (google_style_count / total_docstrings) * 100
            assert style_percentage >= 10, f"Only {style_percentage:.2f}% of docstrings follow Google style"