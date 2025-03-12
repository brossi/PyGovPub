"""
LanceDB vector database provider for PyGovPub.

This module implements a storage provider for LanceDB, a high-performance
embedded vector database. It provides vector search capabilities and
document storage with a simple, embedded deployment model.
"""

import os
import time
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar

import structlog
import lancedb
import pyarrow as pa
import numpy as np
from prometheus_client import Counter, Histogram, Gauge

logger = structlog.get_logger()

# Metrics
LANCEDB_OPERATIONS = Counter(
    "lancedb_operations_total",
    "Total LanceDB operations",
    ["operation", "status", "table"]
)
LANCEDB_OPERATION_DURATION = Histogram(
    "lancedb_operation_duration_seconds",
    "LanceDB operation duration in seconds",
    ["operation", "table"]
)
LANCEDB_SCHEMA_VERSION = Gauge(
    "lancedb_schema_version",
    "LanceDB schema version for a table",
    ["table", "version"]
)

T = TypeVar("T")

class LanceDBProvider:
    """LanceDB storage provider implementation"""

    def __init__(self,
                uri: str = None,
                create_vector_index: bool = True,
                vector_dim: int = 384,
                schema_registry=None,
                **config):
        """
        Initialize LanceDB provider.
        
        Args:
            uri: Path to LanceDB database (directory)
            create_vector_index: Whether to create vector index on table creation
            vector_dim: Dimension of vector embeddings (default: 384 for all-MiniLM-L6-v2)
            schema_registry: Optional schema registry instance for schema management
            **config: Additional configuration options
        """
        self.vector_dim = vector_dim
        self.create_vector_index = create_vector_index
        self.schema_registry = schema_registry
        self.schema_adapter = None

        # Use temporary directory if no URI provided
        if not uri:
            db_dir = config.get("db_dir", os.path.expanduser("~/.pygovpub/lancedb"))
            os.makedirs(db_dir, exist_ok=True)
            timestamp = int(time.time())
            db_id = str(uuid.uuid4())[:8]
            uri = f"{db_dir}/pygovpub_db_{timestamp}_{db_id}"
            logger.info(f"Creating LanceDB at {uri}")

        self.uri = uri
        self.db = lancedb.connect(uri)
        self.config = config
        self.table_info = {}  # Cache table metadata

        # Initialize schema adapter if registry provided
        if self.schema_registry:
            try:
                from pygovpub.storage.providers.lancedb_schema import LanceDBSchemaAdapter
                self.schema_adapter = LanceDBSchemaAdapter(self, self.schema_registry)
                logger.info("LanceDB schema adapter initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize LanceDB schema adapter: {str(e)}")

        logger.info("LanceDB provider initialized", uri=uri)

    def _model_to_dict(self, model_obj: Any) -> Dict[str, Any]:
        """
        Convert model object to dictionary for LanceDB storage.
        
        Args:
            model_obj: Model object (Pydantic, SQLAlchemy, or dict)
            
        Returns:
            Dictionary representation of the model
        """
        if hasattr(model_obj, "model_dump"):
            # Use Pydantic's model_dump() for Pydantic v2 compatibility
            return model_obj.model_dump()
        elif hasattr(model_obj, "__dict__"):
            # Handle SQLAlchemy models or other objects
            return {
                key: value for key, value in model_obj.__dict__.items()
                if not key.startswith("_")
            }
        else:
            # Already a dict or something else
            return model_obj

    def _get_or_create_table(self, table_name: str, schema: Optional[pa.Schema] = None, schema_version: Optional[str] = None):
        """
        Get or create a LanceDB table with appropriate schema.
        
        Args:
            table_name: Table name
            schema: Optional Arrow schema for new table
            schema_version: Optional schema version to apply from registry
            
        Returns:
            LanceDB table
        """
        start_time = time.time()

        try:
            # Check if table exists
            if table_name in self.db.table_names():
                table = self.db.open_table(table_name)
                logger.debug(f"Opened existing table {table_name}")
                
                # Apply schema version if provided and adapter available
                if schema_version and self.schema_adapter:
                    self.schema_adapter.apply_schema_version(table_name, schema_version)
                    # Update metrics
                    LANCEDB_SCHEMA_VERSION.labels(
                        table=table_name,
                        version=schema_version
                    ).set(1)
            else:
                # If schema version is provided and adapter available, use that schema
                if schema_version and self.schema_adapter:
                    # Get schema from registry
                    registry_schema = self.schema_registry.get_schema_version(schema_version)
                    if registry_schema:
                        schema = self.schema_adapter._convert_schema_version_to_arrow(registry_schema)
                        logger.info(f"Using schema version {schema_version} for table {table_name}")
                        # Update metrics
                        LANCEDB_SCHEMA_VERSION.labels(
                            table=table_name,
                            version=schema_version
                        ).set(1)
                
                # Use default schema if none provided
                if schema is None:
                    # Create a minimal initial schema if none provided
                    schema = pa.schema([
                        ("id", pa.string()),
                        ("embedding", pa.list_(pa.float32(), self.vector_dim)),
                        ("metadata", pa.string()),  # JSON-serialized metadata
                        ("content", pa.string()),   # Document content
                        ("created_at", pa.timestamp("us")),
                        ("updated_at", pa.timestamp("us")),
                    ])

                # Create empty table with schema
                empty_data = pa.Table.from_pydict(
                    {field.name: [] for field in schema}, schema=schema
                )

                # Create table
                table = self.db.create_table(
                    table_name,
                    data=empty_data,
                    mode="overwrite" if self.config.get("overwrite_tables", False) else "error"
                )

                # Create vector index if specified
                if self.create_vector_index:
                    table.create_index(
                        ["embedding"],
                        index_type="IVF_PQ",
                        metric_type="L2",
                        replace=True
                    )

                logger.info(f"Created new table {table_name} with vector index")

            # Cache table info
            self.table_info[table_name] = {
                "has_vector_index": self._check_table_has_vector_index(table),
                "schema": table.schema,
                "version": schema_version
            }

            LANCEDB_OPERATION_DURATION.labels(
                operation="get_or_create_table",
                table=table_name
            ).observe(time.time() - start_time)

            return table

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="get_or_create_table",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error getting/creating table {table_name}", error=str(e))
            raise

    def _check_table_has_vector_index(self, table) -> bool:
        """
        Check if table has a vector index.
        
        Args:
            table: LanceDB table
            
        Returns:
            True if table has vector index, False otherwise
        """
        try:
            # Check for index metadata
            indices = table.describe_indices()
            return len(indices) > 0 and any("embedding" in idx.get("column_names", []) for idx in indices)
        except Exception as e:
            logger.warning(f"Could not check vector index: {str(e)}")
            return False

    def _convert_model_to_arrow(self, model_class: Type[T], data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert model data to arrow-compatible format for LanceDB.
        
        Args:
            model_class: Model class
            data: Model data
            
        Returns:
            Arrow-compatible dictionary
        """
        arrow_data = {}

        # Ensure we have basic required fields
        arrow_data["id"] = data.get("id", str(uuid.uuid4()))

        # Handle embedding vector
        if "embedding" in data:
            embedding = data["embedding"]
            # Ensure embedding is a list with correct dimensions
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            elif isinstance(embedding, str):
                # Handle case where embedding might be JSON string
                try:
                    embedding = json.loads(embedding)
                except:
                    logger.warning(f"Could not parse embedding from string: {embedding[:20]}...")
                    # Use zero vector as fallback
                    embedding = [0.0] * self.vector_dim

            # Validate vector dimension
            if len(embedding) != self.vector_dim:
                logger.warning(
                    f"Embedding dimension mismatch: got {len(embedding)}, expected {self.vector_dim}. Padding/truncating."
                )
                if len(embedding) < self.vector_dim:
                    # Pad with zeros
                    embedding = embedding + [0.0] * (self.vector_dim - len(embedding))
                else:
                    # Truncate
                    embedding = embedding[:self.vector_dim]

            arrow_data["embedding"] = embedding
        else:
            # Default empty embedding if none provided
            arrow_data["embedding"] = [0.0] * self.vector_dim

        # Handle metadata - serialize to JSON string
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            arrow_data["metadata"] = json.dumps(metadata)
        else:
            # Handle case where metadata might be an object
            arrow_data["metadata"] = json.dumps(self._model_to_dict(metadata))

        # Handle content
        arrow_data["content"] = data.get("content", "")

        # Handle timestamps
        current_time = pa.scalar(time.time_ns() // 1000).cast(pa.timestamp("us"))
        arrow_data["created_at"] = data.get("created_at", current_time)
        arrow_data["updated_at"] = data.get("updated_at", current_time)

        # Add all other fields as-is
        for key, value in data.items():
            if key not in arrow_data and key not in ["metadata", "embedding", "content"]:
                arrow_data[key] = value

        return arrow_data

    def create(self, model_class: Type[T], data: Dict[str, Any]) -> str:
        """
        Create a new record in LanceDB.
        
        Args:
            model_class: Model class
            data: Model data
            
        Returns:
            ID of created record
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        # Process data for LanceDB
        processed_data = self._convert_model_to_arrow(model_class, data)

        try:
            # Get or create table
            table = self._get_or_create_table(table_name)

            # Add record to table
            table.add([processed_data])

            LANCEDB_OPERATIONS.labels(
                operation="create",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="create",
                table=table_name
            ).observe(time.time() - start_time)

            logger.debug(f"Created record in {table_name}", id=processed_data["id"])
            return processed_data["id"]

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="create",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error creating record in {table_name}", error=str(e))
            raise

    def get(self, model_class: Type[T], id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a record by ID.
        
        Args:
            model_class: Model class
            id: Record ID
            
        Returns:
            Record data or None if not found
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Get table
            table = self._get_or_create_table(table_name)

            # Query record by ID
            result = table.search().where(f"id = '{id}'").limit(1).to_pandas()

            if len(result) == 0:
                logger.debug(f"Record {id} not found in {table_name}")
                return None

            # Convert from pandas row to dict
            record = result.iloc[0].to_dict()

            # Parse metadata from JSON
            if "metadata" in record and isinstance(record["metadata"], str):
                try:
                    record["metadata"] = json.loads(record["metadata"])
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse metadata JSON for record {id}")

            LANCEDB_OPERATIONS.labels(
                operation="get",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="get",
                table=table_name
            ).observe(time.time() - start_time)

            return record

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="get",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error retrieving record {id} from {table_name}", error=str(e))
            raise

    def vector_search(self,
                    model_class: Type[T],
                    query_vector: List[float],
                    limit: int = 10,
                    filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search.
        
        Args:
            model_class: Model class
            query_vector: Query vector
            limit: Maximum number of results
            filter_criteria: Optional filtering criteria
            
        Returns:
            List of matching records
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Get table
            table = self._get_or_create_table(table_name)

            # Start query
            query = table.search(query_vector, vector_column_name="embedding")

            # Apply filters if provided
            if filter_criteria:
                filter_expr = " AND ".join([
                    f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                    for key, value in filter_criteria.items()
                ])
                query = query.where(filter_expr)

            # Execute search
            result = query.limit(limit).to_pandas()

            # Process results
            records = []
            for _, row in result.iterrows():
                record = row.to_dict()

                # Parse metadata from JSON
                if "metadata" in record and isinstance(record["metadata"], str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse metadata JSON")

                records.append(record)

            LANCEDB_OPERATIONS.labels(
                operation="vector_search",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="vector_search",
                table=table_name
            ).observe(time.time() - start_time)

            return records

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="vector_search",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error performing vector search in {table_name}", error=str(e))
            raise

    def hybrid_search(self,
                    model_class: Type[T],
                    query_text: str,
                    query_vector: List[float] = None,
                    limit: int = 10,
                    filter_criteria: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Perform hybrid search (full-text + vector) if text is provided.
        Will automatically generate embeddings if only text is provided.
        
        Args:
            model_class: Model class
            query_text: Text query
            query_vector: Optional vector query (for hybrid search)
            limit: Maximum number of results
            filter_criteria: Optional filtering criteria
            
        Returns:
            List of matching records
        """
        start_time = time.time()

        # Get table name from model class
        if hasattr(model_class, "__tablename__"):
            table_name = model_class.__tablename__
        else:
            table_name = model_class.__name__.lower()

        try:
            # Get table
            table = self._get_or_create_table(table_name)

            # Start hybrid query
            if query_vector is not None:
                # True hybrid search with vector and text components
                query = table.search(query_vector, query_text=query_text)
            else:
                # Full-text search only
                query = table.search(query_text=query_text)

            # Apply filters if provided
            if filter_criteria:
                filter_expr = " AND ".join([
                    f"{key} = '{value}'" if isinstance(value, str) else f"{key} = {value}"
                    for key, value in filter_criteria.items()
                ])
                query = query.where(filter_expr)

            # Execute search
            result = query.limit(limit).to_pandas()

            # Process results
            records = []
            for _, row in result.iterrows():
                record = row.to_dict()

                # Parse metadata from JSON
                if "metadata" in record and isinstance(record["metadata"], str):
                    try:
                        record["metadata"] = json.loads(record["metadata"])
                    except json.JSONDecodeError:
                        logger.warning(f"Could not parse metadata JSON")

                records.append(record)

            LANCEDB_OPERATIONS.labels(
                operation="hybrid_search",
                status="success",
                table=table_name
            ).inc()

            LANCEDB_OPERATION_DURATION.labels(
                operation="hybrid_search",
                table=table_name
            ).observe(time.time() - start_time)

            return records

        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="hybrid_search",
                status="error",
                table=table_name
            ).inc()

            logger.error(f"Error performing hybrid search in {table_name}", error=str(e))
            raise
            
    def apply_schema_version(self, table_name: str, version: str) -> bool:
        """
        Apply a schema version from the registry to a table.
        
        Args:
            table_name: Name of the table
            version: Schema version to apply
            
        Returns:
            True if successful, False otherwise
        """
        if not self.schema_adapter:
            logger.error("Schema adapter not initialized, cannot apply schema version")
            return False
        
        try:
            start_time = time.time()
            
            # Apply schema version
            result = self.schema_adapter.apply_schema_version(table_name, version)
            
            if result:
                # Update metrics
                LANCEDB_SCHEMA_VERSION.labels(
                    table=table_name,
                    version=version
                ).set(1)
                
                # Update table info cache
                if table_name in self.table_info:
                    self.table_info[table_name]["version"] = version
                
                logger.info(f"Applied schema version {version} to table {table_name}")
            
            LANCEDB_OPERATION_DURATION.labels(
                operation="apply_schema_version",
                table=table_name
            ).observe(time.time() - start_time)
            
            LANCEDB_OPERATIONS.labels(
                operation="apply_schema_version",
                status="success" if result else "failure",
                table=table_name
            ).inc()
            
            return result
            
        except Exception as e:
            LANCEDB_OPERATIONS.labels(
                operation="apply_schema_version",
                status="error",
                table=table_name
            ).inc()
            
            logger.error(f"Error applying schema version {version} to table {table_name}", error=str(e))
            return False