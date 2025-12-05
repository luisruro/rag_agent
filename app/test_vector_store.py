# app/test_vector_store.py
import weaviate
import os
from dotenv import load_dotenv

load_dotenv()

def test_vector_store():
    """Test if vector store has documents"""
    client = None
    try:
        # Connect to Weaviate
        print("Connecting to Weaviate...")
        client = weaviate.connect_to_local(
            host="weaviate",
            port=8088
        )
        
        print(" Connected to Weaviate")
        
        # Check collection - list_all() returns a list of collection names
        collections = client.collections.list_all()
        print(f"\n Available collections: {collections}")
        
        if "DocumentChunk" in collections:
            collection = client.collections.get("DocumentChunk")
            
            # Count documents
            count = collection.aggregate.over_all(total_count=True).total_count
            print(f"\n DocumentChunk collection has {count} documents")
            
            # Get a sample document
            if count > 0:
                response = collection.query.fetch_objects(limit=3)
                print(f"\n Sample documents ({len(response.objects)}):")
                
                for i, obj in enumerate(response.objects):
                    print(f"\n--- Document {i+1} ---")
                    print(f"Source: {obj.properties.get('source', 'N/A')}")
                    print(f"Page: {obj.properties.get('page_label', 'N/A')}")
                    print(f"Chunk Index: {obj.properties.get('chunk_index', 'N/A')}")
                    text = obj.properties.get('text', '')
                    print(f"Text preview: {text[:100]}...")
                    
                    # Check if vector exists
                    if obj.vector:
                        print(f"Vector dimension: {len(obj.vector)}")
                    else:
                        print("Vector: Not available")
                        
                # Test a simple query
                print(f"\n Testing basic query...")
                results = collection.query.fetch_objects(
                    limit=2,
                    filters=weaviate.classes.query.Filter.by_property("chunk_index").equal(0)
                )
                print(f"Found {len(results.objects)} documents with chunk_index 0")
                
            else:
                print(" Collection is empty!")
        else:
            print(" DocumentChunk collection doesn't exist!")
        
    except Exception as e:
        print(f" Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            client.close()
            print("\n Connection closed properly")
        
if __name__ == "__main__":
    test_vector_store()