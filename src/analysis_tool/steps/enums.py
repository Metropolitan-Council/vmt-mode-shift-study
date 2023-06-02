from enum import Enum

class Mode(str, Enum):
    CAR = "car"
    WALK = "walk"
    BIKE = "bike"
    TRANSIT = "transit"
    
    def __str__(self) -> str:
        return self.value
    
class CutoffMode(str, Enum):
    PCT = "Percentile"
    RAW = "Raw"
    
    def __str__(self) -> str:
        return self.value