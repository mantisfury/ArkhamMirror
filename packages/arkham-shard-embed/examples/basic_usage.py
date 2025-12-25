"""
Basic usage examples for the Embed Shard.

This demonstrates how to use the Embed Shard API endpoints
and public methods.
"""

import asyncio
import httpx


# Example 1: Embed a single text
async def embed_single_text():
    """Embed a single text using the API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/embed/text",
            json={
                "text": "ArkhamMirror is a local-first document intelligence platform.",
                "use_cache": True
            }
        )
        result = response.json()
        print(f"Embedding dimensions: {result['dimensions']}")
        print(f"Model: {result['model']}")
        print(f"Vector length: {len(result['embedding'])}")
        return result['embedding']


# Example 2: Embed multiple texts in batch
async def embed_batch_texts():
    """Embed multiple texts efficiently."""
    texts = [
        "Document intelligence for journalists",
        "Hybrid OCR with PaddleOCR and Qwen-VL",
        "Semantic search with vector embeddings",
        "Entity extraction and relationship mapping"
    ]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/embed/batch",
            json={"texts": texts, "batch_size": 32}
        )
        result = response.json()
        print(f"Embedded {result['count']} texts")
        print(f"Dimensions: {result['dimensions']}")
        return result['embeddings']


# Example 3: Calculate similarity between two texts
async def calculate_similarity():
    """Calculate semantic similarity between two texts."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/embed/similarity",
            json={
                "text1": "The cat sat on the mat",
                "text2": "A feline rested on the rug",
                "method": "cosine"
            }
        )
        result = response.json()
        print(f"Similarity: {result['similarity']:.4f}")
        print(f"Method: {result['method']}")
        return result['similarity']


# Example 4: Find nearest neighbors
async def find_nearest_neighbors():
    """Find documents similar to a query."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/embed/nearest",
            json={
                "query": "corruption investigation documents",
                "limit": 10,
                "min_similarity": 0.7,
                "collection": "documents"
            }
        )
        result = response.json()
        print(f"Found {result['total']} similar documents")
        for i, neighbor in enumerate(result['neighbors'][:3]):
            print(f"{i+1}. Score: {neighbor.get('score', 'N/A')}")
        return result['neighbors']


# Example 5: Queue document embedding job
async def queue_document_embedding(doc_id: str):
    """Queue an async job to embed a document."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://localhost:8000/api/embed/document/{doc_id}",
            json={
                "force": False,
                "chunk_size": 512,
                "chunk_overlap": 50
            }
        )
        result = response.json()
        print(f"Job ID: {result['job_id']}")
        print(f"Status: {result['status']}")
        return result['job_id']


# Example 6: Get available models
async def list_models():
    """List available embedding models."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/embed/models")
        models = response.json()
        print("Available models:")
        for model in models:
            status = "LOADED" if model['loaded'] else "available"
            print(f"  - {model['name']} ({status})")
            print(f"    Dimensions: {model['dimensions']}")
            print(f"    Size: {model['size_mb']} MB")
            print(f"    {model['description']}")
        return models


# Example 7: Check cache statistics
async def check_cache_stats():
    """Get cache performance statistics."""
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/api/embed/cache/stats")
        stats = response.json()
        if stats.get('enabled'):
            print("Cache Statistics:")
            print(f"  Hits: {stats['hits']}")
            print(f"  Misses: {stats['misses']}")
            print(f"  Current size: {stats['size']}/{stats['max_size']}")
            hit_rate = stats['hits'] / (stats['hits'] + stats['misses']) if (stats['hits'] + stats['misses']) > 0 else 0
            print(f"  Hit rate: {hit_rate:.2%}")
        else:
            print("Cache is disabled")
        return stats


# Example 8: Using the shard from another shard (code example)
def example_shard_to_shard_usage():
    """
    Example of how to use the Embed Shard from another shard.

    This is not executable - it shows the pattern for shard-to-shard communication.
    """
    code = '''
    # In another shard's code:

    class MyAnalysisShard(ArkhamShard):
        async def initialize(self, frame):
            self.frame = frame
            self.embed_shard = None

        async def analyze_document(self, text: str):
            # Get the embed shard
            if not self.embed_shard:
                self.embed_shard = self.frame.get_shard("embed")

            # Embed the text
            embedding = await self.embed_shard.embed_text(text)

            # Find similar documents
            similar = await self.embed_shard.find_similar(
                query=text,
                collection="documents",
                limit=10,
                min_similarity=0.8
            )

            # Use the results
            for doc in similar:
                print(f"Similar doc: {doc['id']} (score: {doc['score']})")
    '''
    print("Shard-to-Shard Usage Pattern:")
    print(code)


# Run all examples
async def main():
    """Run all examples."""
    print("=" * 60)
    print("Embed Shard Examples")
    print("=" * 60)

    print("\n1. Embedding a single text...")
    await embed_single_text()

    print("\n2. Embedding multiple texts in batch...")
    await embed_batch_texts()

    print("\n3. Calculating text similarity...")
    await calculate_similarity()

    print("\n4. Finding nearest neighbors...")
    await find_nearest_neighbors()

    print("\n5. Queuing document embedding job...")
    # await queue_document_embedding("example-doc-123")
    print("   (Skipped - requires valid document ID)")

    print("\n6. Listing available models...")
    await list_models()

    print("\n7. Checking cache statistics...")
    await check_cache_stats()

    print("\n8. Shard-to-shard usage pattern...")
    example_shard_to_shard_usage()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run examples
    # Note: Requires the ArkhamFrame server to be running
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure the ArkhamFrame server is running on localhost:8000")
