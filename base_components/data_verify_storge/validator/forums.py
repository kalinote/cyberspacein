
FORUMS_SCHEMA = {
    "uuid": str,
    "source_id": str,
    "data_version": int,
    "entity_type": str,
    "url": str,
    "tags": list,
    "platform": str,
    "section": str,
    "spider_name": str,
    # "update_at": str, # Auto generated
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
    "topic_id": str,
    "parent_id": str,
    "floor": int,
    "thread_type": str,
    "category_tag": str,
    "title": str,
    "clean_content": str,
    "raw_content": str,
    "safe_raw_content": str,
    "files_urls": list,
    "status_flags": list,
    "likes": int,
    "dislikes": int,
    "collections": int,
    "comments": int,
    "views": int
}

DATE_FIELDS = [
    "crawled_at",
    "publish_at",
    "last_edit_at"
]
