import os
import json
import logging
from typing import List

class TargetInfo:
    def __init__(self,
                 target_names: dict,
                 target_distances: dict,
                 target_ids: dict,
                 targeting_intro: str,
                 targeting_outro: str,
                 send_info_to_llm: bool = True):
        self._target_names = target_names
        self._target_distances = target_distances
        self._target_ids = target_ids
        self._targeting_intro = targeting_intro
        self._targeting_outro = targeting_outro
        self._send_info_to_llm = send_info_to_llm

    # ---------- Traditional getters and setters ----------

    def get_target_names(self) -> dict:
        return self._target_names

    def set_target_names(self, target_names: dict):
        self._target_names = target_names

    def get_target_distances(self) -> dict:
        return self._target_distances

    def set_target_distances(self, target_distances: dict):
        self._target_distances = target_distances

    def get_target_ids(self) -> dict:
        return self._target_ids

    def set_target_ids(self, target_ids: dict):
        self._target_ids = target_ids

    def get_targeting_intro(self) -> str:
        return self._targeting_intro

    def set_targeting_intro(self, targeting_intro: str):
        self._targeting_intro = targeting_intro

    def get_targeting_outro(self) -> str:
        return self._targeting_outro

    def set_targeting_outro(self, targeting_outro: str):
        self._targeting_outro = targeting_outro

    def get_send_info_to_llm(self) -> bool:
        return self._send_info_to_llm

    def set_send_info_to_llm(self, value: bool):
        self._send_info_to_llm = value

    # ---------- Pythonic properties ----------

    @property
    def target_names(self) -> dict:
        return self._target_names

    @target_names.setter
    def target_names(self, value: dict):
        self._target_names = value

    @property
    def target_distances(self) -> dict:
        return self._target_distances

    @target_distances.setter
    def target_distances(self, value: dict):
        self._target_distances = value

    @property
    def target_ids(self) -> dict:
        return self._target_ids

    @target_ids.setter
    def target_ids(self, value: dict):
        self._target_ids = value

    @property
    def targeting_intro(self) -> str:
        return self._targeting_intro

    @targeting_intro.setter
    def targeting_intro(self, value: str):
        self._targeting_intro = value

    @property
    def targeting_outro(self) -> str:
        return self._targeting_outro

    @targeting_outro.setter
    def targeting_outro(self, value: str):
        self._targeting_outro = value

    @property
    def send_info_to_llm(self) -> bool:
        return self._send_info_to_llm

    @send_info_to_llm.setter
    def send_info_to_llm(self, value: bool):
        self._send_info_to_llm = value


class ModeInfo:
    def __init__(self,
                 function_modes: dict,
                 modes_intro: str,
                 modes_outro: str,
                 send_info_to_llm: bool = True):
        self._function_modes = function_modes
        self._modes_intro = modes_intro
        self._modes_outro = modes_outro
        self._send_info_to_llm = send_info_to_llm

    # ---------- Traditional getters and setters ----------

    def get_function_modes(self) -> dict:
        return self._function_modes

    def set_function_modes(self, function_modes: dict):
        self._function_modes = function_modes

    def get_modes_intro(self) -> str:
        return self._modes_intro

    def set_modes_intro(self, modes_intro: str):
        self._modes_intro = modes_intro

    def get_modes_outro(self) -> str:
        return self._modes_outro

    def set_modes_outro(self, modes_outro: str):
        self._modes_outro = modes_outro

    def get_send_info_to_llm(self) -> bool:
        return self._send_info_to_llm

    def set_send_info_to_llm(self, value: bool):
        self._send_info_to_llm = value

    # ---------- Pythonic properties ----------

    @property
    def function_modes(self) -> dict:
        return self._function_modes

    @function_modes.setter
    def function_modes(self, value: dict):
        self._function_modes = value

    @property
    def modes_intro(self) -> str:
        return self._modes_intro

    @modes_intro.setter
    def modes_intro(self, value: str):
        self._modes_intro = value

    @property
    def modes_outro(self) -> str:
        return self._modes_outro

    @modes_outro.setter
    def modes_outro(self, value: str):
        self._modes_outro = value

    @property
    def send_info_to_llm(self) -> bool:
        return self._send_info_to_llm

    @send_info_to_llm.setter
    def send_info_to_llm(self, value: bool):
        self._send_info_to_llm = value


class Tooltip:
    def __init__(self, tooltip_name: str, target_info: TargetInfo, mode_info: ModeInfo):
        self._tooltip_name = tooltip_name
        self._target_info = target_info
        self._mode_info = mode_info

    # ---------- Traditional getters and setters ----------

    def get_tooltip_name(self) -> str:
        return self._tooltip_name

    def set_tooltip_name(self, tooltip_name: str):
        self._tooltip_name = tooltip_name

    def get_target_info(self) -> TargetInfo:
        return self._target_info

    def set_target_info(self, target_info: TargetInfo):
        self._target_info = target_info

    def get_mode_info(self) -> ModeInfo:
        return self._mode_info

    def set_mode_info(self, mode_info: ModeInfo):
        self._mode_info = mode_info

    # ---------- Pythonic properties ----------

    @property
    def tooltip_name(self) -> str:
        return self._tooltip_name

    @tooltip_name.setter
    def tooltip_name(self, value: str):
        self._tooltip_name = value

    @property
    def target_info(self) -> TargetInfo:
        return self._target_info

    @target_info.setter
    def target_info(self, value: TargetInfo):
        self._target_info = value

    @property
    def mode_info(self) -> ModeInfo:
        return self._mode_info

    @mode_info.setter
    def mode_info(self, value: ModeInfo):
        self._mode_info = value

