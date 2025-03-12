"""
Query plan analysis and optimization for storage operations.

This module provides functionality for analyzing and optimizing database
queries, particularly for vector and hybrid searches. It helps determine
the most efficient way to execute queries across different storage providers.
"""

import time
from typing import Any, Dict, List, Optional, Type, Union, TypeVar
import math

import structlog
from prometheus_client import Counter, Histogram, Gauge

# Set up structured logging
logger = structlog.get_logger()

# Set up metrics
QUERY_PLANS_CREATED = Counter(
    "query_plans_created_total", 
    "Total query plans created", 
    ["operation", "provider_type"]
)
QUERY_PLAN_COST = Histogram(
    "query_plan_cost",
    "Estimated query plan cost",
    ["operation", "provider_type"]
)
QUERY_OPTIMIZATIONS_APPLIED = Counter(
    "query_optimizations_applied_total",
    "Total query optimizations applied",
    ["optimization_type", "provider_type"]
)
QUERY_PLAN_EXECUTION_TIME = Histogram(
    "query_plan_execution_time_seconds",
    "Query plan execution time in seconds",
    ["operation", "provider_type"]
)


class QueryPlan:
    """Base class for all query plans"""
    
    def __init__(self, 
                provider_type: str, 
                operation: str, 
                estimated_cost: float,
                estimated_time_ms: int):
        """
        Initialize a generic query plan.
        
        Args:
            provider_type: Storage provider type
            operation: Operation type
            estimated_cost: Estimated cost (arbitrary units)
            estimated_time_ms: Estimated execution time in milliseconds
        """
        self.provider_type = provider_type
        self.operation = operation
        self.estimated_cost = estimated_cost
        self.estimated_time_ms = estimated_time_ms
        self.optimizations = []  # List of suggested optimizations
        
        # Track metrics
        QUERY_PLANS_CREATED.labels(
            operation=operation,
            provider_type=provider_type
        ).inc()
        
        QUERY_PLAN_COST.labels(
            operation=operation,
            provider_type=provider_type
        ).observe(estimated_cost)
    
    def add_optimization(self, name: str, description: str, cost_reduction: float):
        """
        Add an optimization to the query plan.
        
        Args:
            name: Optimization name
            description: Optimization description
            cost_reduction: Estimated cost reduction
        """
        optimization = {
            "name": name,
            "description": description,
            "cost_reduction": cost_reduction
        }
        self.optimizations.append(optimization)
        
        # Track metrics
        QUERY_OPTIMIZATIONS_APPLIED.labels(
            optimization_type=name,
            provider_type=self.provider_type
        ).inc()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert plan to dictionary representation.
        
        Returns:
            Dictionary representation of the plan
        """
        return {
            "provider_type": self.provider_type,
            "operation": self.operation,
            "estimated_cost": self.estimated_cost,
            "estimated_time_ms": self.estimated_time_ms,
            "optimizations": self.optimizations
        }


class VectorSearchPlan(QueryPlan):
    """Specialized query plan for vector search operations"""
    
    def __init__(self, 
                provider_type: str, 
                table_name: str, 
                vector_dim: int,
                filter_count: int,
                has_index: bool,
                estimated_result_count: int,
                estimated_cost: float,
                estimated_time_ms: int):
        """
        Initialize a vector search query plan.
        
        Args:
            provider_type: Storage provider type
            table_name: Table or collection name
            vector_dim: Vector dimension
            filter_count: Number of filter criteria
            has_index: Whether vector index exists
            estimated_result_count: Estimated number of results
            estimated_cost: Estimated cost (arbitrary units)
            estimated_time_ms: Estimated execution time in milliseconds
        """
        super().__init__(
            provider_type=provider_type,
            operation="vector_search",
            estimated_cost=estimated_cost,
            estimated_time_ms=estimated_time_ms
        )
        self.table_name = table_name
        self.vector_dim = vector_dim
        self.filter_count = filter_count
        self.has_index = has_index
        self.estimated_result_count = estimated_result_count
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert plan to dictionary representation.
        
        Returns:
            Dictionary representation of the plan
        """
        base_dict = super().to_dict()
        base_dict.update({
            "table_name": self.table_name,
            "vector_dim": self.vector_dim,
            "filter_count": self.filter_count,
            "has_index": self.has_index,
            "estimated_result_count": self.estimated_result_count
        })
        return base_dict


