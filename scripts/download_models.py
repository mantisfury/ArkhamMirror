import os
import argparse
import sys

# Add parent dir to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import get_config


def download_bge_m3():
    print("Downloading BGE-M3 model (approx 2.2GB)...")
    try:
        from FlagEmbedding import BGEM3FlagModel

        model_name = get_config("embedding.providers.bge-m3.model_name", "BAAI/bge-m3")
        # This triggers download
        BGEM3FlagModel(model_name, use_fp16=False, device="cpu")
        print("✅ BGE-M3 downloaded successfully.")
    except ImportError:
        print("❌ FlagEmbedding not installed. Cannot download BGE-M3.")
    except Exception as e:
        print(f"❌ Error downloading BGE-M3: {e}")


def download_minilm():
    print("Downloading MiniLM model (approx 80MB)...")
    try:
        from sentence_transformers import SentenceTransformer

        model_name = get_config(
            "embedding.providers.minilm-bm25.dense_model",
            "sentence-transformers/all-MiniLM-L6-v2",
        )
        # This triggers download
        SentenceTransformer(model_name)
        print("✅ MiniLM downloaded successfully.")
    except ImportError:
        print("❌ sentence-transformers not installed. Cannot download MiniLM.")
    except Exception as e:
        print(f"❌ Error downloading MiniLM: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download embedding models.")
    parser.add_argument(
        "--provider",
        choices=["bge-m3", "minilm-bm25", "all"],
        default="all",
        help="Which provider's model to download",
    )

    args = parser.parse_args()

    if args.provider in ["bge-m3", "all"]:
        download_bge_m3()

    if args.provider in ["minilm-bm25", "all"]:
        download_minilm()
