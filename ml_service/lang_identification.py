from lingua import Language, LanguageDetectorBuilder

DETECTOR = LanguageDetectorBuilder.from_all_languages_with_latin_script().build()

def get_lang(text):
    result = DETECTOR.detect_language_of(text)
    return result.name if result else "UNKNOWN"

if __name__ == "__main__":
    print(get_lang("This is a test"))
    print(get_lang("测试一下"))