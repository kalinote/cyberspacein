import logging
import re
from typing import Set
from urllib.parse import urlparse

import bleach
import esprima
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)

MEDIA_TAGS_ATTRS = {
    'img': ['src', 'srcset', 'data-src', 'data-srcset'],
    'video': ['src', 'poster', 'data-src', 'data-poster'],
    'audio': ['src', 'data-src'],
    'source': ['src', 'srcset', 'data-src', 'data-srcset'],
    'image': ['href', 'xlink:href'],
}

def _filter_resource_url(url: str) -> str | None:
    # 暂时不做过滤
    return url

def _extract_srcset_urls(srcset: str) -> Set[str]:
    urls: Set[str] = set()
    if not srcset:
        return urls
    for item in srcset.split(','):
        item = item.strip()
        if not item:
            continue
        tokens = item.split()
        if tokens:
            u = _filter_resource_url(tokens[0])
            if u:
                urls.add(u)
    return urls


def _extract_css_urls(css_content: str) -> Set[str]:
    urls: Set[str] = set()
    if not css_content:
        return urls
    url_pattern = r'url\s*\(\s*(["\']?)([^"\'()]+)\1\s*\)'
    for match in re.finditer(url_pattern, css_content, flags=re.IGNORECASE):
        u = _filter_resource_url(match.group(2).strip())
        if u:
            urls.add(u)
    return urls


def _collect_resource_links(html: str) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    seen: Set[str] = set()
    result: list[str] = []
    for tag_name, attrs in MEDIA_TAGS_ATTRS.items():
        for tag in soup.find_all(tag_name):
            for attr in attrs:
                if tag.has_attr(attr):
                    raw = tag[attr]
                    if attr in ('srcset', 'data-srcset'):
                        for u in _extract_srcset_urls(raw):
                            if u not in seen:
                                seen.add(u)
                                result.append(u)
                    else:
                        u = _filter_resource_url(raw)
                        if u and u not in seen:
                            seen.add(u)
                            result.append(u)
    for tag in soup.find_all(style=True):
        for u in _extract_css_urls(tag['style']):
            if u not in seen:
                seen.add(u)
                result.append(u)
    for style_tag in soup.find_all('style'):
        if style_tag.string:
            for u in _extract_css_urls(style_tag.string):
                if u not in seen:
                    seen.add(u)
                    result.append(u)
    return result


class JSSafeAnalyzer:
    def __init__(self, script_content: str, dangerous_functions: Set[str] | None = None):
        self.script_content = script_content
        self.is_malicious = False
        self.dangerous_functions = dangerous_functions or {
            'eval', 'setTimeout', 'setInterval', 'Function',
            'document.write', 'innerHTML', 'outerHTML',
            'execScript', 'constructor'
        }
        self.found_issues: list[str] = []

    def analyze(self) -> bool:
        try:
            tree = esprima.parseScript(self.script_content)
            self._traverse(tree)
            return self.is_malicious
        except Exception as e:
            logger.warning(f"JavaScript 解析失败，标记为可疑: {str(e)}")
            self.is_malicious = True
            self.found_issues.append(f"解析失败: {str(e)}")
            return True

    def _traverse(self, node):
        if not hasattr(node, 'type'):
            return
        if node.type == 'CallExpression':
            self._check_call_expression(node.callee)
        for key, value in vars(node).items():
            if isinstance(value, list):
                for item in value:
                    self._traverse(item)
            elif hasattr(value, 'type'):
                self._traverse(value)

    def _check_call_expression(self, callee):
        if hasattr(callee, 'type'):
            if callee.type == 'Identifier' and callee.name in self.dangerous_functions:
                self.is_malicious = True
                self.found_issues.append(f"危险函数: {callee.name}")
            elif callee.type == 'MemberExpression':
                if hasattr(callee, 'property') and hasattr(callee.property, 'name'):
                    if callee.property.name in self.dangerous_functions:
                        self.is_malicious = True
                        self.found_issues.append(f"危险函数: {callee.property.name}")


