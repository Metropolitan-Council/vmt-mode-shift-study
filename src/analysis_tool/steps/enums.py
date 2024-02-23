from enum import Enum

class Mode(str, Enum):
    """
    This is the enum for mode. Each of these are essentially a string and can be used as such.
    """
    CAR = "car"
    WALK = "walk"
    BIKE = "bike"
    TRANSIT = "transit"
    
    def __str__(self) -> str:
        """
        This function is useful for implicitly converting these enums to strings in an f-string.

        Returns:
            str: string equivalency of the enum
        """
        return self.value
    
    @staticmethod 
    def get_all() -> list:
        """
        This returns a tuple of all possible values this enum takes on

        Returns:
            tuple: all possible values this enum can take on
        """
        return (Mode.CAR, Mode.WALK, Mode.BIKE, Mode.TRANSIT)
    
class CutoffMode(str, Enum):
    """
    This is the enum for CutoffMode. Each of these are essentially a string and can be used as such.
    """
    PCT = "Percentile"
    RAW = "Raw"
    
    def __str__(self) -> str:
        """
        This function is useful for implicitly converting these enums to strings in an f-string.

        Returns:
            str: string equivalency of the enum
        """
        return self.value
    
class Phase(str, Enum):
    """
    This is the enum for Phase (feasible or probable). Each of these are essentially a string and can be used as such.
    """
    FEASIBLE = "feasible"
    PROBABLE = "probable"
    
    def __str__(self) -> str:
        """
        This function is useful for implicitly converting these enums to strings in an f-string.

        Returns:
            str: string equivalency of the enum
        """
        return self.value