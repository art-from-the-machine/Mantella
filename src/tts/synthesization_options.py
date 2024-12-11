class SynthesizationOptions:
    """Options and additional information that can affect the synthesization of a voice line
    """
    def __init__(self, aggro: bool, is_first_line_of_response: bool) -> None:
        self.__aggro = aggro
        self.__is_first_line_of_response = is_first_line_of_response
    
    @property
    def aggro(self) -> bool:
        """Is the NPC saying this angry/in combat right now?
        """
        return self.__aggro
    
    @property
    def is_first_line_of_response(self) -> bool:
        """Is this the first spoken voiceline of the given response?
        """
        return self.__is_first_line_of_response