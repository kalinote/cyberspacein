from app.service.wiki.section_id import new_section_id


def test_new_section_id_unique():
    a = new_section_id("page-a")
    b = new_section_id("page-a")
    assert a != b
    assert len(a) == 32
