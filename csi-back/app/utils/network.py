import socket
import logging
import platform
import subprocess
import httpx

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    """
    获取本机局域网 IP 地址（非 127.0.0.1 和 0.0.0.0）
    返回第一个非回环的网络接口 IP
    不进行任何网络连接，仅通过本地方法获取
    """
    try:
        hostname = socket.gethostname()
        ip_list = socket.gethostbyname_ex(hostname)[2]
        
        for ip in ip_list:
            if ip and ip != "127.0.0.1" and not ip.startswith("169.254"):
                return ip
        
        if platform.system() == "Windows":
            try:
                result = subprocess.run(
                    ["ipconfig"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "IPv4" in line or "IP Address" in line:
                        ip = line.split(":")[-1].strip()
                        if ip and ip != "127.0.0.1" and not ip.startswith("169.254"):
                            return ip
            except Exception:
                pass
        else:
            try:
                result = subprocess.run(
                    ["hostname", "-I"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                ips = result.stdout.strip().split()
                for ip in ips:
                    if ip and ip != "127.0.0.1" and not ip.startswith("169.254"):
                        return ip
            except Exception:
                pass
        
        logger.warning("无法获取局域网 IP，返回 127.0.0.1")
        return "127.0.0.1"
    except Exception as e:
        logger.error(f"获取本机 IP 失败: {e}")
        return "127.0.0.1"


def log_http_error_response(response: httpx.Response):
    request = response.request
    if response.status_code >= 400:
        try:
            response.read()
            error_body = response.text
            
            logger.error(
                f"HTTP请求失败 - 方法: {request.method} URL: {request.url} "
                f"状态码: {response.status_code} 响应体: {error_body}"
            )
        except Exception as e:
            logger.error(
                f"HTTP请求失败 - 方法: {request.method} URL: {request.url} "
                f"状态码: {response.status_code} 响应体解析失败: {e}"
            )


async def log_http_error_response_async(response: httpx.Response):
    request = response.request
    if response.status_code >= 400:
        try:
            await response.aread()
            error_body = response.text
            
            logger.error(
                f"HTTP请求失败 - 方法: {request.method} URL: {request.url} "
                f"状态码: {response.status_code} 响应体: {error_body}"
            )
        except Exception as e:
            logger.error(
                f"HTTP请求失败 - 方法: {request.method} URL: {request.url} "
                f"状态码: {response.status_code} 响应体解析失败: {e}"
            )

