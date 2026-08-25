"""
Qdrant Cloud Vector Store Service:
- Quản lý collection 'products' trên Qdrant Cloud (HNSW Index, Cosine Distance).
- Upsert vector + payload metadata khi cào sản phẩm mới/cập nhật.
- Semantic Search: Tìm K sản phẩm gần nhất theo vector query kèm Payload Filtering.
- Tự động tạo collection nếu chưa tồn tại (ensure_collection).
"""

from typing import List, Optional, Dict, Any
from loguru import logger

from config.settings import settings

try:
    from qdrant_client import QdrantClient, models
    from qdrant_client.http.exceptions import UnexpectedResponse
except ImportError:
    QdrantClient = None
    models = None
    UnexpectedResponse = Exception


VECTOR_DIM = 384
COLLECTION_NAME = "products"


class QdrantVectorStore:
    """
    Dịch vụ Qdrant Cloud Vector Store:
    - Kết nối Qdrant Cloud qua REST/gRPC (qdrant-client SDK).
    - Collection: 'products' (384 chiều, Cosine Distance).
    - Payload: tên, giá, rating, shop, brand, platform, url, image_url... để hỗ trợ Payload Filtering.
    """

    def __init__(self):
        self._client: Optional[QdrantClient] = None
        self._available = False
        self._init_client()

    def _init_client(self):
        api_key = settings.get_qdrant_api_key()
        endpoint = settings.QDRANT_CLUSTER_ENDPOINT
        if not api_key or not endpoint or not QdrantClient:
            logger.warning("⚠️ [QDRANT] Chưa cấu hình QDRANT_API_KEY hoặc QDRANT_CLUSTER_ENDPOINT. Qdrant Vector Store bị vô hiệu hóa.")
            return
        try:
            self._client = QdrantClient(
                url=endpoint,
                api_key=api_key,
                timeout=10,
            )
            self._available = True
            logger.info(f"✅ [QDRANT] Đã kết nối Qdrant Cloud: {endpoint}")
        except Exception as e:
            logger.error(f"❌ [QDRANT] Lỗi kết nối Qdrant Cloud: {e}")

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None

    async def ensure_collection(self):
        """Tạo collection 'products' trên Qdrant nếu chưa tồn tại và tạo Payload Indexes"""
        if not self.is_available:
            return
        try:
            collections = self._client.get_collections().collections
            existing_names = [c.name for c in collections]
            if COLLECTION_NAME not in existing_names:
                self._client.create_collection(
                    collection_name=COLLECTION_NAME,
                    vectors_config=models.VectorParams(
                        size=VECTOR_DIM,
                        distance=models.Distance.COSINE,
                    ),
                )
                logger.info(f"🧠 [QDRANT] Đã tạo collection '{COLLECTION_NAME}' ({VECTOR_DIM}D, Cosine).")
            else:
                info = self._client.get_collection(COLLECTION_NAME)
                logger.info(f"🧠 [QDRANT] Collection '{COLLECTION_NAME}' đã tồn tại ({info.points_count} points).")

            # Tự động tạo Payload Indices cho các trường lọc Range và Match
            for field_name, field_schema in [
                ("current_price", models.PayloadSchemaType.FLOAT),
                ("platform", models.PayloadSchemaType.KEYWORD),
                ("category", models.PayloadSchemaType.KEYWORD),
                ("brand", models.PayloadSchemaType.KEYWORD),
            ]:
                try:
                    self._client.create_payload_index(
                        collection_name=COLLECTION_NAME,
                        field_name=field_name,
                        field_schema=field_schema,
                    )
                except Exception:
                    pass  # index already exists
        except Exception as e:
            logger.error(f"❌ [QDRANT] Lỗi khi tạo/kiểm tra collection: {e}")

    def upsert_product(
        self,
        product_id: int,
        vector: List[float],
        payload: Dict[str, Any],
    ):
        """
        Lưu/cập nhật vector + payload metadata cho 1 sản phẩm lên Qdrant.
        Point ID = product_id trong PostgreSQL (Integer).
        """
        if not self.is_available:
            return
        try:
            self._client.upsert(
                collection_name=COLLECTION_NAME,
                points=[
                    models.PointStruct(
                        id=product_id,
                        vector=vector,
                        payload=payload,
                    )
                ],
            )
        except Exception as e:
            logger.warning(f"⚠️ [QDRANT] Lỗi upsert product #{product_id}: {e}")

    def upsert_products_batch(
        self,
        points: List[Dict[str, Any]],
    ):
        """
        Upsert hàng loạt sản phẩm lên Qdrant.
        points: List[{"id": int, "vector": List[float], "payload": dict}]
        """
        if not self.is_available or not points:
            return
        try:
            qdrant_points = [
                models.PointStruct(
                    id=p["id"],
                    vector=p["vector"],
                    payload=p["payload"],
                )
                for p in points
            ]
            self._client.upsert(
                collection_name=COLLECTION_NAME,
                points=qdrant_points,
            )
            logger.debug(f"📤 [QDRANT] Đã upsert batch {len(points)} products.")
        except Exception as e:
            logger.warning(f"⚠️ [QDRANT] Lỗi upsert batch: {e}")

    def search_similar(
        self,
        query_vector: List[float],
        limit: int = 20,
        score_threshold: float = 0.3,
        price_max: Optional[float] = None,
        platform: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Tìm kiếm K sản phẩm tương đồng nhất theo vector.
        Hỗ trợ Payload Filtering (giá, platform...) ngay trong lúc duyệt HNSW graph.

        Returns: List[{"id": int, "score": float, "payload": dict}]
        """
        if not self.is_available:
            return []

        # Build Qdrant filter conditions
        must_conditions = []
        if price_max and price_max > 0:
            must_conditions.append(
                models.FieldCondition(
                    key="current_price",
                    range=models.Range(lte=price_max),
                )
            )
        if platform:
            must_conditions.append(
                models.FieldCondition(
                    key="platform",
                    match=models.MatchValue(value=platform),
                )
            )

        query_filter = models.Filter(must=must_conditions) if must_conditions else None

        try:
            results = self._client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
                score_threshold=score_threshold,
            )
            hits = []
            for point in results.points:
                hits.append({
                    "id": point.id,
                    "score": point.score,
                    "payload": point.payload or {},
                })
            logger.debug(f"🔍 [QDRANT] Tìm thấy {len(hits)} kết quả tương đồng (threshold={score_threshold}).")
            return hits
        except Exception as e:
            logger.warning(f"⚠️ [QDRANT] Lỗi search với filter: {e}. Thử search fallback...")
            try:
                # Fallback: query không filter và lọc in-memory
                results = self._client.query_points(
                    collection_name=COLLECTION_NAME,
                    query=query_vector,
                    limit=limit * 2,
                    score_threshold=score_threshold,
                )
                hits = []
                for point in results.points:
                    payload = point.payload or {}
                    if price_max and price_max > 0:
                        cp = float(payload.get("current_price") or 0)
                        if cp > price_max:
                            continue
                    if platform and payload.get("platform") != platform:
                        continue
                    hits.append({
                        "id": point.id,
                        "score": point.score,
                        "payload": payload,
                    })
                    if len(hits) >= limit:
                        break
                return hits
            except Exception as e2:
                logger.warning(f"⚠️ [QDRANT] Lỗi search fallback: {e2}")
                return []

    def delete_product(self, product_id: int):
        """Xóa 1 point khỏi Qdrant"""
        if not self.is_available:
            return
        try:
            self._client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=[product_id]),
            )
        except Exception as e:
            logger.warning(f"⚠️ [QDRANT] Lỗi delete product #{product_id}: {e}")

    def get_collection_info(self) -> Optional[Dict[str, Any]]:
        """Lấy thông tin collection (số points, config...)"""
        if not self.is_available:
            return None
        try:
            info = self._client.get_collection(COLLECTION_NAME)
            return {
                "name": COLLECTION_NAME,
                "points_count": info.points_count,
                "indexed_vectors_count": getattr(info, "indexed_vectors_count", None),
                "status": str(info.status),
            }
        except Exception as e:
            logger.warning(f"⚠️ [QDRANT] Lỗi get collection info: {e}")
            return None


# Singleton
qdrant_store = QdrantVectorStore()
