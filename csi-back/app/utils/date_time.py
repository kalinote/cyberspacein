from datetime import datetime

def parse_datetime(value):
    """解析日期时间字段"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            try:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
            except:
                return None
    return None