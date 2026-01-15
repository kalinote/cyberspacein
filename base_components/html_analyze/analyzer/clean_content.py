from analyzer.base import BaseAnalyzer
from bs4 import BeautifulSoup

class CleanContentAnalyzer(BaseAnalyzer):
    @staticmethod
    def analyze(content: str) -> str:
        soup = BeautifulSoup(content, "html.parser")
        return soup.get_text().strip()