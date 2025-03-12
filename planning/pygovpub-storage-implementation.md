# PyGovPub Storage Architecture Implementation Plan

## Executive Summary

This document outlines a streamlined implementation plan for expanding PyGovPub's storage architecture to support multiple database backends (PostgreSQL with pgVector, SQLite) while enabling cloud storage solutions (Supabase, Pinecone) as optional, on-demand features. The plan focuses on:

1. Establishing a minimal but effective abstraction layer
2. Making cloud provider dependencies conditional and optional
3. Implementing feature detection to adapt to available capabilities
4. Ensuring backward compatibility with the existing codebase

## 1. System Architecture

### 1.1 Core Components

```
┌─────────────────┐       ┌───────────────┐
│  External APIs  │◄─────►│               │
│ (GovInfo, etc.) │       │               │
└─────────────────┘       │   PyGovPub    │◄─────┐
                          │   Application  │      │
┌─────────────────┐       │               │      │
│    Billy LLM    │◄─────►│               │      │
└─────────────────┘       └───────┬───────┘      │
                                  │              │
                                  ▼              │
                          ┌───────────────┐      │
                          │    Storage    │      │
                          │   Interface   │      │
                          └───────┬───────┘      │
                                  │              │
           ┌──────────────────────┼──────────────┘
           │                      │              
           ▼                      ▼              
┌────────────────┐      ┌─────────────────┐    ┌─────────────────────┐
│  PostgreSQL +  │      │     SQLite      │    │  Optional Providers │
│   pgVector     │      │                 │    │ (Supabase/Pinecone) │
│                │      │                 │    │                     │
└────────────────┘      └─────────────────┘    └─────────────────────┘
```

### 1.2 Key Design Principles

1. **Minimal Abstraction**: Create only the necessary abstraction to support multiple databases
2. **Optional Dependencies**: Make cloud provider libraries optional and load them only when configured
3. **Feature Detection**: Identify database capabilities at runtime to enable appropriate functionality
4. **Progressive Enhancement**: Add features incrementally as database support allows

## 2. Dependencies Management

### 2.1 Core Requirements

Based on the existing requirements.txt file, we need to add the following dependencies:

```
# Core SQLAlchemy (required since SQLModel is now using an older version)
sqlalchemy>=2.0.0
alembic>=1.12.0  # Database migrations

# PostgreSQL Vector Extensions
pgvector>=0.2.4  # Python bindings for pgVector extension

# Embedding Generation
sentence-transformers>=2.2.2  # Optimized embedding models
torch>=2.1.0  # Required by sentence-transformers (CPU-only is sufficient)

# Async Support
aiosqlite>=0.19.0  # Async SQLite support
```

### 2.2 Optional Cloud Provider Dependencies

We'll make these dependencies optional by using extras_require in setup.py:

```python
# In setup.py
setup(
    name="pygovpub",
    # ...other parameters...
    install_requires=[
        "fastapi>=0.95.0",
        "sqlalchemy>=2.0.0",
        # other core dependencies
    ],
    extras_require={
        "pinecone": ["pinecone-client>=2.2.4"],
        "supabase": ["supabase>=2.0.3"],
        "cloud": ["pinecone-client>=2.2.4", "supabase>=2.0.3"],
        "llm": ["transformers>=4.36.0", "accelerate>=0.25.0"],
    }
)
```

## 3. Implementation Plan

### 3.1 Storage Interface (Priority: High)

Create a minimal storage interface that handles the core operations while abstracting the underlying database implementation.

#### Implementation Approach:

1. **Use SQLAlchemy as the foundation**
   - Leverage SQLAlchemy's existing abstractions for relational databases
   - Keep the interface focused on essential operations

2. **Implement feature detection**
   - Detect database capabilities at runtime
   - Enable/disable features based on available capabilities

