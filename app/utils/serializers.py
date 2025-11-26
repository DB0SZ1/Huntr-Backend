"""
Serialization utilities for MongoDB objects
Converts ObjectId and datetime to JSON-serializable formats
"""
from bson import ObjectId
from datetime import datetime
from typing import Any, Dict, List


def serialize_object_id(obj: Any) -> Any:
    """
    Convert MongoDB ObjectId to string recursively
    Also handles datetime objects
    """
    if isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            serialized_value = serialize_object_id(value)
            # Ensure _id is never None or "Unknown"
            if key == "_id" and (not serialized_value or serialized_value == "Unknown"):
                result[key] = str(value) if value else ""
            else:
                result[key] = serialized_value
        return result
    elif isinstance(obj, list):
        return [serialize_object_id(item) for item in obj]
    else:
        return obj


def serialize_documents(documents: List[Dict]) -> List[Dict]:
    """
    Serialize a list of MongoDB documents
    Ensures all _id fields are valid strings
    """
    result = []
    for doc in documents:
        serialized = serialize_object_id(doc)
        # Ensure _id is always present and valid
        if "_id" not in serialized or not serialized["_id"]:
            if "_id" in doc:
                serialized["_id"] = str(doc["_id"])
            else:
                serialized["_id"] = ""
        result.append(serialized)
    return result


def serialize_document(document: Dict) -> Dict:
    """
    Serialize a single MongoDB document
    Ensures _id field is valid
    """
    serialized = serialize_object_id(document)
    # Ensure _id is always present and valid
    if "_id" not in serialized or not serialized["_id"]:
        if "_id" in document:
            serialized["_id"] = str(document["_id"])
        else:
            serialized["_id"] = ""
    return serialized
