import weaviate

client = weaviate.connect_to_local(
    host="weaviate",
    port=8080
)

try:
    client.collections.delete("DocumentChunk")
    print("✅ Collection deleted!")
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
