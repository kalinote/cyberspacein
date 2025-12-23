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
field = base_component.get_config("field")

if not field:
    base_component.fail("配置数据中未找到必需的field字段")

base_component.finish({
    "data_out": base_component.get_config(field)
})
