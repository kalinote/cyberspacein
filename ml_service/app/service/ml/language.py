import logging
from typing import Optional, List
from lingua import Language, LanguageDetector, LanguageDetectorBuilder
from app.core.config import settings
from app.service.ml.base import BaseMLService

logger = logging.getLogger(__name__)


class LanguageService(BaseMLService):
    _instance: Optional['LanguageService'] = None
    _detector: Optional[LanguageDetector] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        if self._detector is not None:
            logger.info("LanguageDetector 已初始化")
            return

        try:
            builder = self._create_detector_builder()
            
            if settings.LINGUA_LOW_ACCURACY_MODE:
                builder = builder.with_low_accuracy_mode()
                logger.info("使用低精度模式")
            
            if settings.LINGUA_PRELOAD_MODELS:
                builder = builder.with_preloaded_language_models()
                logger.info("启用语言模型预加载")
            
            self._detector = builder.build()
            logger.info("LanguageDetector 初始化成功")
        except Exception as e:
            logger.error(f"LanguageDetector 初始化失败: {e}", exc_info=True)
            raise

    def _create_detector_builder(self) -> LanguageDetectorBuilder:
        if settings.LINGUA_SUPPORTED_LANGUAGES:
            languages = self._parse_languages(settings.LINGUA_SUPPORTED_LANGUAGES)
            if languages:
                logger.info(f"使用指定语言列表: {[lang.name for lang in languages]}")
                return LanguageDetectorBuilder.from_languages(*languages)
        
        logger.info("使用所有支持的语言")
        return LanguageDetectorBuilder.from_all_languages()

    def _parse_languages(self, languages_str: str) -> List[Language]:
        languages = []
        for lang_name in languages_str.split(","):
            lang_name = lang_name.strip().upper()
            try:
                lang = Language.from_str(lang_name)
                languages.append(lang)
            except Exception as e:
                logger.warning(f"无法解析语言: {lang_name}, 错误: {e}")
        return languages

    async def cleanup(self) -> None:
        self._detector = None
        logger.info("LanguageDetector 已清理")

    def _ensure_initialized(self) -> None:
        if self._detector is None:
            raise RuntimeError("LanguageDetector 未初始化，请先调用 initialize()")

    def detect_language(self, text: str) -> Optional[dict]:
        self._ensure_initialized()
        
        if not text or not text.strip():
            return None
        
        try:
            language = self._detector.detect_language_of(text)
            if language is None:
                return None
            
            return {
                "language": language.name,
                "iso_code_639_1": language.iso_code_639_1.name if language.iso_code_639_1 else None,
                "iso_code_639_3": language.iso_code_639_3.name if language.iso_code_639_3 else None,
            }
        except Exception as e:
            logger.error(f"语言检测失败: {e}", exc_info=True)
            raise

    def detect_languages_batch(self, texts: List[str]) -> List[Optional[dict]]:
        self._ensure_initialized()
        
        try:
            results = self._detector.detect_languages_in_parallel_of(texts)
            return [
                {
                    "language": lang.name,
                    "iso_code_639_1": lang.iso_code_639_1.name if lang.iso_code_639_1 else None,
                    "iso_code_639_3": lang.iso_code_639_3.name if lang.iso_code_639_3 else None,
                } if lang else None
                for lang in results
            ]
        except Exception as e:
            logger.error(f"批量语言检测失败: {e}", exc_info=True)
            raise

    def compute_language_confidence(self, text: str) -> List[dict]:
        self._ensure_initialized()
        
        if not text or not text.strip():
            return []
        
        try:
            confidence_values = self._detector.compute_language_confidence_values(text)
            return [
                {
                    "language": conf.language.name,
                    "iso_code_639_1": conf.language.iso_code_639_1.name if conf.language.iso_code_639_1 else None,
                    "iso_code_639_3": conf.language.iso_code_639_3.name if conf.language.iso_code_639_3 else None,
                    "confidence": round(conf.value, 4)
                }
                for conf in confidence_values
            ]
        except Exception as e:
            logger.error(f"计算语言置信度失败: {e}", exc_info=True)
            raise

    def detect_multiple_languages(self, text: str) -> List[dict]:
        self._ensure_initialized()
        
        if not text or not text.strip():
            return []
        
        try:
            results = self._detector.detect_multiple_languages_of(text)
            return [
                {
                    "language": result.language.name,
                    "iso_code_639_1": result.language.iso_code_639_1.name if result.language.iso_code_639_1 else None,
                    "iso_code_639_3": result.language.iso_code_639_3.name if result.language.iso_code_639_3 else None,
                    "start_index": result.start_index,
                    "end_index": result.end_index,
                    "text": text[result.start_index:result.end_index]
                }
                for result in results
            ]
        except Exception as e:
            logger.error(f"混合语言检测失败: {e}", exc_info=True)
            raise

    def compute_single_language_confidence(self, text: str, language: Language) -> float:
        self._ensure_initialized()
        
        if not text or not text.strip():
            return 0.0
        
        try:
            return round(self._detector.compute_language_confidence(text, language), 4)
        except Exception as e:
            logger.error(f"计算单语言置信度失败: {e}", exc_info=True)
            raise


language_service = LanguageService()
