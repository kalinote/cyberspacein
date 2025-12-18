from enum import Enum

class ActionNodeTypeEnum(str, Enum):
    INPUT = "input"
    OUTPUT = "output"
    CRAWLER = "crawler"