```python
# Streamlined implementation using SQLAlchemy
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
import importlib.util

class StorageInterface:
    def __init__(self, connection_string, **config):
        self.connection_string = connection_string
        self.config = config
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)
        self.features = self._detect_features()
        
    def _detect_features(self):
        """Detect basic database capabilities"""
        features = {'basic_storage': True}
        
        # PostgreSQL with pgVector detection
        if 'postgresql' in self.connection_string:
            try:
                with self.engine.connect() as conn:
                    result = conn.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')")
                    if result.scalar():
                        features['vector_operations'] = True
            except Exception:
                # Handle case where extension check fails
                pass
        
        # SQLite detection
        elif 'sqlite' in self.connection_string:
            features['local_storage'] = True
            
        # Pinecone detection - only if the library is available
        elif 'pinecone' in self.connection_string and self._is_package_available('pinecone'):
            features['cloud_storage'] = True
            features['vector_operations'] = True
            
        # Supabase detection - only if the library is available
        elif 'supabase' in self.connection_string and self._is_package_available('supabase'):
            features['cloud_storage'] = True
            
        return features
    
    def _is_package_available(self, package_name):
        """Check if a Python package is installed and available"""
        return importlib.util.find_spec(package_name) is not None
        
    def supports(self, feature):
        """Check if a specific feature is supported"""
        return self.features.get(feature, False)
        
    # Core CRUD operations that work across all backends
    def create(self, model_class, data):
        """Create a new record"""
        session = self.Session()
        try:
            instance = model_class(**data)
            session.add(instance)
            session.commit()
            return instance.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()
```

### 3.2 Provider-Specific Modules (Priority: High)

Create isolated modules for each cloud provider, with dynamic imports to ensure they're only loaded when explicitly used.

```python
# pygovpub/storage/providers/pinecone_provider.py
def is_available():
    """Check if Pinecone library is installed"""
    try:
        import pinecone
        return True
    except ImportError:
        return False

def initialize(api_key, environment, index_name):
    """Initialize Pinecone connection if available"""
    if not is_available():
        raise ImportError(
            "Pinecone library not installed. Install with: pip install pygovpub[pinecone]"
        )
    
    import pinecone
    pinecone.init(api_key=api_key, environment=environment)
    
    # Create index if it doesn't exist
    if index_name not in pinecone.list_indexes():
        pinecone.create_index(
            name=index_name,
            dimension=768,
            metric="cosine"
        )
        
    return pinecone.Index(index_name)
```

```python
# pygovpub/storage/providers/supabase_provider.py
def is_available():
    """Check if Supabase library is installed"""
    try:
        import supabase
        return True
    except ImportError:
        return False

def initialize(url, key):
    """Initialize Supabase connection if available"""
    if not is_available():
        raise ImportError(
            "Supabase library not installed. Install with: pip install pygovpub[supabase]"
        )
    
    from supabase import create_client
    return create_client(url, key)
```

### 3.3 Database-Specific Implementations (Priority: High)

Implement the database-specific operations for each supported backend, focusing on the essential functionality first.

#### Implementation Approach:

1. **Start with PostgreSQL implementation**
   - PostgreSQL is the production database, so implement it first
   - Add pgVector support using the pgvector-python package

2. **Add SQLite implementation**
   - Reuse core SQLAlchemy functionality
   - Handle feature differences with clear fallbacks

```python
# PostgreSQL with pgVector implementation
from sqlalchemy import Column, Integer, String, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class Document(Base):
    __tablename__ = 'documents'
    
    id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)
    embedding = Column(Vector(768), nullable=True)  # Only used if pgvector is available

# Vector search implementation for PostgreSQL
def vector_search_postgres(storage, query_embedding, limit=10):
    """PostgreSQL-specific vector search implementation"""
    if not storage.supports('vector_operations'):
        raise NotImplementedError("Vector operations not supported")
        
    from sqlalchemy import select
    from pgvector.sqlalchemy import cosine_distance
    
    session = storage.Session()
    try:
        stmt = select(Document).order_by(
            cosine_distance(Document.embedding, query_embedding)
        ).limit(limit)
        
        return session.execute(stmt).scalars().all()
    finally:
        session.close()

# SQLite implementation - no vector support but all basic operations
def keyword_search_sqlite(storage, query_text, limit=10):
    """SQLite-specific keyword search implementation"""
    session = storage.Session()
    try:
        # Simplified keyword matching using LIKE operator
        stmt = select(Document).where(
            Document.content.like(f'%{query_text}%')
        ).limit(limit)
        
        return session.execute(stmt).scalars().all()
    finally:
        session.close()
```

