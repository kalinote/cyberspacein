import logging
from csi_base_component_sdk import ComponentContext, ComponentFailure

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [LAUNCHER] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("str_list_constructor")

def run(ctx: ComponentContext) -> dict:
    field = ctx.get_config("field")
    if not field:
        raise ComponentFailure("配置数据中未找到必需的field字段")
    return {field: ctx.get_config(field)}
