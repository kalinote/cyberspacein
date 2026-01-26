from analyzer.base import BaseAnalyzer
import esprima
import bleach
from bleach.css_sanitizer import CSSSanitizer
from bs4 import BeautifulSoup
from typing import Set
import logging
import re

logger = logging.getLogger(__name__)


class JSSafeAnalyzer:
    """基于 AST 的 JavaScript 安全分析器"""
    
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
        """递归遍历 AST 节点"""
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
        """检查函数调用是否危险"""
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
    """HTML 内容安全清理器"""
    
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
        """自定义属性过滤器"""
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
        """检查CSS内容是否安全"""
        if not css_content:
            return True
        
        css_lower = css_content.lower()
        for pattern in self.dangerous_css_patterns:
            if re.search(pattern, css_lower, re.IGNORECASE):
                logger.warning(f"检测到危险CSS模式: {pattern}")
                return False
        
        return True
    
    def clean_style_tag_content(self, css_content: str) -> str:
        """清理style标签内的CSS内容"""
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
        """执行 HTML 清理"""
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


class SafeRawContentAnalyzer(BaseAnalyzer):
    """安全原始内容分析器 - 清理并分析 HTML/JavaScript"""
    
    @staticmethod
    def _is_html_content(content: str) -> bool:
        """检测内容是否为HTML"""
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
    
    @staticmethod
    def analyze(content: str, 
                remove_all_scripts: bool = False,
                remove_external_scripts: bool = True,
                analyze_inline_js: bool = True,
                preserve_safe_styles: bool = True,
                force_html_mode: bool = False,
                enable_media_localization: bool = False,
                base_url: str | None = None,
                download_size_limit: int | None = None) -> str:
        """
        分析并清理 HTML 内容
        
        Args:
            content: 待清理的内容（HTML或纯文本）
            remove_all_scripts: 是否移除所有脚本标签（默认False，只移除危险脚本）
            remove_external_scripts: 是否移除外部脚本引用（默认True）
            analyze_inline_js: 是否分析内联 JavaScript（默认True）
            preserve_safe_styles: 是否保留安全的样式内容（默认True）
            force_html_mode: 强制按HTML处理，即使检测不到HTML标签（默认False）
            enable_media_localization: 是否启用媒体资源本地化（默认False）
            base_url: 基础URL，用于解析相对路径（可选）
            download_size_limit: 下载文件大小限制（字节），超过此大小将跳过下载（可选）
            
        Returns:
            清理后的安全内容
        """
        if not content or not isinstance(content, str):
            logger.warning("输入内容为空或类型错误")
            return ""
        
        if not force_html_mode and not SafeRawContentAnalyzer._is_html_content(content):
            # logger.info("非HTML内容，无需处理")
            return content
        
        try:
            sanitizer = WebSanitizer(content)
            sanitized_html = sanitizer.sanitize()
            
            soup = BeautifulSoup(sanitized_html, 'html.parser')
            
            scripts_removed = 0
            scripts_kept = 0
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
                    scripts_removed += 1
                else:
                    scripts_kept += 1
            
            if scripts_removed > 0 or scripts_kept > 0:
                logger.info(f"脚本处理: 移除 {scripts_removed} 个, 保留 {scripts_kept} 个")
            
            styles_cleaned = 0
            styles_removed = 0
            for style in soup.find_all('style'):
                if style.string:
                    if preserve_safe_styles:
                        cleaned_css = sanitizer.clean_style_tag_content(style.string)
                        if cleaned_css and cleaned_css.strip():
                            style.string = cleaned_css
                            styles_cleaned += 1
                        else:
                            style.decompose()
                            styles_removed += 1
                    else:
                        style_lower = style.string.lower()
                        has_danger = False
                        for pattern in sanitizer.dangerous_css_patterns:
                            if re.search(pattern, style_lower, re.IGNORECASE):
                                has_danger = True
                                break
                        
                        if has_danger:
                            logger.warning(f"检测到危险 CSS 模式，移除 style 标签")
                            style.decompose()
                            styles_removed += 1
            
            if styles_cleaned > 0 or styles_removed > 0:
                logger.info(f"样式处理: 清理 {styles_cleaned} 个, 移除 {styles_removed} 个")
            
            result = str(soup)
            
            if enable_media_localization:
                try:
                    from analyzer.media_localizer import MediaLocalizer
                    localizer = MediaLocalizer(base_url=base_url, download_size_limit=download_size_limit)
                    result = localizer.localize(result)
                except Exception as e:
                    logger.error(f"媒体本地化失败: {e}", exc_info=True)
            
            reduction_percent = round((1 - len(result) / len(content)) * 100, 1) if len(content) > 0 else 0
            # logger.info(f"内容清理完成 - 原始: {len(content)} 字节, 清理后: {len(result)} 字节, 减少: {reduction_percent}%")
            return result
            
        except Exception as e:
            logger.error(f"内容分析失败: {str(e)}", exc_info=True)
            return ""