class HybridSearchPlan(QueryPlan):
    """Specialized query plan for hybrid search operations"""
    
    def __init__(self, 
                provider_type: str, 
                table_name: str, 
                vector_dim: int,
                text_query_length: int,
                filter_count: int,
                has_index: bool,
                estimated_result_count: int,
                estimated_cost: float,
                estimated_time_ms: int):
        """
        Initialize a hybrid search query plan.
        
        Args:
            provider_type: Storage provider type
            table_name: Table or collection name
            vector_dim: Vector dimension
            text_query_length: Length of text query (word count)
            filter_count: Number of filter criteria
            has_index: Whether vector index exists
            estimated_result_count: Estimated number of results
            estimated_cost: Estimated cost (arbitrary units)
            estimated_time_ms: Estimated execution time in milliseconds
        """
        super().__init__(
            provider_type=provider_type,
            operation="hybrid_search",
            estimated_cost=estimated_cost,
            estimated_time_ms=estimated_time_ms
        )
        self.table_name = table_name
        self.vector_dim = vector_dim
        self.text_query_length = text_query_length
        self.filter_count = filter_count
        self.has_index = has_index
        self.estimated_result_count = estimated_result_count
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert plan to dictionary representation.
        
        Returns:
            Dictionary representation of the plan
        """
        base_dict = super().to_dict()
        base_dict.update({
            "table_name": self.table_name,
            "vector_dim": self.vector_dim,
            "text_query_length": self.text_query_length,
            "filter_count": self.filter_count,
            "has_index": self.has_index,
            "estimated_result_count": self.estimated_result_count
        })
        return base_dict


class QueryPlanAnalyzer:
    """Analyzes queries to create optimal query plans"""
    
    def __init__(self):
        """Initialize the query plan analyzer."""
        pass
    
    def analyze_vector_search(self, 
                             provider,
                             model_class,
                             query_vector: List[float], 
                             filter_criteria: Optional[Dict[str, Any]] = None,
                             limit: int = 10) -> VectorSearchPlan:
        """
        Analyze a vector search query and create a query plan.
        
        Args:
            provider: Storage provider
            model_class: Model class for the search
            query_vector: Query vector
            filter_criteria: Optional filter criteria
            limit: Result limit
            
        Returns:
            VectorSearchPlan instance
        """
        # Get provider type
        provider_type = getattr(provider, "db_type", "unknown")
        
        # Get table name
        table_name = getattr(model_class, "__tablename__", model_class.__name__.lower())
        
        # Get vector dimension
        vector_dim = len(query_vector)
        
        # Count filters
        filter_count = len(filter_criteria) if filter_criteria else 0
        
        # Check if table has index
        has_index = False
        if hasattr(provider, "table_info") and table_name in provider.table_info:
            has_index = provider.table_info[table_name].get("has_vector_index", False)
        
        # Estimate cost and time
        base_cost = 10.0  # Base cost
        
        # Adjust for vector dimension
        dim_factor = math.log(vector_dim) / math.log(100)  # Logarithmic scaling
        
        # Adjust for index presence
        index_factor = 0.3 if has_index else 3.0  # Much higher cost without index
        
        # Adjust for filter complexity
        filter_factor = 1.0 + (filter_count * 0.2)  # Each filter adds 20% cost
        
        # Calculate final cost
        estimated_cost = base_cost * dim_factor * index_factor * filter_factor
        
        # Estimate execution time (ms)
        estimated_time_ms = int(estimated_cost * 10)  # Simple mapping from cost to time
        
        # Estimate result count
        est_result_count = max(1, min(limit, int(100 / (filter_count + 1) if filter_count else 100)))
        
        # Create plan
        plan = VectorSearchPlan(
            provider_type=provider_type,
            table_name=table_name,
            vector_dim=vector_dim,
            filter_count=filter_count,
            has_index=has_index,
            estimated_result_count=est_result_count,
            estimated_cost=estimated_cost,
            estimated_time_ms=estimated_time_ms
        )
        
        logger.debug(
            "Created vector search plan",
            provider=provider_type,
            table=table_name,
            cost=estimated_cost,
            time_ms=estimated_time_ms
        )
        
        return plan
    
    def analyze_hybrid_search(self, 
                             provider,
                             model_class,
                             query_text: str, 
                             query_vector: Optional[List[float]] = None,
                             filter_criteria: Optional[Dict[str, Any]] = None,
                             limit: int = 10) -> HybridSearchPlan:
        """
        Analyze a hybrid search query and create a query plan.
        
        Args:
            provider: Storage provider
            model_class: Model class for the search
            query_text: Text query
            query_vector: Optional query vector (None = generate from text)
            filter_criteria: Optional filter criteria
            limit: Result limit
            
        Returns:
            HybridSearchPlan instance
        """
        # Get provider type
        provider_type = getattr(provider, "db_type", "unknown")
        
        # Get table name
        table_name = getattr(model_class, "__tablename__", model_class.__name__.lower())
        
        # Get vector dimension
        vector_dim = len(query_vector) if query_vector else 384  # Default dimension
        
        # Count filters
        filter_count = len(filter_criteria) if filter_criteria else 0
        
        # Calculate text query length (word count)
        text_query_length = len(query_text.split())
        
        # Check if table has index
        has_index = False
        if hasattr(provider, "table_info") and table_name in provider.table_info:
            has_index = provider.table_info[table_name].get("has_vector_index", False)
        
        # Estimate cost and time
        base_cost = 12.0  # Higher base cost than vector-only search
        
        # Adjust for vector dimension
        dim_factor = math.log(vector_dim) / math.log(100)  # Logarithmic scaling
        
        # Adjust for text query length
        text_factor = 1.0 + (text_query_length * 0.03)  # Each word adds 3% cost
        
        # Adjust for index presence
        index_factor = 0.5 if has_index else 2.5  # Higher cost without index
        
        # Adjust for filter complexity
        filter_factor = 1.0 + (filter_count * 0.15)  # Each filter adds 15% cost
        
        # Calculate final cost
        estimated_cost = base_cost * dim_factor * text_factor * index_factor * filter_factor
        
        # Estimate execution time (ms)
        estimated_time_ms = int(estimated_cost * 12)  # Simple mapping from cost to time
        
        # Estimate result count
        text_relevance = 100 / (text_query_length + 1)  # More words = more specific = fewer results
        est_result_count = max(1, min(limit, int(text_relevance / (filter_count + 1))))
        
        # Create plan
        plan = HybridSearchPlan(
            provider_type=provider_type,
            table_name=table_name,
            vector_dim=vector_dim,
            text_query_length=text_query_length,
            filter_count=filter_count,
            has_index=has_index,
            estimated_result_count=est_result_count,
            estimated_cost=estimated_cost,
            estimated_time_ms=estimated_time_ms
        )
        
        logger.debug(
            "Created hybrid search plan",
            provider=provider_type,
            table=table_name,
            text_length=text_query_length,
            cost=estimated_cost,
            time_ms=estimated_time_ms
        )
        
        return plan


class QueryOptimizer:
    """Optimizes query plans for better performance"""
    
    def __init__(self):
        """Initialize the query optimizer."""
        pass
    
    def optimize(self, plan: Union[QueryPlan, VectorSearchPlan, HybridSearchPlan]) -> Union[QueryPlan, VectorSearchPlan, HybridSearchPlan]:
        """
        Optimize a query plan.
        
        Args:
            plan: Query plan to optimize
            
        Returns:
            Optimized query plan
        """
        # Use specific optimizers based on plan type
        if isinstance(plan, VectorSearchPlan):
            return self._optimize_vector_search(plan)
        elif isinstance(plan, HybridSearchPlan):
            return self._optimize_hybrid_search(plan)
        else:
            # Generic optimization
            # Currently no generic optimizations
            return plan
    
    def _optimize_vector_search(self, plan: VectorSearchPlan) -> VectorSearchPlan:
        """
        Optimize a vector search plan.
        
        Args:
            plan: Vector search plan to optimize
            
        Returns:
            Optimized vector search plan
        """
        # Check for missing index
        if not plan.has_index:
            plan.add_optimization(
                name="create_vector_index",
                description="Create a vector index for faster similarity search",
                cost_reduction=plan.estimated_cost * 0.7  # Significant cost reduction
            )
        
        # Check for high filter count
        if plan.filter_count > 5:
            plan.add_optimization(
                name="reduce_filter_count",
                description="Reduce number of filters to improve performance",
                cost_reduction=plan.estimated_cost * 0.2 * (plan.filter_count / 5)
            )
        
        # Check for high vector dimension
        if plan.vector_dim > 1024:
            plan.add_optimization(
                name="reduce_vector_dimension",
                description="Reduce vector dimension using dimensionality reduction",
                cost_reduction=plan.estimated_cost * 0.3
            )
        
        # Use vector index if available
        if plan.has_index:
            plan.add_optimization(
                name="use_vector_index",
                description="Use vector index for efficient ANN search",
                cost_reduction=plan.estimated_cost * 0.1  # Small reduction since already accounted for
            )
        
        return plan
    
    def _optimize_hybrid_search(self, plan: HybridSearchPlan) -> HybridSearchPlan:
        """
        Optimize a hybrid search plan.
        
        Args:
            plan: Hybrid search plan to optimize
            
        Returns:
            Optimized hybrid search plan
        """
        # Check for missing index
        if not plan.has_index:
            plan.add_optimization(
                name="create_vector_index",
                description="Create a vector index for faster similarity search component",
                cost_reduction=plan.estimated_cost * 0.5  # Less impact than pure vector search
            )
        
        # Check for high filter count
        if plan.filter_count > 5:
            plan.add_optimization(
                name="reduce_filter_count",
                description="Reduce number of filters to improve performance",
                cost_reduction=plan.estimated_cost * 0.15 * (plan.filter_count / 5)
            )
        
        # Check for very long text query
        if plan.text_query_length > 20:
            plan.add_optimization(
                name="simplify_text_query",
                description="Simplify text query to key terms for better performance",
                cost_reduction=plan.estimated_cost * 0.25
            )
        
        # Check for high vector dimension
        if plan.vector_dim > 1024:
            plan.add_optimization(
                name="reduce_vector_dimension",
                description="Reduce vector dimension using dimensionality reduction",
                cost_reduction=plan.estimated_cost * 0.2
            )
        
        return plan


def get_query_plan_analyzer() -> QueryPlanAnalyzer:
    """
    Get a query plan analyzer instance.
    
    Returns:
        QueryPlanAnalyzer instance
    """
    return QueryPlanAnalyzer()


def get_query_optimizer() -> QueryOptimizer:
    """
    Get a query optimizer instance.
    
    Returns:
        QueryOptimizer instance
    """
    return QueryOptimizer()


def measure_execution_time(plan: QueryPlan, func, *args, **kwargs):
    """
    Measure execution time of a function with a query plan.
    
    Args:
        plan: Query plan
        func: Function to execute
        *args: Positional arguments for function
        **kwargs: Keyword arguments for function
        
    Returns:
        Result of function execution
    """
    start_time = time.time()
    result = func(*args, **kwargs)
    execution_time = time.time() - start_time
    
    # Record actual execution time
    QUERY_PLAN_EXECUTION_TIME.labels(
        operation=plan.operation,
        provider_type=plan.provider_type
    ).observe(execution_time)
    
    # Log comparison of estimated vs actual time
    estimated_seconds = plan.estimated_time_ms / 1000.0
    logger.debug(
        "Query execution completed",
        operation=plan.operation,
        provider=plan.provider_type,
        estimated_time=estimated_seconds,
        actual_time=execution_time,
        accuracy=f"{(1 - abs(estimated_seconds - execution_time) / execution_time) * 100:.1f}%"
    )
    
    return result