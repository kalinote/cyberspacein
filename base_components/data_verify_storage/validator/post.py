from .article import ARTICLE_SCHEMA, DATE_FIELDS as ARTICLE_DATE_FIELDS


POST_SCHEMA = {
    **ARTICLE_SCHEMA,
    "post_type": str,
    "parent_id": str,
    "mentions": list,
    "metrics": dict,
    "geo_location": dict,
    "ip_location": str,
    "files_urls": list,
    "media_resources": list,
    "media_summary": dict,
}

DATE_FIELDS = ARTICLE_DATE_FIELDS.copy()
