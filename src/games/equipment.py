class EquipmentItem:
    def __init__(self, name: str) -> None:
        self.__name = name
    
    @property
    def name (self) -> str:
        return self.__name

class Equipment:
    BODY = "body"
    HEAD = "head"
    HANDS = "hands"
    FEET = "feet"
    AMULET = "amulet"
    RIGHTHAND = "righthand"
    LEFTHAND = "lefthand"
    DESCRIPTION_ORDER_ARMOR: list[str] = [BODY, HEAD, HANDS, FEET, AMULET]

    def __init__(self, slots_to_items: dict[str, EquipmentItem]) -> None:
        self.__slots_to_items = slots_to_items

    def get_item(self, slot: str) -> EquipmentItem | None:
        if self.__slots_to_items.__contains__(slot):
            return self.__slots_to_items[slot]
        
    def get_equipment_description(self, character_name: str) -> str:        
        worn_armor_items: list[str] = []
        for slot in self.DESCRIPTION_ORDER_ARMOR:
            item = self.get_item(slot)
            if item:
                worn_armor_items.append(item.name)
        armor_text = self.format_listing(worn_armor_items)
        # if armor_text == "":
        #     armor_text = "nothing"
        used_weapon_items: list[str] = []
        for slot in [self.RIGHTHAND, self.LEFTHAND]:
            item = self.get_item(slot)
            if item:
                used_weapon_items.append(item.name)
        weapons_text = self.format_listing(used_weapon_items)
        if weapons_text == "" and armor_text == "":
            return ""
        elif weapons_text == "":
            return f"wears {armor_text}."
        elif armor_text == "":
            return f"uses {weapons_text}."
        else:
            return f"wears {armor_text} and uses {weapons_text}."

    @staticmethod
    def format_listing(listing: list[str]) -> str:
        """Returns a list of string concatenated by ',' and 'and' to be used in a text

        Args:
            listing (list[str]): the list of strings

        Returns:
            str: A natural language listing. Returns an empty string if listing is empty, returns the the string if length of listing is 1
        """
        if len(listing) == 0:
            return ""
        elif len(listing) == 1:
            return listing[0]
        else:
            return ', '.join(listing[:-1]) + ' and ' + listing[-1]          

