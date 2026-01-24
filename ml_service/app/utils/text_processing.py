import re
from typing import List


def split_text_with_overlap(text: str, target_length: int = 500, overlap_length: int = 30) -> List[str]:
    """将文本分段，每段约target_length字符，保留overlap_length字符重叠窗口"""
    if not text or not text.strip():
        return []
    
    text = text.strip()
    text_len = len(text)
    
    if text_len <= target_length:
        return [text]
    
    segments = []
    start = 0
    
    while start < text_len:
        end = start + target_length
        
        if end >= text_len:
            segments.append(text[start:])
            break
        else:
            segments.append(text[start:end])
            start = end - overlap_length
    
    return segments


def remove_think_tags(text: str) -> str:
    """移除文本中的think标签"""
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
