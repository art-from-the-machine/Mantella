class SynthesizationOptions:
    """Options and additional information that can affect the synthesization of a voice line
    """
    def __init__(self, aggro: bool) -> None:
        self.__aggro = aggro
    
    @property
    def aggro(self) -> bool:
        """Is the NPC saying this angry/in combat right now?
        """
        return self.__aggro