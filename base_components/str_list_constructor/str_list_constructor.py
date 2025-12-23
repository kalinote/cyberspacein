import logging
from csi_base_component_sdk.sync import BaseComponent

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [LAUNCHER] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("str_list_constructor")

base_component = BaseComponent()

base_component.initialize()
fields = base_component.get_config("fields")

if not fields:
    logger.error("配置数据中未找到必需的fields字段")
    base_component.fail("配置数据中未找到必需的fields字段")
    
data_out = []
for field in fields:
    data_out += base_component.get_config(field)

base_component.finish({
    "data_out": data_out
})
