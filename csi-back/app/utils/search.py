import re

HIGHLIGHT_MERGE_PATTERN = re.compile(r'</em>(\s*)<em>')


def merge_highlight_tags(text: str | None) -> str | None:
    if not text:
        return text
    return HIGHLIGHT_MERGE_PATTERN.sub(r'\1', text)


def has_keywords(text: str | None) -> bool:
    return bool(text and text.strip())


def rrf_merge(keyword_hits: list, vector_hits: list, k: int) -> list:
    def doc_id(h: dict) -> str:
        return h.get("_source", {}).get("uuid") or h.get("_id", "")

    rank_by_id = {}
    for rank, h in enumerate(keyword_hits, start=1):
        rank_by_id[doc_id(h)] = rank_by_id.get(doc_id(h), 0) + 1 / (k + rank)
    for rank, h in enumerate(vector_hits, start=1):
        rank_by_id[doc_id(h)] = rank_by_id.get(doc_id(h), 0) + 1 / (k + rank)
    sorted_ids = sorted(rank_by_id.keys(), key=lambda x: -rank_by_id[x])
    keyword_map = {doc_id(h): h for h in keyword_hits}
    vector_map = {doc_id(h): h for h in vector_hits}
    merged = []
    for uid in sorted_ids:
        hit = keyword_map.get(uid) or vector_map.get(uid)
        if hit:
            merged.append(hit)
    return merged
