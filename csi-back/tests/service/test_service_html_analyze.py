"""app.service.html_analyze 资源链接与内容检测测试。"""

from app.service.html_analyze import (
    JSSafeAnalyzer,
    WebSanitizer,
    _collect_resource_links,
    _extract_css_urls,
    _extract_srcset_urls,
    _is_html_content,
    html_analyze_service,
)


def test_extract_srcset_urls():
    # srcset 中解析出 URL（含宽度描述符）
    urls = _extract_srcset_urls("a.png 1x, b.png 2x")
    assert "a.png" in urls
    assert "b.png" in urls


def test_extract_css_urls():
    # 从 style 中提取 url(...)
    urls = _extract_css_urls('background: url(https://ex.com/x.png) no-repeat')
    assert "https://ex.com/x.png" in urls


def test_collect_resource_links_from_img():
    # img src 被收集
    html = '<html><body><img src="https://cdn.example.com/a.jpg"/></body></html>'
    links = _collect_resource_links(html)
    assert "https://cdn.example.com/a.jpg" in links


def test_is_html_content_plain_text_false():
    # 纯文本不应识别为 HTML
    assert _is_html_content("hello world") is False


def test_is_html_content_tag_true():
    # 含标签则视为 HTML
    assert _is_html_content("<div>hi</div>") is True


def test_js_safe_analyzer_detects_eval():
    # 内联脚本含 eval 应判为恶意
    a = JSSafeAnalyzer("eval('1')")
    assert a.analyze() is True
    assert a.is_malicious is True


def test_web_sanitizer_blocks_javascript_href():
    # 危险协议链接在属性过滤中被拒绝（返回 False 表示不允许该属性值）
    s = WebSanitizer('<a href="javascript:alert(1)">x</a>')
    assert s._attribute_filter("a", "href", "javascript:alert(1)") is False


def test_html_analyze_service_extract_text():
    # 提取纯文本
    t = html_analyze_service.extract_text("<p>a<b>b</b></p>")
    assert "a" in t and "b" in t
