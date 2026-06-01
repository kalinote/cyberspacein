from uuid import uuid4

from app.utils.id_lib import generate_id


def new_section_id(wiki_id: str) -> str:
    return generate_id(f"wiki_section:{wiki_id}:{uuid4()}")
