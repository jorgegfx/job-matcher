from __future__ import annotations

import numpy as np


class LocalEmbedder:
    """Thin wrapper around sentence-transformers. Runs entirely on-CPU on
    the GitHub-hosted runner — zero API cost, no network calls after the
    model is downloaded/cached once.
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        # Imported lazily so `--no-llm`/config-only code paths that don't
        # need it (e.g. unit tests) stay fast to import.
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def embed(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False
        )

    @staticmethod
    def cosine_similarity(a: np.ndarray, b: np.ndarray) -> np.ndarray:
        # Embeddings are already normalized, so cosine similarity is a dot product.
        return a @ b.T
