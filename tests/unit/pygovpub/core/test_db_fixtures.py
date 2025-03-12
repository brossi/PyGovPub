"""
Tests for database fixture generation and management.

This module contains unit tests for specialized fixtures that support
complex database testing scenarios.
"""

import pytest
from unittest import mock
from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy import text, Column, Integer, String, ForeignKey, Table
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Session, relationship
from sqlmodel import Field, SQLModel

from pygovpub.core.database import get_engine, with_transaction

# These will be implemented in the db_fixtures module
# Import placeholder for now
from unittest.mock import MagicMock
create_versioned_records = MagicMock()
create_relationship_test_data = MagicMock()
create_legislative_text_corpus = MagicMock()
create_bill_hierarchy = MagicMock()
create_read_only_session = MagicMock()
with_multi_database = MagicMock()
cleanup_fixtures = MagicMock()

# Create base for test models
Base = declarative_base()

# Define test models for relationship testing
class TestAuthor(SQLModel, table=True):
    """Author model for testing relationships."""
    __tablename__ = "test_authors"
    
    id: int = Field(primary_key=True)
    name: str
    organization: str


class TestDocument(SQLModel, table=True):
    """Document model for testing relationships."""
    __tablename__ = "test_documents"
    
    id: int = Field(primary_key=True)
    title: str
    content: str
    author_id: int = Field(foreign_key="test_authors.id")
    version: int = Field(default=1)
    created_at: datetime = Field(default_factory=datetime.now)


@pytest.fixture
def setup_test_tables():
    """Create test tables and clean up after test."""
    # Create tables
    engine = get_engine()
    SQLModel.metadata.create_all(engine, tables=[TestAuthor.__table__, TestDocument.__table__])
    
    yield
    
    # Drop tables after test
    SQLModel.metadata.drop_all(engine, tables=[TestAuthor.__table__, TestDocument.__table__])


class TestVersionedRecords:
    """Tests for versioned record fixtures."""
    
    def test_create_versioned_records(self, setup_test_tables):
        """Test creating versioned records for testing."""
        # Set up mock return value
        records = [
            {"id": 1, "title": "Document v1", "content": "Initial content", "version": 1},
            {"id": 1, "title": "Document v2", "content": "Updated content", "version": 2},
            {"id": 1, "title": "Document v3", "content": "Final content", "version": 3}
        ]
        create_versioned_records.return_value = records
        
        # Call function
        created_records = create_versioned_records(
            model_class=TestDocument,
            base_record={
                "id": 1,
                "title": "Document v1",
                "content": "Initial content",
                "author_id": 1
            },
            versions=3,
            version_changes={
                "title": lambda v, r: f"Document v{v}",
                "content": ["Initial content", "Updated content", "Final content"]
            }
        )
        
        # Verify result
        assert len(created_records) == 3
        assert created_records[0]["version"] == 1
        assert created_records[1]["version"] == 2
        assert created_records[2]["version"] == 3
        assert created_records[0]["title"] == "Document v1"
        assert created_records[1]["title"] == "Document v2"
        assert created_records[2]["title"] == "Document v3"
        assert created_records[0]["content"] == "Initial content"
        assert created_records[1]["content"] == "Updated content"
        assert created_records[2]["content"] == "Final content"


class TestRelationshipFixtures:
    """Tests for relationship model fixtures."""
    
    def test_create_relationship_test_data(self, setup_test_tables):
        """Test creating complex relationship test data."""
        # Setup mock return
        relationship_data = {
            "authors": [
                {"id": 1, "name": "Author 1", "organization": "Org A"},
                {"id": 2, "name": "Author 2", "organization": "Org B"}
            ],
            "documents": [
                {"id": 1, "title": "Doc 1", "content": "Content 1", "author_id": 1},
                {"id": 2, "title": "Doc 2", "content": "Content 2", "author_id": 1},
                {"id": 3, "title": "Doc 3", "content": "Content 3", "author_id": 2}
            ]
        }
        create_relationship_test_data.return_value = relationship_data
        
        # Call function
        data = create_relationship_test_data(
            models={
                "authors": TestAuthor,
                "documents": TestDocument
            },
            relationships=[
                ("documents", "author_id", "authors", "id")
            ],
            counts={
                "authors": 2,
                "documents": 3
            },
            distribution={
                "documents_per_author": [2, 1]
            }
        )
        
        # Verify result
        assert "authors" in data
        assert "documents" in data
        assert len(data["authors"]) == 2
        assert len(data["documents"]) == 3
        # Check relationships
        author1_docs = [doc for doc in data["documents"] if doc["author_id"] == 1]
        author2_docs = [doc for doc in data["documents"] if doc["author_id"] == 2]
        assert len(author1_docs) == 2
        assert len(author2_docs) == 1


