from enum import Enum

class ActionNodeTypeEnum(str, Enum):
    CONSTRUCTOR = "construct"
    CRAWLER = "crawler"
    STORAGE = "storage"
    MIDDLEWARE = "middleware"
    PROCESSOR = "processor"
    LOGIC = "logic"
    SIMPLE_OPERATION = "simple_operation"
    OUTPUT = "output"
    INPUT = "input"