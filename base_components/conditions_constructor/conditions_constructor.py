from csi_base_component_sdk.sync import BaseComponent
import logging

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def parse_conditions(conditions):
    OPERATOR_MAP = {
        "=": "eq",
        "__ne": "ne",
        "__gt": "gt",
        "__gte": "gte",
        "__lt": "lt",
        "__lte": "lte",
        "__contains": "contains",
        "__icontains": "icontains",
        "__in": "in",
        "__startswith": "startswith",
        "__endswith": "endswith"
    }
    
    def _convert_value(value_str):
        """将字符串值转换为合适的类型（int/float/str）"""
        value_str = value_str.strip()
        try:
            if '.' in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            return value_str
    
    def _parse_condition(condition):
        """解析单个条件字符串"""
        if '=' not in condition:
            raise ValueError(f"无效的条件格式: {condition}")
        
        parts = condition.split('=', 1)
        field_part = parts[0]
        value_str = parts[1]
        
        operator = "eq"
        field = field_part
        
        for op_key, op_value in OPERATOR_MAP.items():
            if field_part.endswith(op_key):
                operator = op_value
                field = field_part[:-len(op_key)]
                break
        
        values = [v.strip() for v in value_str.split(',')]
        converted_values = [_convert_value(v) for v in values]
        
        if len(converted_values) == 1:
            return {
                "field": field,
                "op": operator,
                "value": converted_values[0]
            }
        else:
            return {
                "$or": [
                    {
                        "field": field,
                        "op": operator,
                        "value": v
                    }
                    for v in converted_values
                ]
            }
    
    result = []
    for condition in conditions:
        parsed = _parse_condition(condition)
        result.append(parsed)
    
    return {"$and": result}

if __name__ == "__main__":
    base_component = BaseComponent()
    base_component.initialize()

    conditions = base_component.get_config("conditions")
    if conditions:
        result = parse_conditions(conditions)
    else:
        base_component.fail("未获取到条件")

    base_component.finish({
        "conditions": result
    })