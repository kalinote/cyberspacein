"""app.utils.search 高亮合并与 RRF 融合测试。"""

from app.utils.search import has_keywords, merge_highlight_tags, rrf_merge


def test_merge_highlight_tags_merges_adjacent_em():
    # 相邻 </em><em> 之间的空白应合并保留
    s = merge_highlight_tags("a</em> <em>b")
    assert s == "a b"


def test_merge_highlight_tags_none_passthrough():
    assert merge_highlight_tags(None) is None
    assert merge_highlight_tags("") == ""


def test_has_keywords():
    # 空或仅空白视为无关键词
    assert has_keywords(None) is False
    assert has_keywords("   ") is False
    assert has_keywords("x") is True


def test_rrf_merge_orders_by_fused_score():
    # 同一文档在两路结果中应合并分数并排序
    kw = [{"_source": {"uuid": "a"}, "_id": ""}]
    vec = [{"_source": {"uuid": "b"}, "_id": ""}]
    merged = rrf_merge(kw, vec, k=60)
    assert len(merged) == 2
    ids = [m["_source"]["uuid"] for m in merged]
    assert set(ids) == {"a", "b"}


def test_rrf_merge_doc_id_fallback_to_hit_id():
    # 无 uuid 时退回 _id
    kw = [{"_source": {}, "_id": "hid1"}]
    merged = rrf_merge(kw, [], k=10)
    assert len(merged) == 1
