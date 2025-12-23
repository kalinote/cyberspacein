import json
import logging
from typing import List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class FileStorage:
    def __init__(self):
        pass

    def _normalize_path(self, file_path: str) -> Path:
        path = Path(file_path)
        if path.is_absolute():
            return path
        else:
            return Path.cwd() / path

    def _ensure_directory(self, file_path: Path):
        directory = file_path.parent
        if directory and not directory.exists():
            directory.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建目录: {directory}")

    def write_documents(self, file_path: str, documents: List[Dict[str, Any]]):
        try:
            normalized_path = self._normalize_path(file_path)
            self._ensure_directory(normalized_path)
            
            with open(normalized_path, 'w', encoding='utf-8') as f:
                json.dump(documents, f, ensure_ascii=False, indent=4)
            
            logger.info(f"写入文件成功: {normalized_path}, 共 {len(documents)} 条记录")
        except Exception as e:
            logger.error(f"写入文件失败: {e}")
            raise

    def append_documents(self, file_path: str, documents: List[Dict[str, Any]]):
        try:
            normalized_path = self._normalize_path(file_path)
            self._ensure_directory(normalized_path)
            
            existing_data = []
            if normalized_path.exists():
                try:
                    with open(normalized_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                        if not isinstance(existing_data, list):
                            existing_data = [existing_data]
                except (json.JSONDecodeError, ValueError):
                    existing_data = []
            
            existing_data.extend(documents)
            
            with open(normalized_path, 'w', encoding='utf-8') as f:
                json.dump(existing_data, f, ensure_ascii=False, indent=4)
            
            logger.info(f"追加文件成功: {normalized_path}, 新增 {len(documents)} 条记录")
        except Exception as e:
            logger.error(f"追加文件失败: {e}")
            raise