### 3.4 Feature-Based Search Implementation (Priority: Medium)

Create a unified search interface that adapts based on the available database capabilities.

#### Implementation Approach:

1. **Implement a feature-aware search service**
   - Single entry point for all search operations
   - Dynamically select appropriate implementation based on available features

```python
# Search service with feature-based implementation selection
class SearchService:
    def __init__(self, storage):
        self.storage = storage
        
    def search(self, query, limit=10):
        """Universal search method that adapts to available features"""
        # Check if we have vector search capability
        if isinstance(query, list) and self.storage.supports('vector_operations'):
            # This is a vector query and we support vector operations
            if 'postgresql' in self.storage.connection_string:
                return vector_search_postgres(self.storage, query, limit)
            elif 'pinecone' in self.storage.connection_string:
                # Only import if we know we're using pinecone
                from pygovpub.storage.providers import pinecone_provider
                if pinecone_provider.is_available():
                    return vector_search_pinecone(self.storage, query, limit)
                else:
                    raise ImportError("Pinecone support required but not installed. Run: pip install pygovpub[pinecone]")
        
        # Fall back to text search
        if isinstance(query, str):
            if 'sqlite' in self.storage.connection_string:
                return keyword_search_sqlite(self.storage, query, limit)
            else:
                return keyword_search_standard(self.storage, query, limit)
        
        raise ValueError("Unsupported query type for the current database")

# API implementation that uses the search service
@app.get("/search/")
async def search_endpoint(query: str, vector: bool = False):
    search_service = SearchService(storage)
    
    if vector and storage.supports('vector_operations'):
        # Convert query to embedding vector
        embedding = get_embedding(query)
        results = search_service.search(embedding)
    else:
        # Use text-based search
        results = search_service.search(query)
        
    return results
```

### 3.5 LLM Integration (Priority: Medium)

Create a minimal integration with the "Billy" LLM for RAG functionality, using the optional dependencies approach.

#### Implementation Approach:

1. **Implement feature detection for LLM support**
   - Check if required libraries are installed
   - Provide clear guidance when dependencies are missing

```python
# pygovpub/llm/billy.py
def is_available():
    """Check if transformers library is installed for LLM support"""
    try:
        import transformers
        return True
    except ImportError:
        return False

class BillyRAG:
    def __init__(self, storage):
        self.storage = storage
        
        # Verify dependencies
        if not is_available():
            raise ImportError(
                "Transformers library not installed. Install with: pip install pygovpub[llm]"
            )
            
        # Import libraries only when necessary
        from sentence_transformers import SentenceTransformer
        import torch
        
        # Load embedding model
        self.embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        
        # LLM will be loaded on first use
        self.llm = None
    
    def _load_model(self):
        """Load the model on first use to avoid unnecessary overhead"""
        if self.llm is None:
            from transformers import pipeline
            self.llm = pipeline(
                "text-generation",
                model="path/to/billy/model",
                max_length=512,
                temperature=0.1
            )
        return self.llm
    
    def store_document(self, document):
        """Process and store a document with vector embedding if supported"""
        # Only import when needed
        from langchain.text_splitter import RecursiveCharacterTextSplitter
        
        # Split document into chunks
        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
        chunks = splitter.split_text(document["content"])
        
        # Store each chunk
        for i, chunk_text in enumerate(chunks):
            chunk_data = {
                "content": chunk_text,
                "metadata": {
                    "source": document.get("source", "unknown"),
                    "chunk_id": i,
                    "document_id": document.get("id", "unknown")
                }
            }
            
            # Add embedding if vector operations are supported
            if self.storage.supports('vector_operations'):
                embedding = self.embedding_model.encode(chunk_text)
                self.storage.create_with_embedding("documents", chunk_data, embedding)
            else:
                self.storage.create("documents", chunk_data)
    
    def query(self, question):
        """Answer a question using retrieved context"""
        # Get relevant context
        context = self._retrieve_context(question)
        
        # Format prompt with context
        prompt = f"Context: {context}\n\nQuestion: {question}\n\nAnswer:"
        
        # Generate answer
        llm = self._load_model()
        response = llm(prompt)[0]["generated_text"]
        
        return response.split("Answer:")[1].strip()
    
    def _retrieve_context(self, question):
        """Retrieve relevant context based on the question"""
        search_service = SearchService(self.storage)
        
        if self.storage.supports('vector_operations'):
            # Vector search
            question_embedding = self.embedding_model.encode(question)
            results = search_service.search(question_embedding)
        else:
            # Keyword search
            results = search_service.search(question)
            
        # Combine retrieved documents into context
        context = "\n\n".join([doc["content"] for doc in results])
        return context
```

