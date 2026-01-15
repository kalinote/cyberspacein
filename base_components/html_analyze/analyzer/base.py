
class BaseAnalyzer:
    @staticmethod
    def analyze(content: str) -> str:
        raise NotImplementedError(f"{__class__.__name__} 分析方法尚未实现")
