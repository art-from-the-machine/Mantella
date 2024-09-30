import json


class ToolsManager:
    def __init__(self):
        self.__tools = {}
        self.__tooltips = {}  


    def build_GPT_function(self,GPT_func_name: str, GPT_func_description: str, GPT_func_parameters: dict, GPT_required: list = None, additionalProperties: bool = False, strict: bool = True, parallel_tool_calls: bool = False):
        """
        Builds a GPT function template with additional parameters for strict mode and parallel tool calls.

        Args:
            GPT_func_name (str): The name of the function.
            GPT_func_description (str): A brief description of the function's purpose.
            GPT_func_parameters (dict): The parameters for the function in the form of a dictionary.
            additionalProperties (bool): Whether additional properties are allowed in the parameters (default is False).
            strict (bool): Whether the function should operate in strict mode (default is False).
            parallel_tool_calls (bool): Whether parallel tool calls are allowed (default is False).

        Returns:
            dict: A dictionary representing the GPT function template.
        """
        if GPT_required is None:
            GPT_required = list(GPT_func_parameters.keys())  # Default to all parameters if 'required' is not provided

        return {
            "type": "function",
            "function": {
                "name": GPT_func_name,
                "description": GPT_func_description,
                "parameters": {
                    "type": "object",
                    "properties": GPT_func_parameters,
                    "required": GPT_required,
                    "additionalProperties": additionalProperties
                },
                "strict": strict,
                "parallel_tool_calls": parallel_tool_calls
            }
        }

    def add_function(self, function_name: str, function_template: dict):
        """
        Manually add a function template to the tools storage.

        Args:
            function_name (str): The name of the function (key for the tools dictionary).
            function_template (dict): The function template to store.
        """
        self.__tools[function_name] = function_template

    def build_dictionary(self,pairs: list[tuple[str, str]]) -> dict:
        """
        Builds a dictionary with multiple customizable names and definitions.

        Args:
            pairs (list of tuples): A list of tuples where each tuple contains a name (key) and a definition (value).

        Returns:
            dict: A dictionary built from the provided name-definition pairs.
        """
        return {name: definition for name, definition in pairs}
    
    def build_nested_dict(self,pairs: list[tuple]) -> dict:
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
    
    def get_function(self, GPT_func_name: str) -> dict:
        """
        Retrieves a function by its name from the tools storage.

        Args:
            GPT_func_name (str): The name of the function.

        Returns:
            dict: The function template, or None if the function does not exist.
        """
        return self.__tools.get(GPT_func_name, None)

    def list_functions_names(self) -> list:
        """
        Lists all the function names stored in the tools manager.

        Returns:
            list: A list of all function names.
        """
        return list(self.__tools.keys())
    
    def list_all_functions(self) -> list:
        """
        Returns an array of all function templates stored in the tools manager.

        Returns:
            list: A list of all function templates as dictionaries.
        """
        return list(self.__tools.values())
    
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
                
# Assuming the ToolsManager class and build_dictionary function are already defined
'''
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

# Build the function using build_GPT_function
move_character_function = manager.build_GPT_function(
    GPT_func_name="move_character_near_npc",
    GPT_func_description="Determine where to move a character closest to a specific NPC, such as 'the rabbit closest to me'.",
    GPT_func_parameters=function_parameters,
    GPT_required=["npc_names", "distances", "npc_ids"],  # Required fields
    additionalProperties=False,
    strict=True,
    parallel_tool_calls=False
)

# Manually add the function to the ToolsManager
manager.add_function("move_character_near_npc", move_character_function)

# You can now retrieve and print the function, or list it
print(manager.get_function("move_character_near_npc"))
'''