### 3.6 Configuration Management (Priority: Medium)

Implement a configuration system that supports environment variables for API keys and connection details.

```python
# pygovpub/config.py
import os
from dotenv import load_dotenv

load_dotenv()

def get_storage_config():
    """Get storage configuration based on environment"""
    connection_string = os.getenv("DATABASE_URL", "sqlite:///./test.db")
    
    config = {}
    
    # Only add Pinecone config if connection string specifies pinecone
    if 'pinecone' in connection_string:
        config.update({
            'api_key': os.getenv("PINECONE_API_KEY"),
            'environment': os.getenv("PINECONE_ENVIRONMENT"),
            'index_name': os.getenv("PINECONE_INDEX", "pygovpub")
        })
    
    # Only add Supabase config if connection string specifies supabase
    if 'supabase' in connection_string:
        config.update({
            'url': os.getenv("SUPABASE_URL"),
            'key': os.getenv("SUPABASE_KEY")
        })
    
    return connection_string, config

# Factory function for storage interface
def create_storage_interface():
    """Create and configure a storage interface based on environment settings"""
    connection_string, config = get_storage_config()
    
    from pygovpub.storage.interface import StorageInterface
    return StorageInterface(connection_string, **config)
```

## 4. Implementation Phases

### Phase 1: Core Infrastructure (2 weeks)

1. Setup optional dependencies in package configuration
2. Create the StorageInterface with feature detection
3. Implement PostgreSQL integration with pgVector support
4. Add SQLite support for local development/testing
5. Develop database migration scripts for both backends

**Deliverables:**
- Working storage abstraction with feature detection
- PostgreSQL and SQLite support
- Core CRUD operations
- Database migration system
- Conditional dependency handling

### Phase 2: Provider-Specific Modules (1 week)

1. Create isolated modules for Pinecone
2. Create isolated modules for Supabase
3. Implement dynamic import mechanisms
4. Add clear error messages for missing dependencies
5. Create documentation for conditional features

**Deliverables:**
- Isolated provider modules
- Dynamic import handling
- User-friendly error messages

### Phase 3: Search Implementation (2 weeks)

1. Implement text search for all database backends
2. Add vector search for PostgreSQL with pgVector
3. Implement vector search for Pinecone (conditional)
4. Create a unified SearchService with feature-based implementation
5. Add unit and integration tests for search functionality

**Deliverables:**
- Working search across all database backends
- Vector search for PostgreSQL and Pinecone
- Conditional feature support

### Phase 4: LLM Integration (2 weeks)

1. Integrate Billy LLM with minimalist approach
2. Implement document processing and chunking
3. Create embedding generation pipeline
4. Build simple RAG query pipeline
5. Add performance optimization for production use

**Deliverables:**
- Working RAG system with Billy LLM
- Document chunking and embedding pipeline
- Optimized query processing

## 5. Extension Points for Future Integrations

The architecture is designed to make adding new database backends straightforward. Here's how to add support for new systems like Snowflake:

1. **Create Provider Module**
   ```python
   # pygovpub/storage/providers/snowflake_provider.py
   def is_available():
       """Check if snowflake-connector-python is installed"""
       try:
           import snowflake.connector
           return True
       except ImportError:
           return False
   
   def initialize(account, user, password, database, schema):
       """Initialize Snowflake connection if available"""
       if not is_available():
           raise ImportError(
               "Snowflake connector not installed. Install with: pip install pygovpub[snowflake]"
           )
       
       import snowflake.connector
       return snowflake.connector.connect(
           account=account,
           user=user,
           password=password,
           database=database,
           schema=schema
       )
   ```

