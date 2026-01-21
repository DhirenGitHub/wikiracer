import os
import chromadb
from sentence_transformers import SentenceTransformer


class EmbeddingStore:
    def __init__(self, db_path: str = None):
        if db_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            db_path = os.path.join(script_dir, "chroma_db")

        self.db_path = db_path
        self.model = None
        self.client = None

    def _load_model(self):
        """Lazy load the sentence transformer model."""
        if self.model is None:
            print("Loading sentence transformer model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.model

    def _get_client(self):
        """Get or create ChromaDB client."""
        if self.client is None:
            self.client = chromadb.PersistentClient(path=self.db_path)
        return self.client

    def _clear_collection(self):
        """Clear the ChromaDB collection."""
        client = self._get_client()
        try:
            client.delete_collection(name="wikipedia_links")
        except ValueError:
            pass

    def store_links(self, links: list) -> chromadb.Collection:
        """
        Create embeddings for links and store in ChromaDB.

        Args:
            links: List of dicts with 'name' and 'url' keys

        Returns:
            ChromaDB collection
        """
        self._clear_collection()

        model = self._load_model()
        link_names = [link['name'] for link in links]

        print("Creating embeddings...")
        embeddings = model.encode(link_names, show_progress_bar=False)

        client = self._get_client()
        collection = client.create_collection(
            name="wikipedia_links",
            metadata={"hnsw:space": "cosine"}
        )

        collection.add(
            ids=[str(i) for i in range(len(links))],
            embeddings=embeddings.tolist(),
            metadatas=[{"name": link['name'], "url": link['url']} for link in links],
            documents=link_names
        )

        return collection

    def find_closest(self, query: str, collection, n_results: int = 1, exclude_urls: set = None) -> list:
        """
        Find links most semantically similar to the query.

        Args:
            query: Search query string
            collection: ChromaDB collection to search
            n_results: Number of results to return
            exclude_urls: Set of URLs to exclude from results

        Returns:
            List of dicts with 'name', 'url', and 'distance' keys
        """
        model = self._load_model()
        query_embedding = model.encode([query])[0]

        # Request more results if we need to filter some out
        fetch_count = n_results
        if exclude_urls:
            fetch_count = min(n_results + len(exclude_urls), 100)

        results = collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=fetch_count
        )

        if not results['metadatas'] or not results['metadatas'][0]:
            return []

        matches = []
        for i, metadata in enumerate(results['metadatas'][0]):
            url = metadata['url']

            # Skip excluded URLs
            if exclude_urls and url in exclude_urls:
                continue

            matches.append({
                'name': metadata['name'],
                'url': url,
                'distance': results['distances'][0][i] if results['distances'] else None
            })

            if len(matches) >= n_results:
                break

        return matches