class WebSanitizer:
    def __init__(self,
                 raw_html: str,
                 allowed_tags: Set[str] | None = None,
                 allowed_attrs: dict[str, list[str]] | None = None,
                 allowed_css_props: list[str] | None = None):
        self.raw_html = raw_html
        self.allowed_tags = allowed_tags or {
            'div', 'span', 'p', 'br', 'hr', 'strong', 'em', 'b', 'i', 'u', 's', 'font',
            'a', 'img', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th', 'caption',
            'ul', 'ol', 'li', 'dl', 'dt', 'dd',
            'blockquote', 'code', 'pre', 'kbd', 'samp', 'var',
            'section', 'article', 'aside', 'nav', 'header', 'footer', 'main',
            'figure', 'figcaption', 'details', 'summary',
            'mark', 'small', 'sub', 'sup', 'abbr', 'time',
            'video', 'audio', 'source',
            'style', 'script'
        }
        self.allowed_attrs = allowed_attrs or {
            'a': ['href', 'title', 'target', 'rel', 'name'],
            'img': ['src', 'alt', 'width', 'height', 'title', 'loading', 'srcset', 'sizes'],
            'video': ['src', 'poster', 'controls', 'autoplay', 'loop', 'muted', 'preload', 'width', 'height', 'data-src', 'data-poster'],
            'audio': ['src', 'controls', 'autoplay', 'loop', 'muted', 'preload', 'data-src'],
            'source': ['src', 'srcset', 'type', 'media', 'sizes', 'data-src', 'data-srcset'],
            'table': ['border', 'cellpadding', 'cellspacing', 'width', 'height'],
            'td': ['colspan', 'rowspan', 'width', 'height', 'align', 'valign'],
            'th': ['colspan', 'rowspan', 'width', 'height', 'align', 'valign', 'scope'],
            'ol': ['start', 'type'],
            'ul': ['type'],
            'li': ['value'],
            'font': ['color', 'face', 'size'],
            '*': ['class', 'id', 'style', 'title', 'lang', 'dir', 'data-*']
        }
        self.css_sanitizer = CSSSanitizer(
            allowed_css_properties=allowed_css_props or [
                'color', 'background', 'background-color', 'background-image',
                'background-position', 'background-size', 'background-repeat',
                'font', 'font-size', 'font-weight', 'font-family', 'font-style',
                'text-align', 'text-decoration', 'text-transform', 'text-indent',
                'line-height', 'letter-spacing', 'word-spacing', 'white-space',
                'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left',
                'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
                'border', 'border-top', 'border-right', 'border-bottom', 'border-left',
                'border-width', 'border-style', 'border-color', 'border-radius',
                'border-collapse', 'border-spacing',
                'width', 'height', 'max-width', 'max-height', 'min-width', 'min-height',
                'display', 'visibility', 'opacity', 'overflow', 'overflow-x', 'overflow-y',
                'position', 'top', 'right', 'bottom', 'left', 'z-index',
                'flex', 'flex-direction', 'flex-wrap', 'justify-content', 'align-items',
                'flex-grow', 'flex-shrink', 'flex-basis', 'align-self',
                'grid', 'grid-template-columns', 'grid-template-rows', 'grid-gap',
                'grid-column', 'grid-row', 'grid-area',
                'float', 'clear', 'vertical-align',
                'list-style', 'list-style-type', 'list-style-position', 'list-style-image',
                'box-shadow', 'text-shadow', 'transform', 'transition', 'animation',
                'cursor', 'pointer-events', 'user-select'
            ]
        )
        self.dangerous_url_schemes = {'javascript:', 'data:', 'vbscript:', 'file:'}
        self.dangerous_css_patterns = [
            r'expression\s*\(',
            r'behavior\s*:',
            r'-moz-binding\s*:',
            r'@import\s+["\']?(?!https?://)',
            r'javascript\s*:',
            r'vbscript\s*:',
        ]

    def _attribute_filter(self, tag: str, name: str, value: str) -> bool:
        if name.startswith('on'):
            return False
        if name in ['href', 'src', 'action', 'formaction', 'data', 'poster', 'cite']:
            value_lower = value.lower().strip()
            for scheme in self.dangerous_url_schemes:
                if value_lower.startswith(scheme):
                    return False
        if name == 'style':
            return self._is_safe_css(value)
        return True

    def _is_safe_css(self, css_content: str) -> bool:
        if not css_content:
            return True
        css_lower = css_content.lower()
        for pattern in self.dangerous_css_patterns:
            if re.search(pattern, css_lower, re.IGNORECASE):
                logger.warning(f"检测到危险CSS模式: {pattern}")
                return False
        return True

    def clean_style_tag_content(self, css_content: str) -> str:
        if not css_content:
            return ""
        lines = []
        for line in css_content.split('\n'):
            line_lower = line.lower()
            is_dangerous = False
            for pattern in self.dangerous_css_patterns:
                if re.search(pattern, line_lower, re.IGNORECASE):
                    logger.warning(f"移除危险CSS行: {line.strip()}")
                    is_dangerous = True
                    break
            if not is_dangerous:
                lines.append(line)
        return '\n'.join(lines)

    def sanitize(self) -> str:
        try:
            clean_html = bleach.clean(
                self.raw_html,
                tags=self.allowed_tags,
                attributes=self._attribute_filter,
                css_sanitizer=self.css_sanitizer,
                strip=True
            )
            return clean_html
        except Exception as e:
            logger.error(f"HTML 清理失败: {str(e)}")
            return ""


