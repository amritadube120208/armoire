import hashlib
from typing import List


class EmbeddingGenerator:
    """
    Interface for CLIP-style multimodal clothing embeddings.
    Adheres to Backend.md §6 and Level 1-2 evolution in Upgradation.md.
    """

    async def generate_image_embedding(self, image_bytes: bytes) -> List[float]:
        """
        Generates normalized embedding vector (512 dimensions) for the clothing image.
        Uses deterministic hash projection for MVP testing, ready to drop in OpenCLIP / SentenceTransformers.
        """
        # Generate reproducible 512-dim vector based on image hash for MVP consistency
        hasher = hashlib.sha256(image_bytes)
        seed_ints = [int(b) for b in hasher.digest()]

        vector = []
        for i in range(512):
            val = ((seed_ints[i % len(seed_ints)] * (i + 1)) % 1000) / 1000.0 - 0.5
            vector.append(val)

        # L2 normalize
        norm = sum(x * x for x in vector) ** 0.5
        if norm > 0:
            vector = [round(x / norm, 6) for x in vector]

        return vector


embedding_generator = EmbeddingGenerator()
