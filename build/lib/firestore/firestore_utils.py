from firestore.firebase_config import db
from google.cloud.firestore_v1.base_query import FieldFilter

def add_document(collection_name: str, document_id: str, data: dict):
    """Adds a document to a Firestore collection."""
    db.collection(collection_name).document(document_id).set(data)

def get_document(collection_name: str, document_id: str) -> dict:
    """Retrieves a document from Firestore."""
    doc = db.collection(collection_name).document(document_id).get()
    return doc.to_dict() if doc.exists else None

def update_document(collection_name: str, document_id: str, updates: dict):
    """Updates fields of an existing document in Firestore."""
    db.collection(collection_name).document(document_id).update(updates)

def delete_document(collection_name: str, document_id: str):
    """Deletes a document from Firestore."""
    db.collection(collection_name).document(document_id).delete()

def query_collection(collection_name: str, field: str, operator: str, value) -> list:
    """Queries a Firestore collection for matching documents."""
    query = db.collection(collection_name).where(filter=FieldFilter(field, operator, value)).stream()
    return [{doc.id: doc.to_dict()} for doc in query]
