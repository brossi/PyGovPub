"""
Synchronization manager for PyGovPub.

This module provides a synchronization manager for coordinating data updates
between multiple government data sources and ensuring consistency.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Union, Any, Callable
from uuid import UUID

from pygovpub.auth.models import ApiSource
from pygovpub.events.event_manager import get_event_manager
from pygovpub.events.event_types import (
    Event, EventCategory, EventType, EventPayload,
    DocumentPublishedPayload, DocumentUpdatedPayload
)
from pygovpub.sync.tracker import EntityTracker


class SyncStatus(str, Enum):
    """Status of a synchronization operation."""
    
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CONFLICT = "conflict"


class ConflictResolutionStrategy(str, Enum):
    """Strategy for resolving conflicts between data sources."""
    
    SOURCE_PRECEDENCE = "source_precedence"
    """Prioritize one source over others."""
    
    MOST_RECENT = "most_recent"
    """Use the most recently updated data."""
    
    FIELD_LEVEL_MERGE = "field_level_merge"
    """Merge data at the field level using field-specific rules."""
    
    MANUAL = "manual"
    """Flag for manual review and resolution."""


class ConflictType(str, Enum):
    """Types of data conflicts that can occur."""
    
    VALUE_MISMATCH = "value_mismatch"
    """Different values for the same field."""
    
    TEMPORAL_INCONSISTENCY = "temporal_inconsistency"
    """Inconsistent timestamps or ordering of events."""
    
    MISSING_DATA = "missing_data"
    """Data present in one source but missing in another."""
    
    SEMANTIC_CONTRADICTION = "semantic_contradiction"
    """Logically contradictory information across sources."""
    
    REFERENCE_INCONSISTENCY = "reference_inconsistency"
    """Inconsistent references to related entities."""


class FieldConflict:
    """Represents a conflict in a specific field between data sources."""
    
    def __init__(
        self, 
        field_path: str, 
        conflict_type: ConflictType,
        values: Dict[ApiSource, Any],
        description: str
    ):
        """Initialize field conflict.
        
        Args:
            field_path: Path to the field with conflict (e.g. 'sponsor.party')
            conflict_type: Type of conflict
            values: Dictionary mapping sources to their values
            description: Human-readable description of the conflict
        """
        self.field_path = field_path
        self.conflict_type = conflict_type
        self.values = values
        self.description = description
        self.resolution = None
        self.resolved_value = None
        self.resolution_time = None
        self.resolution_strategy = None


class SyncManager:
    """Manager for data synchronization between multiple sources."""
    
    # Source precedence order (highest priority first)
    SOURCE_PRECEDENCE = {
        "bill": [ApiSource.CONGRESS, ApiSource.GOVINFO],
        "document": [ApiSource.GOVINFO, ApiSource.CONGRESS],
        "committee": [ApiSource.CONGRESS, ApiSource.GOVINFO],
        "member": [ApiSource.CONGRESS, ApiSource.GOVINFO],
        "default": [ApiSource.CONGRESS, ApiSource.GOVINFO]
    }
    
    # Field-specific resolution strategies
    FIELD_STRATEGIES = {
        # Bill fields
        "bill.title": ConflictResolutionStrategy.SOURCE_PRECEDENCE,
        "bill.status": ConflictResolutionStrategy.SOURCE_PRECEDENCE,
        "bill.introduced_date": ConflictResolutionStrategy.SOURCE_PRECEDENCE,
        "bill.latest_action_date": ConflictResolutionStrategy.MOST_RECENT,
        "bill.actions": ConflictResolutionStrategy.FIELD_LEVEL_MERGE,
        "bill.versions": ConflictResolutionStrategy.FIELD_LEVEL_MERGE,
        
        # Document fields
        "document.title": ConflictResolutionStrategy.SOURCE_PRECEDENCE,
        "document.date_issued": ConflictResolutionStrategy.SOURCE_PRECEDENCE,
        "document.last_modified": ConflictResolutionStrategy.MOST_RECENT,
        
        # Default strategy for fields not explicitly listed
        "default": ConflictResolutionStrategy.SOURCE_PRECEDENCE
    }
    
    def __init__(self):
        """Initialize synchronization manager."""
        self._event_manager = get_event_manager()
        self._entity_tracker = EntityTracker()
        self._lock = asyncio.Lock()
        self._sync_history = {}
        self._conflict_history = {}
        self._logger = logging.getLogger("pygovpub.sync")
        
        # Subscribe to relevant events
        self._subscribe_to_events()
    
    def _subscribe_to_events(self):
        """Subscribe to events that require synchronization."""
        # Document events
        self._event_manager.subscribe(
            self._handle_document_event,
            category=EventCategory.DOCUMENT_UPDATE
        )
        
        # Bill events
        self._event_manager.subscribe(
            self._handle_bill_event,
            category=EventCategory.BILL_UPDATE
        )
    
    async def _handle_document_event(self, event: Event):
        """Handle document update events.
        
        Args:
            event: Document update event
        """
        if not event.payload or not isinstance(event.payload, (DocumentPublishedPayload, DocumentUpdatedPayload)):
            return
        
        # Get entity information
        entity_type = "document"
        entity_id = event.payload.document_id
        source = event.payload.source
        
        # Track the entity update
        await self._entity_tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event.id,
            data=event.payload.data
        )
        
        # Check for related bill events if this is a bill document
        if event.payload.document_type == "bill" and hasattr(event.payload, 'related_bills') and event.payload.related_bills:
            # This is a bill document, check for corresponding bill updates
            for bill_id in event.payload.related_bills:
                await self._check_bill_document_consistency(
                    bill_id=bill_id,
                    document_id=entity_id,
                    event=event
                )
    
    async def _handle_bill_event(self, event: Event):
        """Handle bill update events.
        
        Args:
            event: Bill update event
        """
        # Extract bill ID from event
        if not event.payload or not hasattr(event.payload, 'data') or not event.payload.data:
            return
            
        bill_data = event.payload.data
        if not isinstance(bill_data, dict):
            return
            
        # Get bill identifiers
        congress = bill_data.get("congress")
        bill_type = bill_data.get("type")
        bill_number = bill_data.get("number")
        
        if not all([congress, bill_type, bill_number]):
            return
            
        # Construct bill ID
        entity_type = "bill"
        entity_id = f"{congress}{bill_type}{bill_number}"
        source = event.payload.source
        
        # Track the entity update
        self._logger.debug(f"Tracking bill update for {entity_id} from {source}")
        await self._entity_tracker.track_update(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source,
            event_id=event.id,
            data=bill_data
        )
        
        # Check for related document events
        document_id = f"BILLS-{congress}{bill_type}{bill_number}"
        await self._check_bill_document_consistency(
            bill_id=entity_id,
            document_id=document_id,
            event=event
        )
    
    async def _check_bill_document_consistency(self, bill_id: str, document_id: str, event: Event):
        """Check consistency between bill and document data.
        
        Args:
            bill_id: Bill identifier
            document_id: Document identifier
            event: Triggering event
        """
        # Get bill data if available
        bill_updates = await self._entity_tracker.get_updates(
            entity_type="bill",
            entity_id=bill_id
        )
        
        # Get document data if available
        document_updates = await self._entity_tracker.get_updates(
            entity_type="document",
            entity_id=document_id
        )
        
        if not bill_updates or not document_updates:
            # Not enough data to check consistency
            return
            
        # Get latest updates from each source
        congress_bill = None
        govinfo_doc = None
        
        for update in bill_updates:
            if update["source"] == ApiSource.CONGRESS:
                congress_bill = update
                
        for update in document_updates:
            if update["source"] == ApiSource.GOVINFO:
                govinfo_doc = update
                
        if not congress_bill or not govinfo_doc:
            # Missing data from one source
            return
            
        # Check consistency
        await self._verify_consistency(
            entity_type="bill",
            entity_id=bill_id,
            sources=[congress_bill, govinfo_doc]
        )
    
    async def _verify_consistency(self, entity_type: str, entity_id: str, sources: List[Dict[str, Any]]):
        """Verify consistency between multiple data sources.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            sources: List of source data
        """
        # Generate a unique ID for this verification operation
        sync_id = uuid.uuid4()
        
        # Detect conflicts between sources
        conflicts = self._detect_conflicts(entity_type, entity_id, sources)
        
        if conflicts:
            # Conflicts detected
            self._logger.warning(
                f"Detected {len(conflicts)} conflicts for {entity_type} {entity_id} "
                f"across {len(sources)} sources"
            )
            
            # Try to resolve conflicts
            resolution_results = await self._resolve_conflicts(
                entity_type=entity_type,
                entity_id=entity_id,
                conflicts=conflicts
            )
            
            # Store conflict and resolution data
            async with self._lock:
                self._conflict_history[sync_id] = {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "timestamp": datetime.utcnow(),
                    "conflicts": conflicts,
                    "resolutions": resolution_results
                }
            
            # Record sync status based on resolution results
            if resolution_results["status"] == "resolved":
                sync_status = SyncStatus.COMPLETED
                consistent = True
                self._logger.info(
                    f"Successfully resolved conflicts for {entity_type} {entity_id}"
                )
            elif resolution_results["status"] == "partial":
                sync_status = SyncStatus.CONFLICT
                consistent = False
                self._logger.warning(
                    f"Partially resolved conflicts for {entity_type} {entity_id}, "
                    f"{resolution_results['unresolved_count']} conflicts require manual resolution"
                )
            else:
                sync_status = SyncStatus.CONFLICT
                consistent = False
                self._logger.error(
                    f"Failed to resolve conflicts for {entity_type} {entity_id}"
                )
                
            # Emit event for conflict detection/resolution
            await self._emit_conflict_event(
                entity_type=entity_type,
                entity_id=entity_id,
                conflicts=conflicts,
                resolutions=resolution_results
            )
        else:
            # No conflicts detected
            self._logger.info(
                f"No conflicts detected for {entity_type} {entity_id} "
                f"across {len(sources)} sources"
            )
            sync_status = SyncStatus.COMPLETED
            consistent = True
        
        # Record the verification in history
        async with self._lock:
            self._sync_history[sync_id] = {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "sources": [s["source"] for s in sources],
                "status": sync_status,
                "timestamp": datetime.utcnow(),
                "consistent": consistent,
                "conflict_id": sync_id if conflicts else None
            }
    
    def _detect_conflicts(self, entity_type: str, entity_id: str, sources: List[Dict[str, Any]]) -> List[FieldConflict]:
        """Detect conflicts between multiple data sources.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            sources: List of source data
            
        Returns:
            List of detected field conflicts
        """
        conflicts = []
        
        if len(sources) < 2:
            # Need at least two sources to detect conflicts
            return conflicts
        
        # For bills, check specific fields that should be consistent
        if entity_type == "bill":
            conflicts.extend(self._detect_bill_conflicts(entity_id, sources))
        # For documents, check specific document fields
        elif entity_type == "document":
            conflicts.extend(self._detect_document_conflicts(entity_id, sources))
        # Add other entity types as needed
        
        return conflicts
    
    def _detect_bill_conflicts(self, bill_id: str, sources: List[Dict[str, Any]]) -> List[FieldConflict]:
        """Detect conflicts in bill data.
        
        Args:
            bill_id: Bill identifier
            sources: List of source data
            
        Returns:
            List of detected field conflicts
        """
        conflicts = []
        
        # Get data from each source
        source_data = {}
        for source in sources:
            source_data[source["source"]] = source["data"]
        
        # Check core fields that should be consistent
        core_fields = [
            "congress",
            "type", 
            "number", 
            "title",
            "introducedDate", 
            "latestAction"
        ]
        
        # Check each core field for consistency
        for field in core_fields:
            # Only check fields that exist in multiple sources
            field_values = {}
            for source, data in source_data.items():
                if field in data:
                    field_values[source] = data[field]
            
            # If we have the field from multiple sources
            if len(field_values) >= 2:
                # Check for value differences
                values = list(field_values.values())
                if not all(v == values[0] for v in values):
                    # Conflict detected - different values for same field
                    conflict = FieldConflict(
                        field_path=f"bill.{field}",
                        conflict_type=ConflictType.VALUE_MISMATCH,
                        values=field_values,
                        description=f"Different values for bill {field}"
                    )
                    conflicts.append(conflict)
        
        # Check for temporal consistency in actions
        self._check_temporal_consistency(source_data, conflicts, bill_id)
        
        # Check for semantic contradictions
        self._check_semantic_consistency(source_data, conflicts, bill_id)
        
        # Check for reference consistency
        self._check_reference_consistency(source_data, conflicts, bill_id)
        
        return conflicts
    
    def _detect_document_conflicts(self, document_id: str, sources: List[Dict[str, Any]]) -> List[FieldConflict]:
        """Detect conflicts in document data.
        
        Args:
            document_id: Document identifier
            sources: List of source data
            
        Returns:
            List of detected field conflicts
        """
        conflicts = []
        
        # Get data from each source
        source_data = {}
        for source in sources:
            source_data[source["source"]] = source["data"]
        
        # Check core fields that should be consistent
        core_fields = [
            "packageId",
            "title", 
            "dateIssued", 
            "collectionCode"
        ]
        
        # Check each core field for consistency
        for field in core_fields:
            # Only check fields that exist in multiple sources
            field_values = {}
            for source, data in source_data.items():
                if field in data:
                    field_values[source] = data[field]
            
            # If we have the field from multiple sources
            if len(field_values) >= 2:
                # Check for value differences
                values = list(field_values.values())
                if not all(v == values[0] for v in values):
                    # Conflict detected - different values for same field
                    conflict = FieldConflict(
                        field_path=f"document.{field}",
                        conflict_type=ConflictType.VALUE_MISMATCH,
                        values=field_values,
                        description=f"Different values for document {field}"
                    )
                    conflicts.append(conflict)
        
        return conflicts
    
    def _check_temporal_consistency(self, source_data: Dict[ApiSource, Dict[str, Any]], 
                                    conflicts: List[FieldConflict], entity_id: str):
        """Check for temporal consistency issues.
        
        Args:
            source_data: Data from different sources
            conflicts: List to add detected conflicts to
            entity_id: Entity identifier
        """
        # Check for actions list consistency in bills
        actions_by_source = {}
        
        for source, data in source_data.items():
            if "actions" in data and isinstance(data["actions"], list):
                actions_by_source[source] = data["actions"]
        
        if len(actions_by_source) >= 2:
            # Check if action counts are significantly different
            action_counts = {src: len(actions) for src, actions in actions_by_source.items()}
            max_count = max(action_counts.values())
            min_count = min(action_counts.values())
            
            # If one source has 25% more actions than another, flag as conflict
            if min_count > 0 and max_count / min_count > 1.25:
                conflict = FieldConflict(
                    field_path="bill.actions",
                    conflict_type=ConflictType.TEMPORAL_INCONSISTENCY,
                    values=action_counts,
                    description=f"Different number of actions across sources for {entity_id}"
                )
                conflicts.append(conflict)
            
            # Check for matching latest action dates
            latest_action_dates = {}
            for source, actions in actions_by_source.items():
                if actions:
                    # Sort actions by date if available
                    sorted_actions = sorted(
                        actions, 
                        key=lambda a: a.get("actionDate", ""), 
                        reverse=True
                    )
                    latest_action_dates[source] = sorted_actions[0].get("actionDate")
            
            # If we have latest dates from multiple sources
            if len(latest_action_dates) >= 2:
                # Check if dates match
                dates = list(latest_action_dates.values())
                if not all(d == dates[0] for d in dates if d):
                    conflict = FieldConflict(
                        field_path="bill.latestActionDate",
                        conflict_type=ConflictType.TEMPORAL_INCONSISTENCY,
                        values=latest_action_dates,
                        description=f"Different latest action dates for {entity_id}"
                    )
                    conflicts.append(conflict)
    
    def _check_semantic_consistency(self, source_data: Dict[ApiSource, Dict[str, Any]], 
                                    conflicts: List[FieldConflict], entity_id: str):
        """Check for semantic contradictions.
        
        Args:
            source_data: Data from different sources
            conflicts: List to add detected conflicts to
            entity_id: Entity identifier
        """
        # Check for bill status conflicts
        status_values = {}
        
        for source, data in source_data.items():
            if "status" in data:
                status_values[source] = data["status"]
        
        if len(status_values) >= 2:
            values = list(status_values.values())
            if not all(v == values[0] for v in values):
                # Check for contradictory statuses
                # e.g., one source says "enacted" while another says "introduced"
                enacted_statuses = ["enacted", "became_law"]
                early_statuses = ["introduced", "referred"]
                
                has_enacted = any(v in enacted_statuses for v in values)
                has_early = any(v in early_statuses for v in values)
                
                if has_enacted and has_early:
                    conflict = FieldConflict(
                        field_path="bill.status",
                        conflict_type=ConflictType.SEMANTIC_CONTRADICTION,
                        values=status_values,
                        description=f"Contradictory bill statuses for {entity_id}"
                    )
                    conflicts.append(conflict)
    
    def _check_reference_consistency(self, source_data: Dict[ApiSource, Dict[str, Any]], 
                                    conflicts: List[FieldConflict], entity_id: str):
        """Check for reference consistency issues.
        
        Args:
            source_data: Data from different sources
            conflicts: List to add detected conflicts to
            entity_id: Entity identifier
        """
        # Check for sponsor consistency
        sponsor_values = {}
        
        for source, data in source_data.items():
            if "sponsors" in data and data["sponsors"]:
                sponsor = data["sponsors"][0] if isinstance(data["sponsors"], list) else data["sponsors"]
                if isinstance(sponsor, dict) and "bioguideId" in sponsor:
                    sponsor_values[source] = sponsor["bioguideId"]
        
        if len(sponsor_values) >= 2:
            values = list(sponsor_values.values())
            if not all(v == values[0] for v in values):
                conflict = FieldConflict(
                    field_path="bill.sponsor",
                    conflict_type=ConflictType.REFERENCE_INCONSISTENCY,
                    values=sponsor_values,
                    description=f"Different sponsor references for {entity_id}"
                )
                conflicts.append(conflict)
    
    async def _resolve_conflicts(self, entity_type: str, entity_id: str, 
                                conflicts: List[FieldConflict]) -> Dict[str, Any]:
        """Attempt to resolve conflicts based on resolution strategies.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            conflicts: List of detected conflicts
            
        Returns:
            Resolution results including status and counts
        """
        # Initialize resolution results
        results = {
            "status": "none",
            "total_count": len(conflicts),
            "resolved_count": 0,
            "unresolved_count": 0,
            "resolution_strategies": {}
        }
        
        if not conflicts:
            return results
        
        # Track resolution statistics
        for conflict in conflicts:
            # Determine the appropriate resolution strategy
            strategy = self._get_resolution_strategy(entity_type, conflict.field_path)
            
            # Apply the resolution strategy
            resolved, resolved_value = await self._apply_resolution_strategy(
                entity_type=entity_type,
                conflict=conflict,
                strategy=strategy
            )
            
            # Update conflict with resolution information
            if resolved:
                conflict.resolution = "resolved"
                conflict.resolved_value = resolved_value
                conflict.resolution_time = datetime.utcnow()
                conflict.resolution_strategy = strategy
                results["resolved_count"] += 1
                
                # Track which strategies were successful
                if strategy not in results["resolution_strategies"]:
                    results["resolution_strategies"][strategy] = 0
                results["resolution_strategies"][strategy] += 1
            else:
                conflict.resolution = "unresolved"
                results["unresolved_count"] += 1
        
        # Set overall status
        if results["resolved_count"] == results["total_count"]:
            results["status"] = "resolved"
        elif results["resolved_count"] > 0:
            results["status"] = "partial"
        else:
            results["status"] = "unresolved"
        
        return results
    
    def _get_resolution_strategy(self, entity_type: str, field_path: str) -> ConflictResolutionStrategy:
        """Get the appropriate resolution strategy for a field.
        
        Args:
            entity_type: Type of entity
            field_path: Path to the field with conflict
            
        Returns:
            Resolution strategy to apply
        """
        # Check if there's a field-specific strategy
        if field_path in self.FIELD_STRATEGIES:
            return self.FIELD_STRATEGIES[field_path]
            
        # Fall back to default strategy
        return self.FIELD_STRATEGIES["default"]
    
    async def _apply_resolution_strategy(self, entity_type: str, conflict: FieldConflict,
                                         strategy: ConflictResolutionStrategy) -> Tuple[bool, Any]:
        """Apply a resolution strategy to a conflict.
        
        Args:
            entity_type: Type of entity
            conflict: Field conflict to resolve
            strategy: Resolution strategy to apply
            
        Returns:
            Tuple of (resolved successfully, resolved value)
        """
        if strategy == ConflictResolutionStrategy.SOURCE_PRECEDENCE:
            return self._resolve_by_source_precedence(entity_type, conflict)
            
        elif strategy == ConflictResolutionStrategy.MOST_RECENT:
            return self._resolve_by_most_recent(conflict)
            
        elif strategy == ConflictResolutionStrategy.FIELD_LEVEL_MERGE:
            return self._resolve_by_field_merge(conflict)
            
        elif strategy == ConflictResolutionStrategy.MANUAL:
            # Cannot resolve automatically
            return False, None
            
        # Unknown strategy
        return False, None
    
    def _resolve_by_source_precedence(self, entity_type: str, conflict: FieldConflict) -> Tuple[bool, Any]:
        """Resolve conflict by source precedence.
        
        Args:
            entity_type: Type of entity
            conflict: Field conflict to resolve
            
        Returns:
            Tuple of (resolved successfully, resolved value)
        """
        # Get the precedence list for this entity type
        precedence = self.SOURCE_PRECEDENCE.get(entity_type, self.SOURCE_PRECEDENCE["default"])
        
        # Try sources in order of precedence
        for source in precedence:
            if source in conflict.values:
                return True, conflict.values[source]
                
        # Couldn't resolve using precedence
        return False, None
    
    def _resolve_by_most_recent(self, conflict: FieldConflict) -> Tuple[bool, Any]:
        """Resolve conflict by using the most recent value.
        
        Args:
            conflict: Field conflict to resolve
            
        Returns:
            Tuple of (resolved successfully, resolved value)
        """
        # This strategy requires timestamp information which we may not have directly
        # In a real implementation, we would use update timestamps to determine the most recent
        # For now, as a simplification, we'll use a default order of precedence
        
        # Since we don't have actual timestamps in this simplified version,
        # we'll fall back to source precedence for the demo
        primary_sources = [ApiSource.CONGRESS, ApiSource.GOVINFO]
        
        for source in primary_sources:
            if source in conflict.values:
                return True, conflict.values[source]
                
        return False, None
    
    def _resolve_by_field_merge(self, conflict: FieldConflict) -> Tuple[bool, Any]:
        """Resolve conflict by merging values at the field level.
        
        Args:
            conflict: Field conflict to resolve
            
        Returns:
            Tuple of (resolved successfully, resolved value)
        """
        # Field merging depends on the specific field type
        if conflict.field_path == "bill.actions":
            # For actions, we would merge the lists, remove duplicates, and sort by date
            # This is a simplified implementation
            all_actions = []
            for source, value in conflict.values.items():
                if isinstance(value, list):
                    all_actions.extend(value)
            
            # In a real implementation, we would deduplicate and sort actions
            # For now, just return the combined list
            return True, all_actions
            
        elif conflict.field_path == "bill.versions":
            # Similar approach for versions
            all_versions = []
            for source, value in conflict.values.items():
                if isinstance(value, list):
                    all_versions.extend(value)
            
            # In a real implementation, we would deduplicate versions
            return True, all_versions
            
        # For other fields, merging may not be possible
        return False, None
    
    async def _emit_conflict_event(self, entity_type: str, entity_id: str, 
                                   conflicts: List[FieldConflict], resolutions: Dict[str, Any]):
        """Emit an event for conflict detection and resolution.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            conflicts: List of detected conflicts
            resolutions: Resolution results
        """
        # Prepare event data
        conflict_data = {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "detection_time": datetime.utcnow(),
            "conflict_count": len(conflicts),
            "resolution_status": resolutions["status"],
            "resolved_count": resolutions["resolved_count"],
            "unresolved_count": resolutions["unresolved_count"]
        }
        
        # In a real implementation, we would create and emit the event:
        # await self._event_manager.create_and_emit_event(
        #     event_type=EventType.SYNC_CONFLICT_DETECTED,
        #     payload=conflict_data
        # )
        
        # Log the conflict information
        self._logger.warning(f"Sync conflict detected: {conflict_data}")
    
    async def get_conflicts(self, entity_type: str, entity_id: str) -> List[Dict[str, Any]]:
        """Get conflicts for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            List of conflicts for the entity
        """
        conflicts = []
        
        for conflict_id, conflict_data in self._conflict_history.items():
            if (conflict_data["entity_type"] == entity_type and 
                conflict_data["entity_id"] == entity_id):
                conflicts.append({
                    "conflict_id": conflict_id,
                    "timestamp": conflict_data["timestamp"],
                    "conflicts": conflict_data["conflicts"],
                    "resolutions": conflict_data["resolutions"]
                })
        
        return sorted(conflicts, key=lambda x: x["timestamp"], reverse=True)
    
    async def resolve_conflict_manually(self, conflict_id: UUID, field_path: str, 
                                       resolved_value: Any) -> bool:
        """Manually resolve a specific conflict.
        
        Args:
            conflict_id: Conflict ID
            field_path: Path to the field with conflict
            resolved_value: Value to use for resolution
            
        Returns:
            Whether the resolution was successful
        """
        if conflict_id not in self._conflict_history:
            return False
        
        conflict_data = self._conflict_history[conflict_id]
        
        # Find the specific field conflict
        for conflict in conflict_data["conflicts"]:
            if conflict.field_path == field_path and conflict.resolution == "unresolved":
                # Update the conflict resolution
                conflict.resolution = "manual"
                conflict.resolved_value = resolved_value
                conflict.resolution_time = datetime.utcnow()
                conflict.resolution_strategy = ConflictResolutionStrategy.MANUAL
                
                # Update resolution statistics
                if "resolutions" in conflict_data:
                    conflict_data["resolutions"]["resolved_count"] += 1
                    conflict_data["resolutions"]["unresolved_count"] -= 1
                    
                    # Update overall status
                    if conflict_data["resolutions"]["unresolved_count"] == 0:
                        conflict_data["resolutions"]["status"] = "resolved"
                    else:
                        conflict_data["resolutions"]["status"] = "partial"
                
                return True
        
        return False
    
    async def get_sync_status(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get synchronization status for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            Synchronization status if available
        """
        # Find the most recent sync record
        latest_sync = None
        latest_time = None
        
        for sync_id, sync_data in self._sync_history.items():
            if sync_data["entity_type"] == entity_type and sync_data["entity_id"] == entity_id:
                if latest_time is None or sync_data["timestamp"] > latest_time:
                    latest_sync = sync_data
                    latest_time = sync_data["timestamp"]
                    
        return latest_sync


# Global sync manager instance
_sync_manager = None


def get_sync_manager() -> SyncManager:
    """Get the global synchronization manager instance.
    
    Returns:
        Global synchronization manager instance
    """
    global _sync_manager
    if _sync_manager is None:
        _sync_manager = SyncManager()
    return _sync_manager