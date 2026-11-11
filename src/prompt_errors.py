class PromptSectionError(Exception):
    """A prompt cannot be built: a variable it uses is not allowed, or a shared section cannot be expanded. The LLM call is refused"""

    def __init__(self, variable: str):
        self.variable = variable
        super().__init__(f"Refusing LLM call. Broken prompt variable '{{{variable}}}'.")


class PromptConditionError(PromptSectionError):
    """A prompt's conditional blocks ({if ...}, {else}, {end if}) are broken. A PromptSectionError, so every place that refuses
    the LLM call for a broken prompt also refuses it for this

    Args:
        problem (str): what is wrong, in plain words, as shown in the prompt editor
    """

    def __init__(self, problem: str):
        self.variable = ""
        self.problem = problem
        Exception.__init__(self, f"Refusing LLM call. The prompt's conditional blocks are broken: {problem}")
