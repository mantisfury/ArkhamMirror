from backend.embedding_services import embed_hybrid
import numpy as np

try:
    result = embed_hybrid("test")
    dense_vec = result["dense"]
    print(f"Dense vector length: {len(dense_vec)}")
except Exception as e:
    print(f"Error: {e}")
