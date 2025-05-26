import pytest
from firestore.firestore_utils import add_document, get_document, update_document, delete_document, query_collection

COLLECTION_NAME = "test_collection"

@pytest.fixture
def sample_data():
    """Sample JSON data for tests."""
    return {
        "name": "Test User",
        "email": "testuser@example.com",
        "age": 25,
        "roles": ["admin", "editor"]
    }

@pytest.fixture(autouse=True)
def cleanup_firestore():
    """Cleanup Firestore test collection after each test."""
    yield
    docs = query_collection(COLLECTION_NAME, "age", ">", 0)  # Query all documents
    for doc in docs:
        doc_id = list(doc.keys())[0]
        delete_document(COLLECTION_NAME, doc_id)

@pytest.mark.skip(reason="No changes to firestore")
def test_add_document(sample_data):
    """Test adding a document to Firestore."""
    doc_id = "user_1"
    add_document(COLLECTION_NAME, doc_id, sample_data)
    result = get_document(COLLECTION_NAME, doc_id)
    assert result == sample_data

@pytest.mark.skip(reason="No changes to firestore")
def test_get_document(sample_data):
    """Test retrieving a document from Firestore."""
    doc_id = "user_2"
    add_document(COLLECTION_NAME, doc_id, sample_data)
    result = get_document(COLLECTION_NAME, doc_id)
    assert result == sample_data

    # Test non-existent document
    assert get_document(COLLECTION_NAME, "non_existent") is None

@pytest.mark.skip(reason="No changes to firestore")
def test_update_document(sample_data):
    """Test updating a document in Firestore."""
    doc_id = "user_3"
    add_document(COLLECTION_NAME, doc_id, sample_data)
    updates = {"age": 30, "roles": ["admin"]}
    update_document(COLLECTION_NAME, doc_id, updates)
    result = get_document(COLLECTION_NAME, doc_id)
    assert result["age"] == 30
    assert result["roles"] == ["admin"]

@pytest.mark.skip(reason="No changes to firestore")
def test_delete_document(sample_data):
    """Test deleting a document from Firestore."""
    doc_id = "user_4"
    add_document(COLLECTION_NAME, doc_id, sample_data)
    delete_document(COLLECTION_NAME, doc_id)
    assert get_document(COLLECTION_NAME, doc_id) is None

@pytest.mark.skip(reason="No changes to firestore")
def test_query_documents(sample_data):
    """Test querying documents from Firestore."""
    doc_id_1 = "user_5"
    doc_id_2 = "user_6"
    sample_data_2 = {**sample_data, "name": "Another User", "age": 35}
    
    add_document(COLLECTION_NAME, doc_id_1, sample_data)
    add_document(COLLECTION_NAME, doc_id_2, sample_data_2)

    # Query for users younger than 30
    results = query_collection(COLLECTION_NAME, "age", "<", 30)
    assert len(results) == 1
    assert doc_id_1 in results[0]

    # Query for users older than 30
    results = query_collection(COLLECTION_NAME, "age", ">", 30)
    assert len(results) == 1
    assert doc_id_2 in results[0]
