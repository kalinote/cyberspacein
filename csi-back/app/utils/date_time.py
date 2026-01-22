from datetime import datetime

def parse_datetime(value):
    """解析日期时间字段，返回格式为 2026-01-19T23:56:46 的datetime对象"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return dt.replace(microsecond=0)
        except:
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            except:
                return None
    return None