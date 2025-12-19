import hashlib


def generate_id(s: str):
    return hashlib.sha256(s.encode()).hexdigest()[:32]