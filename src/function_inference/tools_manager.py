import json
from src.function_inference.LLMFunction_class import LLMFunction,LLMOpenAIfunction

class ToolsManager:
    def __init__(self):
        self.__tools = {}
        self.__tooltips = {}

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
            dict: The formatted function template, or None if the function does not exist.
        """
        llm_function:LLMFunction = self.__tools.get(GPT_func_name, None)
        if llm_function:
            return llm_function
        return None

    def get_function(self, GPT_func_name: str) -> dict:
        """
        Retrieves a function by its name from the tools storage.

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
            list: A list of all function objects.
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
            json_array = json.dumps(items)  # Convert list to JSON formatted string
            formatted_sections.append(f'{description} {json_array}')
        formatted_sections.append(outro_text)
        return "\n".join(formatted_sections)

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


# Example usage of the updated ToolsManager and LLMFunction classes

# Initialize the ToolsManager
manager = ToolsManager()

# Define the parameters using build_dictionary to make it cleaner
function_parameters = manager.build_dictionary([
    ("npc_names", {
        "type": "array",
        "description": "A list of names of nearby NPCs.",
        "items": {"type": "string"}
    }),
    ("distances", {
        "type": "array",
        "description": "A list of distances to each NPC, corresponding to npc_names.",
        "items": {"type": "number"}
    }),
    ("npc_ids", {
        "type": "array",
        "description": "A list of unique IDs for each NPC, corresponding to npc_names.",
        "items": {"type": "string"}
    })
])
'''
# Build the function using the LLMFunction class
move_character_function = LLMFunction(
    GPT_func_name="move_character_near_npc",
    GPT_func_description="Determine where to move a character closest to a specific NPC, such as 'the rabbit closest to me'.",
    function_parameters=function_parameters,
    GPT_required=["npc_names", "distances", "npc_ids"],  # Required fields
    is_generic_npc_function=False,
    is_follower_function=False,
    is_settler_function=False
)

# Add the function to the ToolsManager
manager.add_function(move_character_function)

# Retrieve and print the function
formatted_function = manager.get_function("move_character_near_npc")
print(json.dumps(formatted_function, indent=4))

# List all function names
print("Function names:", manager.list_functions_names())

# List all formatted functions
all_functions = manager.list_all_functions()
print("All functions:")
for func in all_functions:
    print(json.dumps(func, indent=4))
'''