import json
from src.function_inference.llm_function_class import LLMFunction, LLMOpenAIfunction, ContextPayload, LLMFunctionCondition
from src.function_inference.llm_tooltip_class import TargetInfo, Tooltip, ModeInfo
from src.conversation.context import context

class ToolsManager:
    def __init__(self):
        self.__tools = {}
        self.__tooltips = {}
        self.__conditions = {}
        self.__custom_tooltips = {}  

    ######################### LLM Function management ###################################

    def add_function(self, llm_function: LLMFunction):
        """
        Adds an LLMFunction instance to the tools storage.

        Args:
            llm_function (LLMFunction): The LLMFunction instance to store.
        """
        self.__tools[llm_function.GPT_func_name] = llm_function

    def get_function_object(self, GPT_func_name: str) -> LLMFunction:
        """
        Retrieves a function by its name from the tools storage.

        Args:
            GPT_func_name (str): The name of the function.

        Returns:
            LLMFunction: The LLMFunction instance, or None if it does not exist.
        """
        return self.__tools.get(GPT_func_name, None)

    def get_function(self, GPT_func_name: str) -> dict:
        """
        Retrieves a formatted function by its name from the tools storage.

        Args:
            GPT_func_name (str): The name of the function.

        Returns:
            dict: The formatted function template, or None if the function does not exist.
        """
        llm_function:LLMFunction = self.__tools.get(GPT_func_name, None)
        if llm_function:
            return llm_function.get_formatted_LLMFunction()
        return None

    def list_functions_names(self) -> list:
        """
        Lists all the function names stored in the tools manager.

        Returns:
            list: A list of all function names.
        """
        return list(self.__tools.keys())

    def list_all_functions(self) -> list:
        """
        Returns an array of all formatted function templates stored in the tools manager.

        Returns:
            list: A list of all function templates as dictionaries.
        """
        return [func.get_formatted_LLMFunction() for func in self.__tools.values()]
    
    def get_all_functions(self) -> list:
        """
        Returns a list of all function objects stored in the tools manager.

        Returns:
            list: A list of all function objects (LLMFunction instances).
        """
        return list(self.__tools.values())

    def clear_all_functions(self):
        """
        Clears all function templates from the tools storage.
        """
        self.__tools.clear()
        print("All function templates have been cleared.")

    def build_dictionary(self, pairs: list[tuple[str, str]]) -> dict:
        """
        Builds a dictionary with multiple customizable names and definitions.

        Args:
            pairs (list of tuples): A list of tuples where each tuple contains a name (key) and a definition (value).

        Returns:
            dict: A dictionary built from the provided name-definition pairs.
        """
        return {name: definition for name, definition in pairs}

    def build_nested_dict(self, pairs: list[tuple]) -> dict:
        """
        Builds a nested dictionary from a list of tuples.

        Args:
            pairs (list of tuples): A list where each tuple represents a path of keys and a final value.
                                    Each tuple's format should be (key1, key2, ..., keyN, value).

        Returns:
            dict: A nested dictionary built from the provided key-value pairs.
        """
        nested_dict = {}
        for path in pairs:
            # Traverse through the tuple to build the nested structure
            current_level = nested_dict
            *keys, value = path

            for key in keys:
                # Create a new nested dictionary if the key doesn't exist
                if key not in current_level:
                    current_level[key] = {}
                current_level = current_level[key]
            # Set the final value at the deepest level
            current_level[keys[-1]] = value

        return nested_dict

    def format_with_multiple_arrays(self, intro_text: str, array_descriptions: list[tuple[str, list]], outro_text: str) -> str:
        """
        Builds a formatted string with multiple JSON arrays based on the provided descriptions.

        Args:
            intro_text (str): The introductory text.
            array_descriptions (list of tuples): Each tuple contains a description string and an array of values.
            outro_text (str): The concluding text.

        Returns:
            str: A formatted multi-part string containing all arrays and descriptions.
        """
        formatted_sections = [intro_text]
        for description, items in array_descriptions:
            json_array = json.dumps(items)
            formatted_sections.append(f'{description} {json_array}')
        formatted_sections.append(outro_text)
        return "\n".join(formatted_sections)

    ######################### Tooltip management ###################################

    def add_tooltip(self, tooltip_name: str, formatted_tooltip: str):
        """
        Stores a pre-formatted tooltip.

        Args:
            tooltip_name (str): The name of the tooltip for future reference.
            formatted_tooltip (str): The pre-formatted tooltip string.
        """
        self.__tooltips[tooltip_name] = formatted_tooltip

    def get_tooltip(self, tooltip_name: str) -> str:
        """
        Retrieves a tooltip by its name.

        Args:
            tooltip_name (str): The name of the tooltip to retrieve.

        Returns:
            str: The tooltip string, or None if the tooltip does not exist.
        """
        return self.__tooltips.get(tooltip_name, None)

    def list_tooltips(self) -> list:
        """
        Lists all the tooltip names stored in the manager.

        Returns:
            list: A list of all tooltip names.
        """
        return list(self.__tooltips.keys())

    def list_all_tooltips(self) -> list:
        """
        Lists all tooltips stored in the manager.

        Returns:
            list: A list of all tooltips as strings.
        """
        return list(self.__tooltips.values())

    def clear_all_tooltips(self):
        """
        Clears all tooltips from the manager.
        """
        self.__tooltips.clear()
        print("All tooltips have been cleared.")

    ######################### Context payload management ###################################

    def clear_all_context_payloads(self):
        """
        Iterates over all LLMFunction instances in the manager
        and clears their context_payload lists.
        """
        for llm_function in self.__tools.values():
            # Access the context_payload (a list) via the property
            llm_function:LLMFunction
            llm_function.context_payload=None
            llm_function.context_payload = ContextPayload()
        print("All context_payloads have been cleared for every stored LLMFunction.")


    ######################### Condition management ###################################

    def add_condition(self, condition: LLMFunctionCondition):
        """
        Adds an LLMFunctionCondition instance to the conditions storage.

        Args:
            condition (LLMFunctionCondition): The LLMFunctionCondition instance to store.
        """
        self.__conditions[condition.condition_name] = condition

    def evaluate_condition(self, condition_name: str, conversation_context: context) -> bool:
        """
        Evaluates a stored condition against the given conversation context.

        Args:
            condition_name (str): The name of the condition to evaluate.
            conversation_context (context): The conversation context to use in evaluation.

        Returns:
            bool: The result of the condition evaluation, or False if the condition does not exist.
        """
        condition: LLMFunctionCondition = self.__conditions.get(condition_name, None)
        if condition:
            return condition.evaluate(conversation_context)
        print(f"Condition {condition_name} doesn't exist in tool_manager")
        return None
    
    def get_all_conditions(self) -> list:
        """
        Returns a list of all LLMFunctionCondition objects stored in the tools manager.

        Returns:
            list: A list of all condition objects (LLMFunctionCondition instances).
        """
        return list(self.__conditions.values())

    ######################### Custom tooltip management ###################################

    def add_custom_tooltip(self, tooltip_obj: Tooltip):
        """
        Stores a custom Tooltip object for later retrieval.

        Args:
            tooltip_obj (Tooltip): The Tooltip object to store.
        """
        tooltip_name = tooltip_obj.get_tooltip_name()
        self.__custom_tooltips[tooltip_name] = tooltip_obj

    def get_custom_tooltip(self, tooltip_name: str) -> Tooltip:
        """
        Retrieves a stored custom Tooltip object by its name.

        Args:
            tooltip_name (str): The name of the custom tooltip to retrieve.

        Returns:
            Tooltip: The stored Tooltip object, or None if not found.
        """
        return self.__custom_tooltips.get(tooltip_name, None)