2. **Update Package Configuration**
   ```python
   # setup.py extras_require update
   extras_require={
       # existing extras
       "snowflake": ["snowflake-connector-python>=3.0.0"],
   }
   ```

3. **Add Feature Detection**
   ```python
   # Add to StorageInterface._detect_features
   elif 'snowflake' in self.connection_string and self._is_package_available('snowflake.connector'):
       features['enterprise_storage'] = True
   ```

4. **Implement Database-Specific Operations**
   ```python
   # Create snowflake-specific implementations
   def search_snowflake(storage, query, limit=10):
       # Snowflake-specific implementation
       pass
   ```

## 6. Key Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Vector search performance at scale | Implement caching; add pagination; use database indexing; benchmark early |
| SQLite limitations for production use | Clearly document as development-only; automate testing to verify compatibility |
| Cloud provider API changes | Create provider version detection; add compatibility layers if needed |
| Missing optional dependencies | Implement clear error messages with installation instructions |
| Billy LLM performance issues | Implement lazy loading; add caching layer; optimize context window usage |

## 7. Testing Strategy

### 7.1 Unit Tests

Create tests that verify behavior with and without optional dependencies:

```python
# tests/test_provider_availability.py
import pytest
import sys
from unittest.mock import patch

def test_pinecone_not_available():
    # Mock an ImportError when importing pinecone
    with patch.dict(sys.modules, {'pinecone': None}):
        from pygovpub.storage.providers import pinecone_provider
        assert not pinecone_provider.is_available()
        
        # Test initialization raises the correct exception
        with pytest.raises(ImportError) as excinfo:
            pinecone_provider.initialize("fake-key", "us-east1", "test-index")
        assert "Install with: pip install pygovpub[pinecone]" in str(excinfo.value)
```

### 7.2 Integration Tests

Create tests that run only when dependencies are available:

```python
# tests/test_pinecone_integration.py
import pytest
from pygovpub.storage.providers import pinecone_provider

# Skip all tests in this module if Pinecone is not available
pytestmark = pytest.mark.skipif(
    not pinecone_provider.is_available(),
    reason="Pinecone library not installed"
)

def test_pinecone_initialization():
    # This test only runs when Pinecone is available
    # ...
```

## 8. Documentation Updates

### 8.1 Installation Guide

Update your documentation to explain the optional dependency approach:

```markdown
## Installation

### Basic Installation
```bash
pip install pygovpub
```

### With Cloud Provider Support
```bash
# For Pinecone vector database support
pip install pygovpub[pinecone]

# For Supabase support
pip install pygovpub[supabase]

# For all cloud providers
pip install pygovpub[cloud]

# For LLM support
pip install pygovpub[llm]
```

### Required Environment Variables

Depending on your configuration, you may need to set:

**For Pinecone:**
- `PINECONE_API_KEY` - Your Pinecone API key
- `PINECONE_ENVIRONMENT` - Pinecone environment (e.g., "us-east1-gcp")
- `PINECONE_INDEX` - Index name (default: "pygovpub")

**For Supabase:**
- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase API key
```

## 9. Next Steps

1. **Update Package Configuration**
   - Modify setup.py to include extras_require for optional dependencies
   - Update requirements.txt with core dependencies

2. **Start with Core Infrastructure**
   - Implement StorageInterface with PostgreSQL support
   - Add feature detection
   - Create database schema and migrations

3. **Create Provider Modules**
   - Implement isolated modules for each cloud provider
   - Add dynamic import handling
   - Create clear error messages for missing dependencies

4. **Develop Iteratively**
   - Follow implementation phases outlined above
   - Prioritize PostgreSQL support as the production database
   - Add other backends once core functionality is solid

## 10. Conclusion

This implementation plan provides a streamlined approach to expanding PyGovPub's storage architecture while making cloud providers optional. The design focuses on:

1. **Minimal abstraction** - only adding what's necessary to support multiple backends
2. **Optional dependencies** - ensuring users only install what they need
3. **Feature detection** - adapting to available libraries and capabilities
4. **Clear guidance** - providing helpful messages when optional features are requested

This approach avoids over-engineering while ensuring the system can grow to accommodate new database backends as needed. The core PostgreSQL and SQLite support will provide immediate value, with cloud providers available as opt-in features when required.
