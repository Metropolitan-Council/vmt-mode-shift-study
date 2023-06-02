from enum import Enum

class Mode(str, Enum):
    CAR = "car"
    WALK = "walk"
    BIKE = "bike"
    TRANSIT = "transit"
    
    def __str__(self) -> str:
        return self.value
    
    def get_all(self) -> list:
        return (Mode.CAR, Mode.WALK, Mode.BIKE, Mode.TRANSIT)
    
class CutoffMode(str, Enum):
    PCT = "Percentile"
    RAW = "Raw"
    
    def __str__(self) -> str:
        return self.value