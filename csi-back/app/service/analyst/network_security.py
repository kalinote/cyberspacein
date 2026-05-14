"""网络安全工具：SSRF 防护与内部 URL 检测。"""

from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlparse

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # unique local
    ipaddress.ip_network("fe80::/10"),  # link-local v6
]

_URL_RE = re.compile(r"https?://[^\s\"'`;|<>]+", re.IGNORECASE)

_allowed_networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []


def configure_ssrf_whitelist(cidrs: list[str]) -> None:
    """允许特定 CIDR 绕过 SSRF 阻断（例如 Tailscale 的 100.64.0.0/10）。"""
    global _allowed_networks
    nets = []
    for cidr in cidrs:
        try:
            nets.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            pass
    _allowed_networks = nets


def _is_private(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if _allowed_networks and any(addr in net for net in _allowed_networks):
        return False
    return any(addr in net for net in _BLOCKED_NETWORKS)


def validate_url_target(url: str) -> tuple[bool, str]:
    """校验 URL 是否可安全访问：协议、域名、解析 IP 是否落入内网段。

    返回 (ok, error_message)。ok=True 时 error_message 为空字符串。
    """
    try:
        p = urlparse(url)
    except Exception as e:
        return False, str(e)

    if p.scheme not in ("http", "https"):
        return False, f"仅允许 http/https，当前为 '{p.scheme or 'none'}'"
    if not p.netloc:
        return False, "缺少域名"

    hostname = p.hostname
    if not hostname:
        return False, "缺少主机名"

    try:
        infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except socket.gaierror:
        return False, f"无法解析域名: {hostname}"

    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if _is_private(addr):
            return False, f"已阻止：{hostname} 解析到内网/保留地址 {addr}"

    return True, ""


def validate_resolved_url(url: str) -> tuple[bool, str]:
    """校验已访问后的最终 URL（常见于重定向）。优先检查字面 IP，必要时再解析域名。"""
    try:
        p = urlparse(url)
    except Exception:
        return True, ""

    hostname = p.hostname
    if not hostname:
        return True, ""

    try:
        addr = ipaddress.ip_address(hostname)
        if _is_private(addr):
            return False, f"重定向目标为内网/保留地址: {addr}"
    except ValueError:
        try:
            infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        except socket.gaierror:
            return True, ""
        for info in infos:
            try:
                addr = ipaddress.ip_address(info[4][0])
            except ValueError:
                continue
            if _is_private(addr):
                return False, f"重定向目标 {hostname} 解析到内网/保留地址 {addr}"

    return True, ""


def contains_internal_url(command: str) -> bool:
    """命令字符串中包含指向内网/保留地址的 URL 时返回 True。"""
    for m in _URL_RE.finditer(command):
        url = m.group(0)
        ok, _ = validate_url_target(url)
        if not ok:
            return True
    return False

