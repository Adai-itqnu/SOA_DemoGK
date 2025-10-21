from pymongo import MongoClient
from datetime import datetime
from config import MONGO_URI

client = MongoClient(MONGO_URI)
db = client["bookdb"]
collection = db["books"]

# create
def create_book(data):
    now = datetime.utcnow()
    book = {
        "id": data["id"],
        "title": data["title"],
        "author": data["author"],
        "category": data.get("category", ""),
        "quantity": int(data["quantity"]),
        "created_at": now,
        "updated_at": now
    }
    collection.insert_one(book)
    return book

# read
def get_all_books():
    books = list(collection.find({}, {"_id": 0}))
    return books

# read (by id)
def get_book_by_id(bid):
    return collection.find_one({"id":bid}, {"_id": 0})

# update
def update_book(bid, data):
    data["updated_at"] = datetime.utcnow()
    update_data = {k: v for k, v in data.items() if k in ["title", "author", "category", "quantity"]}
    result = collection.update_one({"id": bid}, {"$set": update_data})
    return result.modified_count > 0

# delete
def delete_book(bid):
    result = collection.delete_one({"id": bid})
    return result.deleted_count > 0