def _is_html_content(content: str) -> bool:
    html_indicators = [
        r'<\s*([a-zA-Z][a-zA-Z0-9]*)\b[^>]*>',
        r'<\s*/\s*([a-zA-Z][a-zA-Z0-9]*)\s*>',
        r'<!DOCTYPE',
        r'<!doctype'
    ]
    for pattern in html_indicators:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def _clean_html_impl(content: str,
                     remove_all_scripts: bool = False,
                     remove_external_scripts: bool = True,
                     analyze_inline_js: bool = True,
                     preserve_safe_styles: bool = True,
                     force_html_mode: bool = False) -> str:
    if not content or not isinstance(content, str):
        logger.warning("输入内容为空或类型错误")
        return ""
    if not force_html_mode and not _is_html_content(content):
        return content
    try:
        sanitizer = WebSanitizer(content)
        sanitized_html = sanitizer.sanitize()
        soup = BeautifulSoup(sanitized_html, 'html.parser')
        for script in soup.find_all('script'):
            should_remove = False
            if script.get('src'):
                if remove_external_scripts:
                    logger.info(f"移除外部脚本: {script.get('src')}")
                    should_remove = True
                else:
                    src = script.get('src', '').lower()
                    if any(src.startswith(scheme) for scheme in ['javascript:', 'data:', 'vbscript:']):
                        logger.warning(f"移除危险外部脚本: {script.get('src')}")
                        should_remove = True
            if analyze_inline_js and script.string and not should_remove:
                analyzer = JSSafeAnalyzer(script.string)
                if analyzer.analyze():
                    logger.warning(f"检测到危险 JavaScript: {analyzer.found_issues}")
                    should_remove = True
            if remove_all_scripts or should_remove:
                script.decompose()
        for style in soup.find_all('style'):
            if style.string:
                if preserve_safe_styles:
                    cleaned_css = sanitizer.clean_style_tag_content(style.string)
                    if cleaned_css and cleaned_css.strip():
                        style.string = cleaned_css
                    else:
                        style.decompose()
                else:
                    style_lower = style.string.lower()
                    has_danger = any(
                        re.search(pattern, style_lower, re.IGNORECASE)
                        for pattern in sanitizer.dangerous_css_patterns
                    )
                    if has_danger:
                        logger.warning("检测到危险 CSS 模式，移除 style 标签")
                        style.decompose()
        return str(soup)
    except Exception as e:
        logger.error(f"内容分析失败: {str(e)}", exc_info=True)
        return ""


class HtmlAnalyzeService:
    _instance: "HtmlAnalyzeService | None" = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    async def initialize(self) -> None:
        pass

    async def cleanup(self) -> None:
        pass

    def extract_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text().strip()

    def clean_html(self, html: str) -> str:
        return _clean_html_impl(html)

    def extract_resource_links(self, html: str) -> list[str]:
        return _collect_resource_links(html)


html_analyze_service = HtmlAnalyzeService()
