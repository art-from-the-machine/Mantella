class SynthesizationOptions:
    """Options and additional information that can affect the synthesization of a voice line
    """
    def __init__(self, aggro: bool, is_first_line_of_response: bool, stream_first_line: bool = False) -> None:
        self.__aggro = aggro
        self.__is_first_line_of_response = is_first_line_of_response
        self.__stream_first_line = stream_first_line

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

    @property
    def stream_first_line(self) -> bool:
        """Should this voiceline be streamed from the TTS server and played externally as it arrives (if the service supports streaming)?
        """
        return self.__stream_first_line
