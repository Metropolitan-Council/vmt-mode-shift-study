from enum import Enum

class Mode(str, Enum):
    CAR = "car"
    WALK = "walk"
    BIKE = "bike"
    TRANSIT = "transit"
    
    def __str__(self) -> str:
        return self.value
    
    @staticmethod
    def get_all() -> list:
        return (Mode.CAR, Mode.WALK, Mode.BIKE, Mode.TRANSIT)
    
class CutoffMode(str, Enum):
    PCT = "Percentile"
    RAW = "Raw"
    
    def __str__(self) -> str:
        return self.value
    
class Phase(str, Enum):
    FEASIBLE = "feasible"
    PROBABLE = "probable"
    
    def __str__(self) -> str:
        return self.value