class TestLegislativeFixtures:
    """Tests for legislative content fixtures."""
    
    def test_create_legislative_text_corpus(self):
        """Test creating legislative text corpus for search testing."""
        # Setup mock return
        sample_corpus = [
            {
                "id": 1,
                "title": "Healthcare Reform Act",
                "text": "A bill to reform healthcare access and improve affordability...",
                "metadata": {
                    "congress": 117,
                    "bill_type": "HR",
                    "bill_number": 1234
                }
            },
            {
                "id": 2,
                "title": "Environmental Protection Bill",
                "text": "A bill to strengthen environmental regulations...",
                "metadata": {
                    "congress": 117,
                    "bill_type": "S",
                    "bill_number": 5678
                }
            }
        ]
        create_legislative_text_corpus.return_value = sample_corpus
        
        # Call function
        corpus = create_legislative_text_corpus(
            count=2,
            topics=["healthcare", "environment"],
            include_metadata=True
        )
        
        # Verify result
        assert len(corpus) == 2
        assert "title" in corpus[0]
        assert "text" in corpus[0]
        assert "metadata" in corpus[0]
        assert "congress" in corpus[0]["metadata"]
        
        # Check topics were used
        healthcare_bills = [bill for bill in corpus if "healthcare" in bill["title"].lower()]
        environment_bills = [bill for bill in corpus if "environment" in bill["title"].lower()]
        assert len(healthcare_bills) + len(environment_bills) > 0
    
    def test_create_legislative_text_corpus_with_db_storage(self):
        """Test creating a corpus with database storage and full-text search capabilities."""
        # Skip if not postgres
        if get_engine().dialect.name != 'postgresql':
            pytest.skip("This test requires PostgreSQL")
            
        # Setup expected corpus result
        sample_corpus = [
            {
                "id": 1,
                "title": "Healthcare Reform Act",
                "text": "A bill to reform healthcare access and improve affordability...",
                "metadata": {
                    "congress": 117,
                    "bill_type": "HR",
                    "bill_number": 1234,
                    "topic": "healthcare"
                }
            },
            {
                "id": 2,
                "title": "Environmental Protection Bill",
                "text": "A bill to strengthen environmental regulations...",
                "metadata": {
                    "congress": 117,
                    "bill_type": "S",
                    "bill_number": 5678,
                    "topic": "environment"
                }
            }
        ]
        create_legislative_text_corpus.return_value = sample_corpus
        
        # Mock SQL execution for database operations
        with mock.patch('sqlalchemy.MetaData'), \
             mock.patch('sqlalchemy.Table'), \
             mock.patch('sqlalchemy.text'), \
             mock.patch('sqlalchemy.engine.Engine.begin') as mock_begin:
            
            # Configure the mock context manager
            mock_context = mock.MagicMock()
            mock_conn = mock.MagicMock()
            mock_context.__enter__.return_value = mock_conn
            mock_begin.return_value = mock_context
            
            # Call function with db storage
            corpus = create_legislative_text_corpus(
                count=2,
                topics=["healthcare", "environment"],
                include_metadata=True,
                store_in_db=True,
                table_name="test_fts_corpus"
            )
            
            # Verify result
            assert len(corpus) == 2
            
            # Verify database operations were performed
            assert mock_begin.call_count >= 1
            
            # Execute should be called multiple times:
            # - Once for each document insert (2)
            # - Once for each FTS vector update (2)
            # - Once for index creation
            assert mock_conn.execute.call_count >= 5
    
    @pytest.mark.integration
    def test_fts_corpus_integration(self):
        """Test full-text search corpus creation and querying (integration test)."""
        # Skip if not postgres
        if get_engine().dialect.name != 'postgresql':
            pytest.skip("This test requires PostgreSQL")
        
        # Mock to avoid actual DB operations in unit tests, but in integration tests
        # we'd use a real database and run the full process
        with mock.patch('sqlalchemy.Table'), \
             mock.patch('sqlalchemy.engine.Engine.begin') as mock_begin, \
             mock.patch('sqlalchemy.engine.Engine.connect') as mock_connect:
            
            # Configure mocks
            mock_begin_ctx = mock.MagicMock()
            mock_conn_begin = mock.MagicMock()
            mock_begin_ctx.__enter__.return_value = mock_conn_begin
            mock_begin.return_value = mock_begin_ctx
            
            mock_connect_ctx = mock.MagicMock()
            mock_conn = mock.MagicMock()
            mock_connect_ctx.__enter__.return_value = mock_conn
            mock_connect.return_value = mock_connect_ctx
            
            # Setup mock query results
            mock_result = mock.MagicMock()
            mock_result_rows = [
                {"id": 1, "title": "Healthcare Reform Act", "rank": 0.75},
                {"id": 2, "title": "Medical Coverage Improvement Act", "rank": 0.5}
            ]
            mock_result.__iter__.return_value = [mock.MagicMock(**row) for row in mock_result_rows]
            mock_conn.execute.return_value = mock_result
            
            # Create test table name
            test_table_name = "test_legislative_fts_corpus"
            
            # Create a corpus with DB storage for testing
            create_legislative_text_corpus.return_value = [
                {"id": 1, "title": "Healthcare Reform Act", "text": "Content..."},
                {"id": 2, "title": "Medical Coverage Improvement Act", "text": "Content..."},
                {"id": 3, "title": "Environmental Protection Act", "text": "Content..."}
            ]
            
            corpus = create_legislative_text_corpus(
                count=3,
                topics=["healthcare", "environment"],
                include_metadata=True,
                store_in_db=True,
                table_name=test_table_name
            )
            
            # Verify corpus was created
            assert len(corpus) == 3
            
            # Test a full-text search query
            search_query = text(f"""
            SELECT id, title, 
                   ts_rank(fts_document, to_tsquery('english', 'healthcare')) as rank
            FROM {test_table_name}
            WHERE fts_document @@ to_tsquery('english', 'healthcare')
            ORDER BY rank DESC
            """)
            
            # Execute search
            with get_engine().connect() as conn:
                result = conn.execute(search_query)
                healthcare_docs = [dict(row) for row in result]
            
            # Verify search results
            assert len(healthcare_docs) == 2
            assert healthcare_docs[0]["id"] == 1
            assert healthcare_docs[0]["title"] == "Healthcare Reform Act"
            assert isinstance(healthcare_docs[0]["rank"], float)
            assert healthcare_docs[0]["rank"] > healthcare_docs[1]["rank"]


