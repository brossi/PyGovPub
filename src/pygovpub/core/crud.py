"""
Generic CRUD operations for database entities.

This module provides generic Create, Read, Update, and Delete operations
for database entities using SQLModel.
"""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union
from sqlmodel import Session, select, SQLModel

# Configure logging
logger = logging.getLogger(__name__)

# Type variable for model classes
ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = Dict[str, Any]
UpdateSchemaType = Dict[str, Any]


def create_entity(
    session: Session, 
    model_class: Type[ModelType], 
    entity_data: CreateSchemaType
) -> ModelType:
    """
    Create a new database entity.
    
    Args:
        session: SQLModel Session
        model_class: SQLModel class to create
        entity_data: Dictionary of entity attribute values
        
    Returns:
        Created entity instance
    """
    entity = model_class(**entity_data)
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


def get_entity(
    session: Session, 
    model_class: Type[ModelType], 
    entity_id: Any
) -> Optional[ModelType]:
    """
    Get a single entity by ID.
    
    Args:
        session: SQLModel Session
        model_class: SQLModel class to query
        entity_id: Primary key value
        
    Returns:
        Entity instance or None if not found
    """
    return session.get(model_class, entity_id)


def get_entities(
    session: Session,
    model_class: Type[ModelType],
    *,
    filters: Optional[Dict[str, Any]] = None,
    skip: int = 0,
    limit: Optional[int] = None,
    order_by: Optional[str] = None,
    descending: bool = False
) -> List[ModelType]:
    """
    Get multiple entities with optional filtering and pagination.
    
    Args:
        session: SQLModel Session
        model_class: SQLModel class to query
        filters: Optional dictionary of attribute=value filters
        skip: Number of records to skip
        limit: Maximum number of records to return
        order_by: Attribute to order by
        descending: Whether to sort in descending order
        
    Returns:
        List of entity instances
    """
    query = select(model_class)
    
    # Apply filters if provided
    if filters:
        for attr, value in filters.items():
            query = query.where(getattr(model_class, attr) == value)
    
    # Apply ordering if specified
    if order_by:
        column = getattr(model_class, order_by)
        if descending:
            query = query.order_by(column.desc())
        else:
            query = query.order_by(column)
    
    # Apply offset and limit
    if skip:
        query = query.offset(skip)
    if limit:
        query = query.limit(limit)
    
    # Execute query
    results = session.exec(query).all()
    return results


def update_entity(
    session: Session,
    model_class: Type[ModelType],
    entity_id: Any,
    update_data: UpdateSchemaType
) -> Optional[ModelType]:
    """
    Update an existing entity.
    
    Args:
        session: SQLModel Session
        model_class: SQLModel class to update
        entity_id: Primary key value
        update_data: Dictionary of attributes to update
        
    Returns:
        Updated entity instance or None if not found
    """
    entity = session.get(model_class, entity_id)
    if not entity:
        return None
    
    # Update entity attributes
    for key, value in update_data.items():
        setattr(entity, key, value)
    
    session.add(entity)
    session.commit()
    session.refresh(entity)
    return entity


def delete_entity(
    session: Session,
    model_class: Type[ModelType],
    entity_id: Any
) -> bool:
    """
    Delete an entity by ID.
    
    Args:
        session: SQLModel Session
        model_class: SQLModel class to delete from
        entity_id: Primary key value
        
    Returns:
        True if entity was deleted, False if not found
    """
    entity = session.get(model_class, entity_id)
    if not entity:
        return False
    
    session.delete(entity)
    session.commit()
    return True


def count_entities(
    session: Session,
    model_class: Type[ModelType],
    *,
    filters: Optional[Dict[str, Any]] = None
) -> int:
    """
    Count entities with optional filtering.
    
    Args:
        session: SQLModel Session
        model_class: SQLModel class to count
        filters: Optional dictionary of attribute=value filters
        
    Returns:
        Count of matching entities
    """
    query = select(model_class)
    
    # Apply filters if provided
    if filters:
        for attr, value in filters.items():
            query = query.where(getattr(model_class, attr) == value)
    
    # Execute count query - use len() since count() is not available
    results = session.exec(query).all()
    return len(results)


class CRUDBase(Generic[ModelType]):
    """
    Base class for CRUD operations on a specific model.
    
    Provides a reusable interface for common database operations.
    """
    
    def __init__(self, model: Type[ModelType]):
        """
        Initialize CRUD with model class.
        
        Args:
            model: SQLModel class to operate on
        """
        self.model = model
    
    def create(self, session: Session, obj_in: CreateSchemaType) -> ModelType:
        """
        Create a new entity.
        
        Args:
            session: SQLModel Session
            obj_in: Dictionary of entity attribute values
            
        Returns:
            Created entity instance
        """
        return create_entity(session, self.model, obj_in)
    
    def get(self, session: Session, entity_id: Any) -> Optional[ModelType]:
        """
        Get a single entity by ID.
        
        Args:
            session: SQLModel Session
            entity_id: Primary key value
            
        Returns:
            Entity instance or None if not found
        """
        return get_entity(session, self.model, entity_id)
    
    def get_multi(
        self,
        session: Session,
        *,
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: Optional[int] = None,
        order_by: Optional[str] = None,
        descending: bool = False
    ) -> List[ModelType]:
        """
        Get multiple entities with optional filtering and pagination.
        
        Args:
            session: SQLModel Session
            filters: Optional dictionary of attribute=value filters
            skip: Number of records to skip
            limit: Maximum number of records to return
            order_by: Attribute to order by
            descending: Whether to sort in descending order
            
        Returns:
            List of entity instances
        """
        return get_entities(
            session, 
            self.model, 
            filters=filters, 
            skip=skip, 
            limit=limit,
            order_by=order_by,
            descending=descending
        )
    
    def update(
        self,
        session: Session,
        entity_id: Any,
        obj_in: UpdateSchemaType
    ) -> Optional[ModelType]:
        """
        Update an existing entity.
        
        Args:
            session: SQLModel Session
            entity_id: Primary key value
            obj_in: Dictionary of attributes to update
            
        Returns:
            Updated entity instance or None if not found
        """
        return update_entity(session, self.model, entity_id, obj_in)
    
    def delete(self, session: Session, entity_id: Any) -> bool:
        """
        Delete an entity by ID.
        
        Args:
            session: SQLModel Session
            entity_id: Primary key value
            
        Returns:
            True if entity was deleted, False if not found
        """
        return delete_entity(session, self.model, entity_id)
    
    def count(
        self,
        session: Session,
        filters: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Count entities with optional filtering.
        
        Args:
            session: SQLModel Session
            filters: Optional dictionary of attribute=value filters
            
        Returns:
            Count of matching entities
        """
        return count_entities(session, self.model, filters=filters)