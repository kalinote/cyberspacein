from langchain.tools import tool
from datetime import datetime, timezone

@tool(parse_docstring=True)
def get_current_time(time_zone: str = "Asia/Shanghai") -> str:
    """
    获取当前时间，时区默认东八区。时间格式为：YYYY-MM-DD HH:MM:SS 时区
    
    Args:
        time_zone: 时区，默认东八区
    Returns:
        str: 当前时间，格式为：YYYY-MM-DD HH:MM:SS 时区
    """
    return datetime.now(timezone(time_zone)).strftime("%Y-%m-%d %H:%M:%S") + " " + time_zone
