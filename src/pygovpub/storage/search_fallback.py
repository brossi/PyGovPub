"""
Search fallback strategies for storage providers.

This module implements fallback strategies for search operations,
particularly for vector and hybrid searches. It provides mechanisms
for graceful degradation when primary search methods fail or return
low-quality results.
"""

import time
import copy
import logging
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar, Union

import structlog
from prometheus_client import Counter, Histogram, Gauge
from pydantic import BaseModel, Field

# Set up structured logging
logger = structlog.get_logger()

# Set up metrics
SEARCH_FALLBACKS = Counter(
    "search_fallbacks_total",
    "Total search fallbacks by strategy type",
    ["strategy", "reason", "provider_type"]
)

SEARCH_FALLBACK_LATENCY = Histogram(
    "search_fallback_latency_seconds",
    "Search fallback latency in seconds",
    ["strategy", "provider_type"]
)

SEARCH_QUALITY_SCORES = Histogram(
    "search_quality_scores",
    "Search quality scores by search type",
    ["search_type", "provider_type"]
)

T = TypeVar("T")


class FallbackConfig(BaseModel):
    """Configuration for search fallback behavior."""
    
    # Quality thresholds for different search strategies
    vector_quality_threshold: float = Field(0.6, description="Minimum quality score required for vector search results")
    hybrid_quality_threshold: float = Field(0.5, description="Minimum quality score required for hybrid search results")
    text_quality_threshold: float = Field(0.4, description="Minimum quality score required for text-only search results")
    
    # Minimum result counts to consider a search successful
    results_count_threshold: int = Field(3, description="Minimum number of results required to consider search successful")
    
    # Result merging configuration
    enable_result_merging: bool = Field(False, description="Whether to merge results from different search strategies")
    vector_weight: float = Field(1.0, description="Weight for vector search results during merging")
    text_weight: float = Field(0.7, description="Weight for text search results during merging")
    hybrid_text_weight: float = Field(0.8, description="Weight for text component of hybrid search during merging")
    hybrid_vector_weight: float = Field(1.0, description="Weight for vector component of hybrid search during merging")
    
    def copy(self) -> 'FallbackConfig':
        """Create a copy of the configuration."""
        return FallbackConfig(**self.model_dump())


def apply_score_threshold(results: List[Dict[str, Any]], threshold: float) -> List[Dict[str, Any]]:
    """
    Filter search results by score threshold.
    
    Args:
        results: List of search results
        threshold: Minimum score threshold to keep
        
    Returns:
        Filtered list of search results
    """
    return [r for r in results if r.get("score", 0) >= threshold]


def verify_vector_search_quality(
    results: List[Dict[str, Any]],
    min_quality: float = 0.6,
    min_results: int = 3
) -> Dict[str, Any]:
    """
    Verify that vector search results meet quality standards.
    
    Args:
        results: List of search results
        min_quality: Minimum average quality score required
        min_results: Minimum number of results required
        
    Returns:
        Dictionary with quality information
    """
    # Check if we have enough results
    result_count = len(results)
    
    # Calculate average quality score for non-empty results
    if result_count > 0:
        avg_score = sum(r.get("score", 0) for r in results) / result_count
        max_score = max((r.get("score", 0) for r in results), default=0)
    else:
        avg_score = 0.0
        max_score = 0.0
    
    # Determine if results are sufficient
    sufficient_quality = (
        avg_score >= min_quality and
        result_count >= min_results
    )
    
    # Alternative condition: fewer results but very high quality
    if not sufficient_quality and result_count > 0 and max_score > min_quality + 0.2:
        sufficient_quality = True
        
    return {
        "sufficient_quality": sufficient_quality,
        "quality_score": avg_score,
        "max_score": max_score,
        "result_count": result_count,
        "min_quality_required": min_quality,
        "min_results_required": min_results
    }


