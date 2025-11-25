from FlagEmbedding import BGEM3FlagModel
import torch


device = "cuda" if torch.cuda.is_available() else "cpu"
model = None


def get_model():
    global model
    if model is None:
        print(f"Loading BGE-M3 Model on {device}...")
        model = BGEM3FlagModel(
            "BAAI/bge-m3", use_fp16=(device == "cuda"), device=device
        )
    return model


def embed_hybrid(text):
    model_instance = get_model()
    output = model_instance.encode(text, return_dense=True, return_sparse=True)
    return {"dense": output["dense_vecs"].tolist(), "sparse": output["lexical_weights"]}
