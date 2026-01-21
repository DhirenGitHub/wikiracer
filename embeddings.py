import json
import chromadb
from sentence_transformers import SentenceTransformer


def load_wikipedia_links(json_path: str) -> dict:
    """Load Wikipedia links from JSON file."""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def create_embeddings_and_store(json_path: str, db_path: str = "./chroma_db"):
    """
    Load Wikipedia links, create embeddings for link names, and store in ChromaDB.

    Args:
        json_path: Path to the wikipedia_links.json file
        db_path: Path to store the ChromaDB database
    """
    # Load the Wikipedia links
    print("Loading Wikipedia links...")
    data = load_wikipedia_links(json_path)
    links = data['links']
    source_page = data.get('source_page', 'Unknown')

    print(f"Loaded {len(links)} links from '{source_page}'")

    # Initialize the sentence transformer model
    print("Loading sentence transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Extract link names
    link_names = [link['name'] for link in links]

    # Create embeddings for all link names
    print("Creating embeddings for link names...")
    embeddings = model.encode(link_names, show_progress_bar=True)

    # Initialize ChromaDB client with persistent storage
    print(f"Initializing ChromaDB at {db_path}...")
    client = chromadb.PersistentClient(path=db_path)

    # Delete existing collection if it exists, then create new one
    try:
        client.delete_collection(name="wikipedia_links")
    except ValueError:
        pass  # Collection doesn't exist

    collection = client.create_collection(
        name="wikipedia_links",
        metadata={"source_page": source_page, "hnsw:space": "cosine"}
    )

    # Add embeddings to the collection
    print("Adding embeddings to ChromaDB...")
    collection.add(
        ids=[str(i) for i in range(len(links))],
        embeddings=embeddings.tolist(),
        metadatas=[{"name": link['name'], "url": link['url']} for link in links],
        documents=link_names
    )

    print(f"Successfully stored {len(links)} embeddings in ChromaDB")
    print(f"Database location: {db_path}")

    return collection


def search_similar_links(query: str, db_path: str = "./chroma_db", n_results: int = 5):
    """
    Search for links similar to the query.

    Args:
        query: The search query
        db_path: Path to the ChromaDB database
        n_results: Number of results to return

    Returns:
        List of similar links with their metadata
    """
    # Load the model
    model = SentenceTransformer('all-MiniLM-L6-v2')

    # Create embedding for the query
    query_embedding = model.encode([query])[0]

    # Initialize ChromaDB client
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_collection(name="wikipedia_links")

    # Search for similar embeddings
    results = collection.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=n_results
    )

    return results


def main():
    import os

    # Get the directory of this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, "wikipedia_links.json")
    db_path = os.path.join(script_dir, "chroma_db")

    # Create embeddings and store in vector DB
    create_embeddings_and_store(json_path, db_path)

    # Test with a sample search
    print("\n" + "="*50)
    print("Testing search functionality...")
    print("="*50)

    test_queries = ["food", "country in South America", "plant disease"]

    for query in test_queries:
        print(f"\nSearching for: '{query}'")
        results = search_similar_links(query, db_path, n_results=3)

        print("Top 3 results:")
        for i, metadata in enumerate(results['metadatas'][0], 1):
            print(f"  {i}. {metadata['name']} -> {metadata['url']}")


if __name__ == "__main__":
    main()
