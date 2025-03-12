"""
Tests for model performance optimization.

This module tests optimization techniques for model serialization,
deserialization, lazy loading, and batch processing.
"""

import unittest
import time
import json
from typing import List, Dict, Any, Optional
import pytest
from pydantic import ValidationError, BaseModel

from pygovpub.models.optimization import (
    OptimizedModel,
    BatchProcessor,
    LazyLoadableModel,
    SerializationOptimizer,
    batch_process,
    lazy_load
)


class TestModelOptimization:
    """Tests for model optimization features."""

    def test_optimized_model_serialization(self):
        """Test serialization performance of the optimized model."""
        # Arrange
        data = {
            "id": "model-12345",
            "name": "Test Model",
            "attributes": {
                "attr1": "value1",
                "attr2": "value2",
                "attr3": "value3",
                "nested": {
                    "nested1": "value1",
                    "nested2": "value2"
                }
            },
            "tags": ["tag1", "tag2", "tag3"]
        }
        model = OptimizedModel(**data)

        # Act
        start_time = time.time()
        serialized = model.model_dump_json()
        serialization_time = time.time() - start_time

        # Assert
        assert isinstance(serialized, str)
        parsed = json.loads(serialized)
        assert parsed["id"] == "model-12345"
        assert parsed["name"] == "Test Model"
        assert "attr1" in parsed["attributes"]
        assert "nested" in parsed["attributes"]
        assert len(parsed["tags"]) == 3
        
        # The actual threshold is relaxed for CI environments, but should be fast
        assert serialization_time < 0.1  # Serialization should be fast

    def test_optimized_model_deserialization(self):
        """Test deserialization performance of the optimized model."""
        # Arrange
        json_str = """
        {
            "id": "model-12345",
            "name": "Test Model",
            "attributes": {
                "attr1": "value1",
                "attr2": "value2",
                "attr3": "value3",
                "nested": {
                    "nested1": "value1",
                    "nested2": "value2"
                }
            },
            "tags": ["tag1", "tag2", "tag3"]
        }
        """

        # Act
        start_time = time.time()
        model = OptimizedModel.model_validate_json(json_str)
        deserialization_time = time.time() - start_time

        # Assert
        assert model.id == "model-12345"
        assert model.name == "Test Model"
        assert model.attributes["attr1"] == "value1"
        assert model.attributes["nested"]["nested1"] == "value1"
        assert len(model.tags) == 3
        
        # The actual threshold is relaxed for CI environments, but should be fast
        assert deserialization_time < 0.1  # Deserialization should be fast

    def test_lazy_loading_model(self):
        """Test lazy loading capabilities."""
        # Arrange
        data = {
            "id": "model-12345",
            "name": "Test Model",
            "summary": "This is a summary"
        }
        
        # Create a model with lazy-loadable content
        model = LazyLoadableModel(**data)

        # Assert that content is not loaded initially
        assert model.id == "model-12345"
        assert model.name == "Test Model"
        assert model.lazy_content is None

        # Act - trigger lazy loading
        content = model.get_content()

        # Assert
        assert content is not None
        assert "sections" in content
        assert len(content["sections"]) > 0
        
    def test_batch_processing(self):
        """Test batch processing functionality."""
        # Arrange
        items = [
            {"id": f"item-{i}", "value": i} for i in range(100)
        ]
        
        # Act
        processor = BatchProcessor(batch_size=25)
        results = processor.process(items)
        
        # Assert
        assert len(results) == 100
        assert results[0]["id"] == "item-0"
        assert results[99]["id"] == "item-99"
        
        # Check batch processing counts
        assert processor.batch_count == 4  # 100 items / 25 batch size = 4 batches
        
    def test_batch_process_function(self):
        """Test the batch_process utility function."""
        # Arrange
        items = [i for i in range(100)]
        
        # Act
        results = batch_process(items, batch_size=30, transform_fn=lambda x: x * 2)
        
        # Assert
        assert len(results) == 100
        assert results[0] == 0
        assert results[1] == 2
        assert results[99] == 198

    def test_serialization_optimizer(self):
        """Test the serialization optimizer."""
        # Arrange
        data = {
            "id": "model-12345",
            "name": "Test Model",
            "deep_nested": {
                "level1": {
                    "level2": {
                        "level3": {
                            "value": "deeply nested value"
                        }
                    }
                }
            },
            "large_list": [i for i in range(1000)]
        }
        
        # Act
        optimizer = SerializationOptimizer()
        optimized = optimizer.optimize(data)
        
        # Assert
        assert optimized["id"] == "model-12345"
        assert optimized["name"] == "Test Model"
        
        # Check optimization: deep nesting is preserved
        assert optimized["deep_nested"]["level1"]["level2"]["level3"]["value"] == "deeply nested value"
        
        # Check optimization: large list is preserved
        assert len(optimized["large_list"]) == 1000
        assert optimized["large_list"][0] == 0
        assert optimized["large_list"][999] == 999