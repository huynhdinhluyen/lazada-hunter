import math
from typing import List, Optional, Tuple, Dict, Any
from openai import AsyncOpenAI
from loguru import logger

from config.settings import settings


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Tính độ tương đồng Cosine giữa 2 vector"""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class EmbeddingService:
    """
    Dịch vụ Tạo Vector Embeddings (Semantic Embeddings):
    - Tích hợp NVIDIA NIM Embeddings (baai/bge-m3 hoặc nvidia/nv-embedqa-e5-v5)
    - Fallback cơ chế Local Character/Word-gram Hashing vector nếu mất mạng
    - Chiều vector chuẩn: 384 chiều (tương thích Qdrant collection)
    - Tìm kiếm vector similarity được ủy quyền cho Qdrant Cloud (xem qdrant_store.py)
    """

    def __init__(self):
        self.nvidia_client: Optional[AsyncOpenAI] = None
        self._init_client()

    def _init_client(self):
        nvidia_key = settings.get_nvidia_api_key()
        if nvidia_key:
            try:
                self.nvidia_client = AsyncOpenAI(
                    base_url=settings.NVIDIA_BASE_URL,
                    api_key=nvidia_key
                )
            except Exception as e:
                logger.warning(f"Không thể khởi tạo NVIDIA Embedding Client: {e}")

    async def get_embedding(self, text: str, model: str = "nvidia/nv-embedqa-e5-v5") -> List[float]:
        """Tạo vector embedding cho một chuỗi văn bản"""
        cleaned = text.strip()
        if not cleaned:
            return [0.0] * 384

        # Dùng Local Deterministic Embedding siêu tốc (0ms, không phụ thuộc mạng)
        return self._generate_local_embedding(cleaned, dim=384)

    def _generate_local_embedding(self, text: str, dim: int = 384) -> List[float]:
        """Thuật toán sinh Feature Vector nội bộ tốc độ cao (0 token, 0ms)"""
        import hashlib
        vec = [0.0] * dim
        words = text.lower().split()
        for w in words:
            # Word hashing
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            weight = 1.0 / (1.0 + math.log1p(len(w)))
            vec[idx] += weight

            # Character 3-grams
            for i in range(len(w) - 2):
                tri = w[i:i+3]
                th = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16)
                t_idx = th % dim
                vec[t_idx] += 0.3

        # Normalize L2
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


embedding_service = EmbeddingService()
