from qdrant_client import models

try:
    q = models.FusionQuery(fusion=models.Fusion.RRF)
    print("Success with fusion=...")
except Exception as e:
    print(f"Failed with fusion=...: {e}")

try:
    q = models.FusionQuery(method=models.Fusion.RRF)
    print("Success with method=...")
except Exception as e:
    print(f"Failed with method=...: {e}")
