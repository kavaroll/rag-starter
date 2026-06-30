from app.db.chroma import get_collection


class Retriever:

    def __init__(self):
        self.collection = get_collection()

    def get_by_id(self, recipe_id):
        result = self.collection.get(ids=[recipe_id], include=["documents", "metadatas"])
        if not result["ids"]:
            return None
        return {"document": result["documents"][0], "metadata": result["metadatas"][0]}

    def search(self, query, k=5, filters=None):
        kwargs = {"query_texts": [query], "n_results": k}
        if filters:
            conditions = [{k: {"$eq": v}} for k, v in filters.items()]
            kwargs["where"] = {"$and": conditions} if len(conditions) > 1 else conditions[0]
        result = self.collection.query(**kwargs)
        return result["documents"][0], result["metadatas"][0], result["ids"][0]