def normalize_search_results(results_by_source: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Normalize results from different search sources to have consistent format.
    
    Args:
        results_by_source: Dictionary mapping source names to result lists
        
    Returns:
        Dictionary of normalized results by source
    """
    normalized = {}
    
    for source, results in results_by_source.items():
        # Deep copy to avoid modifying original results
        source_results = copy.deepcopy(results)
        
        # Add source to each result
        for result in source_results:
            result["source"] = source
            
            # Ensure each result has a score
            if "score" not in result:
                result["score"] = 0.0
                
            # Initialize sources array for merging
            result["sources"] = [source]
            
        normalized[source] = source_results
        
    return normalized


def merge_search_results(
    results_by_source: Dict[str, List[Dict[str, Any]]],
    weights: Dict[str, float] = None
) -> List[Dict[str, Any]]:
    """
    Merge results from multiple search sources, handling duplicates.
    
    Args:
        results_by_source: Dictionary mapping source names to result lists
        weights: Dictionary mapping source names to relative weights
        
    Returns:
        Merged list of unique results with adjusted scores
    """
    if weights is None:
        weights = {
            "vector": 1.0,
            "hybrid": 0.9,
            "text": 0.7
        }
    
    # Create dictionary to track merged results by ID
    merged_dict = {}
    
    # Process each source
    for source, results in results_by_source.items():
        source_weight = weights.get(source, 1.0)
        
        for result in results:
            result_id = result.get("id")
            if not result_id:
                continue
                
            if result_id in merged_dict:
                # Result already exists, merge information
                existing = merged_dict[result_id]
                
                # Update score (higher score wins)
                weighted_score = result["score"] * source_weight
                if weighted_score > existing["score"]:
                    existing["score"] = weighted_score
                
                # Track that this result came from multiple sources
                existing["sources"].append(source)
                
                # Add any additional fields that might be in this result
                for key, value in result.items():
                    if key not in existing and key not in ["score", "sources"]:
                        existing[key] = value
            else:
                # New result, apply source weighting to score
                result_copy = copy.deepcopy(result)
                result_copy["score"] = result["score"] * source_weight
                merged_dict[result_id] = result_copy
    
    # Convert back to list and boost scores for results from multiple sources
    merged_list = list(merged_dict.values())
    
    # Boost scores for results from multiple sources
    for result in merged_list:
        if len(result["sources"]) > 1:
            # Boost score by 10% for each additional source
            result["score"] = min(1.0, result["score"] * (1.0 + 0.1 * (len(result["sources"]) - 1)))
    
    # Sort by score (highest first)
    merged_list.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    return merged_list


def apply_fallback_strategy(
    provider,
    model_class: Type[T],
    query_text: str,
    query_vector: Optional[List[float]] = None,
    limit: int = 10,
    filter_criteria: Optional[Dict[str, Any]] = None,
    config: Optional[FallbackConfig] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Apply search fallback strategy based on configuration and result quality.
    
    Args:
        provider: Storage provider instance
        model_class: Model class for the search
        query_text: Text query
        query_vector: Optional vector query
        limit: Maximum number of results
        filter_criteria: Optional filtering criteria
        config: Fallback configuration
        
    Returns:
        Tuple of (results, fallback_info)
    """
    start_time = time.time()
    
    # Use default config if none provided
    if config is None:
        config = FallbackConfig()
    
    # Initialize fallback info
    fallback_info = {
        "strategy": None,
        "reason": None,
        "execution_time_ms": 0
    }
    
    # Get provider type for metrics
    provider_type = getattr(provider, "db_type", "unknown")
    
    # Skip vector search if no query vector provided
    if query_vector is None:
        try:
            # Directly use hybrid search with text only
            text_results = provider.hybrid_search(
                model_class,
                query_text=query_text,
                query_vector=None,
                limit=limit,
                filter_criteria=filter_criteria
            )
            
            fallback_info["strategy"] = "text_only"
            fallback_info["reason"] = "no_query_vector"
            
            # Record metrics
            SEARCH_FALLBACKS.labels(
                strategy="text_only",
                reason="no_query_vector",
                provider_type=provider_type
            ).inc()
            
            execution_time = time.time() - start_time
            fallback_info["execution_time_ms"] = int(execution_time * 1000)
            
            SEARCH_FALLBACK_LATENCY.labels(
                strategy="text_only",
                provider_type=provider_type
            ).observe(execution_time)
            
            return text_results, fallback_info
            
        except Exception as e:
            fallback_info["strategy"] = "error"
            fallback_info["reason"] = "text_search_error"
            fallback_info["error"] = str(e)
            
            # Log error and return empty results
            logger.error(
                "Text search error during fallback",
                error=str(e),
                provider=provider_type
            )
            
            # Record metrics
            SEARCH_FALLBACKS.labels(
                strategy="error",
                reason="text_search_error",
                provider_type=provider_type
            ).inc()
            
            return [], fallback_info
    
    # Try vector search first
    vector_results = []
    try:
        vector_results = provider.vector_search(
            model_class,
            query_vector=query_vector,
            limit=limit,
            filter_criteria=filter_criteria
        )
        
        # Verify vector search quality
        quality_info = verify_vector_search_quality(
            vector_results,
            min_quality=config.vector_quality_threshold,
            min_results=config.results_count_threshold
        )
        
        # Record quality metrics
        SEARCH_QUALITY_SCORES.labels(
            search_type="vector",
            provider_type=provider_type
        ).observe(quality_info["quality_score"])
        
        # If vector results are sufficient, we might still want to merge with hybrid search
        if quality_info["sufficient_quality"]:
            if not config.enable_result_merging:
                # If merging is disabled, just return vector results
                fallback_info["strategy"] = "vector_only"
                fallback_info["reason"] = "sufficient_quality_and_results"
                fallback_info["quality_info"] = quality_info
                
                execution_time = time.time() - start_time
                fallback_info["execution_time_ms"] = int(execution_time * 1000)
                
                return vector_results, fallback_info
                
            # If merging is enabled, we need to run hybrid search too
            try:
                hybrid_results = provider.hybrid_search(
                    model_class,
                    query_text=query_text,
                    query_vector=query_vector,
                    limit=limit,
                    filter_criteria=filter_criteria
                )
                
                # Normalize and merge results
                normalized = normalize_search_results({
                    "vector": vector_results,
                    "hybrid": hybrid_results
                })
                
                merged_results = merge_search_results(
                    normalized,
                    weights={
                        "vector": config.vector_weight,
                        "hybrid": config.hybrid_vector_weight
                    }
                )
                
                fallback_info["strategy"] = "merged_results"
                fallback_info["reason"] = "vector_and_hybrid_combined"
                fallback_info["quality_info"] = quality_info
                
                # Track metrics
                SEARCH_FALLBACKS.labels(
                    strategy="merged_results",
                    reason="vector_and_hybrid_combined",
                    provider_type=provider_type
                ).inc()
                
                execution_time = time.time() - start_time
                fallback_info["execution_time_ms"] = int(execution_time * 1000)
                
                SEARCH_FALLBACK_LATENCY.labels(
                    strategy="merged_results",
                    provider_type=provider_type
                ).observe(execution_time)
                
                return merged_results, fallback_info
            except Exception as e:
                # If hybrid search fails, just use vector results
                logger.warning(
                    "Hybrid search error during result merging, using vector results only",
                    error=str(e),
                    provider=provider_type
                )
                
                fallback_info["strategy"] = "vector_only"
                fallback_info["reason"] = "hybrid_search_error_during_merging"
                fallback_info["quality_info"] = quality_info
                fallback_info["hybrid_search_error"] = str(e)
                
                execution_time = time.time() - start_time
                fallback_info["execution_time_ms"] = int(execution_time * 1000)
                
                return vector_results, fallback_info
            
    except Exception as e:
        # Log error and continue to fallback
        logger.warning(
            "Vector search error, falling back to hybrid search",
            error=str(e),
            provider=provider_type
        )
        
        fallback_info["vector_search_error"] = str(e)
        
        # Record metrics
        SEARCH_FALLBACKS.labels(
            strategy="hybrid_fallback",
            reason="vector_search_error",
            provider_type=provider_type
        ).inc()
        
        # Continue to hybrid search fallback
    
    # Try hybrid search as fallback
    hybrid_results = []
    try:
        hybrid_results = provider.hybrid_search(
            model_class,
            query_text=query_text,
            query_vector=query_vector,
            limit=limit,
            filter_criteria=filter_criteria
        )
        
        # Verify hybrid search quality
        quality_info = verify_vector_search_quality(
            hybrid_results,
            min_quality=config.hybrid_quality_threshold,
            min_results=config.results_count_threshold
        )
        
        # Record quality metrics
        SEARCH_QUALITY_SCORES.labels(
            search_type="hybrid",
            provider_type=provider_type
        ).observe(quality_info["quality_score"])
        
        # If we have both vector and hybrid results and merging is enabled
        if config.enable_result_merging and vector_results and hybrid_results:
            # Normalize and merge results
            normalized = normalize_search_results({
                "vector": vector_results,
                "hybrid": hybrid_results
            })
            
            merged_results = merge_search_results(
                normalized,
                weights={
                    "vector": config.vector_weight,
                    "hybrid": config.hybrid_vector_weight
                }
            )
            
            fallback_info["strategy"] = "merged_results"
            fallback_info["reason"] = "vector_and_hybrid_combined"
            fallback_info["quality_info"] = quality_info
            
            # Track metrics
            SEARCH_FALLBACKS.labels(
                strategy="merged_results",
                reason="vector_and_hybrid_combined",
                provider_type=provider_type
            ).inc()
            
            execution_time = time.time() - start_time
            fallback_info["execution_time_ms"] = int(execution_time * 1000)
            
            SEARCH_FALLBACK_LATENCY.labels(
                strategy="merged_results",
                provider_type=provider_type
            ).observe(execution_time)
            
            return merged_results, fallback_info
            
        # Otherwise, use hybrid results as fallback
        fallback_info["strategy"] = "hybrid_fallback"
        fallback_info["reason"] = "low_vector_quality" if vector_results else "vector_search_error"
        fallback_info["quality_info"] = quality_info
        
        # Track metrics
        SEARCH_FALLBACKS.labels(
            strategy="hybrid_fallback",
            reason=fallback_info["reason"],
            provider_type=provider_type
        ).inc()
        
        execution_time = time.time() - start_time
        fallback_info["execution_time_ms"] = int(execution_time * 1000)
        
        SEARCH_FALLBACK_LATENCY.labels(
            strategy="hybrid_fallback",
            provider_type=provider_type
        ).observe(execution_time)
        
        return hybrid_results, fallback_info
        
    except Exception as e:
        # Both vector and hybrid search failed
        fallback_info["hybrid_search_error"] = str(e)
        
        # Log error
        logger.error(
            "Hybrid search error during fallback",
            error=str(e),
            provider=provider_type
        )
        
        # Try text-only search as last resort
        if hasattr(provider, "text_search"):
            try:
                text_results = provider.text_search(
                    model_class,
                    query_text=query_text,
                    limit=limit,
                    filter_criteria=filter_criteria
                )
                
                fallback_info["strategy"] = "text_fallback"
                fallback_info["reason"] = "hybrid_search_error"
                fallback_info["error"] = str(e)
                
                # Record metrics
                SEARCH_FALLBACKS.labels(
                    strategy="text_fallback",
                    reason="hybrid_search_error",
                    provider_type=provider_type
                ).inc()
                
                execution_time = time.time() - start_time
                fallback_info["execution_time_ms"] = int(execution_time * 1000)
                
                SEARCH_FALLBACK_LATENCY.labels(
                    strategy="text_fallback",
                    provider_type=provider_type
                ).observe(execution_time)
                
                return text_results, fallback_info
                
            except Exception as text_error:
                # All search methods failed
                fallback_info["strategy"] = "error"
                fallback_info["reason"] = "all_search_methods_failed"
                fallback_info["error"] = str(e)
                fallback_info["text_search_error"] = str(text_error)
                
                # Log error
                logger.error(
                    "All search methods failed",
                    vector_error=fallback_info.get("vector_search_error", "Unknown"),
                    hybrid_error=str(e),
                    text_error=str(text_error),
                    provider=provider_type
                )
                
                # Record metrics
                SEARCH_FALLBACKS.labels(
                    strategy="error",
                    reason="all_search_methods_failed",
                    provider_type=provider_type
                ).inc()
                
                return [], fallback_info
        else:
            # No text search method available
            fallback_info["strategy"] = "error"
            fallback_info["reason"] = "no_text_fallback_available"
            fallback_info["error"] = str(e)
            
            # Log error
            logger.error(
                "All search methods failed and no text fallback available",
                vector_error=fallback_info.get("vector_search_error", "Unknown"),
                hybrid_error=str(e),
                provider=provider_type
            )
            
            # Record metrics
            SEARCH_FALLBACKS.labels(
                strategy="error",
                reason="no_text_fallback_available",
                provider_type=provider_type
            ).inc()
            
            return [], fallback_info