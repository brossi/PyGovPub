"""
Entity tracker for synchronization.

This module provides tracking of entity updates from different sources
to enable synchronization and consistency checks.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from pygovpub.auth.models import ApiSource


class EntityTracker:
    """Tracks entity updates from different sources."""
    
    def __init__(self):
        """Initialize entity tracker."""
        self._entities = {}
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger("pygovpub.sync.tracker")
    
    async def track_update(
        self,
        entity_type: str,
        entity_id: str,
        source: ApiSource,
        event_id: UUID,
        data: Dict[str, Any]
    ) -> None:
        """Track an entity update from a specific source.
        
        Args:
            entity_type: Type of entity (e.g., "bill", "document")
            entity_id: Unique identifier for the entity
            source: Source of the update
            event_id: Event ID that triggered this update
            data: Update data
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        async with self._lock:
            if entity_key not in self._entities:
                self._entities[entity_key] = []
                
            # Add update to the entity's history
            self._entities[entity_key].append({
                "source": source,
                "event_id": event_id,
                "timestamp": datetime.utcnow(),
                "data": data
            })
            
            self._logger.debug(
                f"Tracked update for {entity_type} {entity_id} "
                f"from {source} (event: {event_id})"
            )
    
    async def get_updates(
        self, 
        entity_type: str, 
        entity_id: str, 
        source: Optional[ApiSource] = None
    ) -> List[Dict[str, Any]]:
        """Get updates for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            source: Optional filter by source
            
        Returns:
            List of updates for the entity
        """
        entity_key = f"{entity_type}:{entity_id}"
        
        if entity_key not in self._entities:
            return []
            
        updates = self._entities[entity_key]
        
        if source:
            # Filter by source if specified
            updates = [update for update in updates if update["source"] == source]
            
        return sorted(updates, key=lambda x: x["timestamp"], reverse=True)
    
    async def get_latest_update(
        self, 
        entity_type: str, 
        entity_id: str, 
        source: Optional[ApiSource] = None
    ) -> Optional[Dict[str, Any]]:
        """Get the latest update for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            source: Optional filter by source
            
        Returns:
            Latest update if available
        """
        updates = await self.get_updates(
            entity_type=entity_type,
            entity_id=entity_id,
            source=source
        )
        
        if not updates:
            return None
            
        return updates[0]  # Already sorted by timestamp (newest first)
    
    async def get_sources_for_entity(self, entity_type: str, entity_id: str) -> Set[ApiSource]:
        """Get all sources that have updates for an entity.
        
        Args:
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            Set of sources with updates for the entity
        """
        updates = await self.get_updates(
            entity_type=entity_type,
            entity_id=entity_id
        )
        
        return {update["source"] for update in updates}
    
    async def clear_history(self, entity_type: Optional[str] = None, entity_id: Optional[str] = None):
        """Clear update history.
        
        Args:
            entity_type: Optional entity type to clear
            entity_id: Optional entity ID to clear
        """
        async with self._lock:
            if entity_type and entity_id:
                # Clear specific entity
                entity_key = f"{entity_type}:{entity_id}"
                if entity_key in self._entities:
                    del self._entities[entity_key]
            elif entity_type:
                # Clear all entities of a specific type
                keys_to_delete = []
                for key in self._entities.keys():
                    if key.startswith(f"{entity_type}:"):
                        keys_to_delete.append(key)
                
                for key in keys_to_delete:
                    del self._entities[key]
            else:
                # Clear all history
                self._entities = {}