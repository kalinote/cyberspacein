from uuid import uuid4

from app.utils.id_lib import generate_id


def new_section_id(page_id: str) -> str:
    return generate_id(f"wiki_section:{page_id}:{uuid4()}")
