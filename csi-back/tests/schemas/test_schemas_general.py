"""app.schemas.general 分页与通用结构测试。"""

import pytest

from app.schemas.general import DictModelSchema, PageParamsSchema, PageResponseSchema


def test_page_params_defaults():
    # 默认页码与每页条数在约束内
    p = PageParamsSchema()
    assert p.page == 1
    assert p.page_size == 10


def test_page_params_validation_bounds():
    # page 必须 >=1，page_size 不超过 100
    with pytest.raises(Exception):
        PageParamsSchema(page=0, page_size=10)
    with pytest.raises(Exception):
        PageParamsSchema(page=1, page_size=101)


def test_page_response_create_total_pages():
    # total_pages 按整页向上取整
    r = PageResponseSchema.create(items=[1, 2], total=25, page=1, page_size=10)
    assert r.total == 25
    assert r.total_pages == 3
    assert r.items == [1, 2]


def test_page_response_create_zero_total():
    # 无数据时总页数为 0
    r = PageResponseSchema.create(items=[], total=0, page=1, page_size=10)
    assert r.total_pages == 0


def test_dict_model_schema():
    # 键值对容器
    d = DictModelSchema(key="k", value=[1, 2])
    assert d.key == "k"
    assert d.value == [1, 2]
