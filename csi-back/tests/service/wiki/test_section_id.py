from app.service.wiki.section_id import new_section_id


def test_new_section_id_unique():
    wiki_id = "b" * 32
    a = new_section_id(wiki_id)
    b = new_section_id(wiki_id)
    assert a != b
    assert len(a) == 32
