
ARTICLE_SCHEMA = {
    "uuid": str,
    "source_id": str,
    "data_version": int,
    "entity_type": str,
    "url": str,
    "tags": list,
    "platform": str,
    "section": str,
    "spider_name": str,
    # "update_at": str, # 由系统自动生成
    "crawled_at": str, # Date
    "publish_at": str, # Date
    "last_edit_at": str, # Date
    "language": str,
    "author_id": str,
    "author_name": str,
    "nsfw": bool,
    "aigc": bool,
    "translation_content": str,
    "keywords": list,
    "emotion": float,
    "political_bias": list,
    "confidence": float,
    "subjective_rating": int,
    "title": str,
    "clean_content": str,
    "raw_content": str,
    "safe_raw_content": str,
    "cover_image": str,
    "vector_status": bool,
    "clean_content_vector": list,
    "likes": int,
    "is_highlighted": bool,
    "highlighted_at": str,
    "highlight_reason": str
}

DATE_FIELDS = [
    "crawled_at",
    "publish_at",
    "last_edit_at",
    "highlighted_at"
]