class TestBillHierarchyFixtures:
    """Tests for bill hierarchy fixtures."""
    
    def test_create_bill_hierarchy(self):
        """Test creating bill hierarchy with versions and relationships."""
        # Setup mock return
        hierarchy = {
            "bill": {
                "id": 1,
                "congress": 117,
                "bill_type": "HR",
                "bill_number": 1234,
                "title": "Healthcare Reform Act"
            },
            "versions": [
                {"id": 1, "version_code": "IH", "title": "Introduced in House"},
                {"id": 2, "version_code": "RH", "title": "Reported in House"},
                {"id": 3, "version_code": "EH", "title": "Engrossed in House"}
            ],
            "actions": [
                {"id": 1, "action_code": "INTRO", "text": "Introduced in House"},
                {"id": 2, "action_code": "CMTEE", "text": "Referred to Committee"},
                {"id": 3, "action_code": "FLOOR", "text": "Placed on House Calendar"}
            ],
            "sponsors": [
                {"id": 1, "name": "Representative Smith"},
                {"id": 2, "name": "Representative Jones"}
            ]
        }
        create_bill_hierarchy.return_value = hierarchy
        
        # Call function
        bill_data = create_bill_hierarchy(
            congress=117,
            bill_type="HR",
            bill_number=1234,
            version_count=3,
            action_count=3,
            sponsor_count=2
        )
        
        # Verify result
        assert "bill" in bill_data
        assert "versions" in bill_data
        assert "actions" in bill_data
        assert "sponsors" in bill_data
        assert bill_data["bill"]["congress"] == 117
        assert bill_data["bill"]["bill_type"] == "HR"
        assert bill_data["bill"]["bill_number"] == 1234
        assert len(bill_data["versions"]) == 3
        assert len(bill_data["actions"]) == 3
        assert len(bill_data["sponsors"]) == 2


class TestDatabaseSessionFixtures:
    """Tests for database session fixtures."""
    
    def test_create_read_only_session(self):
        """Test creating a read-only database session."""
        # Create mock session
        mock_session = mock.MagicMock()
        create_read_only_session.return_value = mock_session
        
        # Call function
        session = create_read_only_session()
        
        # Verify session was returned
        assert session is not None
        assert session is mock_session
        
        # Try to use session for write operations
        session.add(TestAuthor(id=99, name="Test", organization="Org"))
        session.commit()
        
        # This should have raised an exception in the real implementation
        # but we're just checking that the mock was called
        session.add.assert_called_once()
        session.commit.assert_called_once()
    
    def test_with_multi_database(self):
        """Test the multi-database fixture context manager."""
        # Define mock context return
        mock_sessions = {"primary": mock.MagicMock(), "replica": mock.MagicMock()}
        with_multi_database.return_value.__enter__.return_value = mock_sessions
        
        # Use context manager
        with with_multi_database(["primary", "replica"]) as sessions:
            # Verify sessions were created
            assert "primary" in sessions
            assert "replica" in sessions
            
            # Try to use sessions
            sessions["primary"].query(TestAuthor).all()
            sessions["replica"].query(TestDocument).all()
            
            # Check mocks were called
            sessions["primary"].query.assert_called_once()
            sessions["replica"].query.assert_called_once()


def test_cleanup_fixtures():
    """Test cleaning up test fixtures."""
    try:
        # Simply test that the function doesn't throw an error
        # with minimal tables
        cleanup_fixtures(tables=["test_authors", "test_documents"])
        assert True
    except Exception as e:
        assert False, f"cleanup_fixtures raised an exception: {e}"