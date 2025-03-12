"""
Tests for the relationship models.

This module tests the models used for representing complex relationships between entities,
including hierarchical relationships, many-to-many mappings, and temporal relationships.
"""

import unittest
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from enum import Enum
import pytest
from pydantic import ValidationError, BaseModel

from pygovpub.models.documents import DocumentType, SourceReference
from pygovpub.auth.models import ApiSource
from pygovpub.models.relationship import (
    HierarchicalRelationship,
    ManyToManyMapping,
    TemporalRelationship,
    RelationshipConstraint,
    EntityType,
    RelationshipDirection,
    HistoricalState
)


class TestRelationshipModels:
    """Tests for the relationship models."""

    def test_hierarchical_relationship_creation(self):
        """Test creating a hierarchical relationship."""
        # Arrange
        data = {
            "relationship_id": "hier-12345",
            "parent_id": "committee-123",
            "parent_type": EntityType.COMMITTEE,
            "child_id": "subcommittee-456",
            "child_type": EntityType.COMMITTEE,
            "relationship_type": "PARENT_CHILD",
            "start_date": "2023-01-15",
            "properties": {
                "level": 1,
                "index_in_parent": 2,
                "name": "Jurisdiction hierarchy"
            }
        }

        # Act
        relationship = HierarchicalRelationship(**data)

        # Assert
        assert relationship.relationship_id == "hier-12345"
        assert relationship.parent_id == "committee-123"
        assert relationship.parent_type == EntityType.COMMITTEE
        assert relationship.child_id == "subcommittee-456"
        assert relationship.child_type == EntityType.COMMITTEE
        assert relationship.relationship_type == "PARENT_CHILD"
        assert relationship.properties["level"] == 1

    def test_many_to_many_mapping_creation(self):
        """Test creating a many-to-many mapping."""
        # Arrange
        data = {
            "mapping_id": "m2m-12345",
            "entity_a_collection": "committees",
            "entity_a_type": EntityType.COMMITTEE,
            "entity_b_collection": "members",
            "entity_b_type": EntityType.MEMBER,
            "mappings": [
                {"a_id": "committee-123", "b_id": "member-789", "properties": {"role": "Chair", "joined": "2023-01-15"}},
                {"a_id": "committee-123", "b_id": "member-456", "properties": {"role": "Member", "joined": "2023-02-01"}}
            ],
            "mapping_type": "COMMITTEE_MEMBERSHIP",
            "direction": RelationshipDirection.BIDIRECTIONAL
        }

        # Act
        mapping = ManyToManyMapping(**data)

        # Assert
        assert mapping.mapping_id == "m2m-12345"
        assert mapping.entity_a_collection == "committees"
        assert mapping.entity_a_type == EntityType.COMMITTEE
        assert mapping.entity_b_collection == "members"
        assert mapping.entity_b_type == EntityType.MEMBER
        assert len(mapping.mappings) == 2
        assert mapping.mappings[0]["a_id"] == "committee-123"
        assert mapping.mappings[0]["b_id"] == "member-789"
        assert mapping.mappings[0]["properties"]["role"] == "Chair"
        assert mapping.direction == RelationshipDirection.BIDIRECTIONAL

    def test_temporal_relationship_creation(self):
        """Test creating a temporal relationship."""
        # Arrange
        data = {
            "temporal_id": "temp-12345",
            "entity_id": "bill-123",
            "entity_type": EntityType.BILL,
            "history": [
                {
                    "state_id": "state-1",
                    "state_type": "INTRODUCED",
                    "timestamp": "2023-01-15T10:00:00Z",
                    "properties": {"chamber": "HOUSE", "sponsor_count": 5}
                },
                {
                    "state_id": "state-2",
                    "state_type": "COMMITTEE_ACTION",
                    "timestamp": "2023-02-15T14:30:00Z",
                    "properties": {"committee": "Judiciary", "action": "Hearing held"}
                }
            ],
            "current_state_id": "state-2"
        }

        # Act
        temporal = TemporalRelationship(**data)

        # Assert
        assert temporal.temporal_id == "temp-12345"
        assert temporal.entity_id == "bill-123"
        assert temporal.entity_type == EntityType.BILL
        assert len(temporal.history) == 2
        assert temporal.history[0]["state_type"] == "INTRODUCED"
        assert temporal.history[1]["state_type"] == "COMMITTEE_ACTION"
        assert temporal.current_state_id == "state-2"

    def test_relationship_constraint_creation(self):
        """Test creating a relationship constraint."""
        # Arrange
        data = {
            "constraint_id": "const-12345",
            "relationship_type": "COMMITTEE_MEMBERSHIP",
            "source_entity_type": EntityType.COMMITTEE,
            "target_entity_type": EntityType.MEMBER,
            "cardinality": "MANY_TO_MANY",
            "required": True,
            "validation_rules": [
                {"rule_type": "MAX_ITEMS", "value": 50, "target": "COMMITTEE"},
                {"rule_type": "UNIQUENESS", "value": True, "target": "MAPPING"}
            ]
        }

        # Act
        constraint = RelationshipConstraint(**data)

        # Assert
        assert constraint.constraint_id == "const-12345"
        assert constraint.relationship_type == "COMMITTEE_MEMBERSHIP"
        assert constraint.source_entity_type == EntityType.COMMITTEE
        assert constraint.target_entity_type == EntityType.MEMBER
        assert constraint.cardinality == "MANY_TO_MANY"
        assert constraint.required is True
        assert len(constraint.validation_rules) == 2
        assert constraint.validation_rules[0]["rule_type"] == "MAX_ITEMS"
        assert constraint.validation_rules[0]["value"] == 50