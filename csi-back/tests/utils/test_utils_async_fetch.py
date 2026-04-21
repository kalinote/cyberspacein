from app.utils.async_fetch import unwrap_response


def test_unwrap_response_not_dict():
    """非 dict 入参原样返回。"""
    assert unwrap_response("x") == "x"
    assert unwrap_response(None) is None


def test_unwrap_response_dict_without_data_key():
    """dict 无 data 键时返回原 dict。"""
    d = {"code": 0, "message": "ok"}
    assert unwrap_response(d) is d


def test_unwrap_response_extracts_data():
    """dict 含 data 时返回 data 字段内容。"""
    assert unwrap_response({"data": {"a": 1}}) == {"a": 1}
