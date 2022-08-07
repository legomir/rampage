import json
import os
import string
import secrets

import hou

from enum import Enum, unique
from functools import lru_cache
from typing import Optional, Tuple, Dict, Union, List


@unique
class RampType(Enum):
    FLOAT = "float"
    COLOR = "color"


class RampPreset:
    def __init__(
        self,
        name: str,
        ramp_type: RampType,
        basis: Tuple[str],
        keys: Tuple[float],
        values: Tuple[Union[float, Tuple[float]]],
    ) -> None:
        if len(basis) != len(keys) != len(values):
            ValueError("basis, keys and values must have the same length!")
        self.name = name
        self.ramp_type = ramp_type
        self.basis = basis
        self.keys = keys
        self.values = values

    @classmethod
    def from_dict(cls, preset_dict: Dict) -> "RampPreset":
        ramp_type = RampType(preset_dict["ramp_type"])
        ramp_preset = RampPreset(
            preset_dict["name"],
            ramp_type,
            values=preset_dict["values"],
            basis=preset_dict["basis"],
            keys=preset_dict["keys"],
        )
        return ramp_preset

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "ramp_type": self.ramp_type.value,
            "keys": self.keys,
            "values": self.values,
            "basis": self.basis,
        }

    @classmethod
    def from_parm(cls, parm: hou.Parm, name: Optional[str] = None) -> "RampPreset":
        if not is_ramp_parm(parm):
            raise TypeError("Cannot use not ramp parameter type!")

        ramp: hou.Ramp = parm.evalAsRamp()
        if not name:
            name = parm.name()
        return cls.from_ramp(ramp, name)

    @classmethod
    def from_ramp(cls, ramp: hou.Ramp, name: str) -> "RampPreset":
        ramp_type = RampType.COLOR if ramp.isColor() else RampType.FLOAT
        basis = tuple(basis.name() for basis in ramp.basis())
        return cls(name, ramp_type, basis, ramp.keys(), ramp.values())

    def to_ramp(self) -> hou.Ramp:
        ramp_basis = tuple(_convert_str_to_ramp_basis(base) for base in self.basis)
        return hou.Ramp(ramp_basis, self.keys, self.values)


def _convert_str_to_ramp_basis(basis_str: str):
    for method in dir(hou.rampBasis):
        if method.startswith("_"):
            continue

        if method[0].islower():
            continue

        basis = getattr(hou.rampBasis, method)
        if basis.name() == basis_str:
            return basis

    raise ValueError(f"Could not find {basis_str} in hou.rampBasis")


def is_ramp_parm(parm: hou.Parm):
    return parm.parmTemplate().type() == hou.parmTemplateType.Ramp


#######################################################################################
# Menu related functions
#######################################################################################


def should_display_rampage_menu(kwargs: dict) -> bool:
    if not kwargs["parms"]:
        return False

    if len(kwargs["parms"]) > 1:
        return False

    parm = kwargs["parms"][0]
    parm_template = parm.parmTemplate()
    parm_template_type = parm_template.type()
    if parm_template_type != hou.parmTemplateType.Ramp:
        return False

    return True


def add_ramp_preset_menu_callback(kwargs: dict) -> None:
    choice, name = hou.ui.readInput(
        "Name of the preset:",
    )
    if choice == -1:
        return

    _add_ramp_preset_to_presets_file(kwargs["parms"][0], name)


def _add_ramp_preset_to_presets_file(parm: hou.Parm, name: str):
    preset = RampPreset.from_parm(parm, name)
    preset_key = hou.text.alphaNumeric(name.lower())
    ramp_type = _get_ramp_type(parm)
    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    presets_data = _read_preset_file(preset_file_path)

    if preset_key in presets_data:
        raise ValueError(f"Name {name} already exists in presets file")

    presets_data[preset_key] = preset.to_dict()

    _safe_save_preset_file(preset_file_path, presets_data)


def _create_random_end_str(num_of_chars: int):
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(num_of_chars))


def _get_ramp_type(parm: hou.Parm):
    parm_template = parm.parmTemplate()
    ramp_parm_type = parm_template.parmType()

    return ramp_parm_type


def create_menu_strip(kwargs: dict) -> List[str]:
    if not kwargs["parms"]:
        return []

    if len(kwargs["parms"]) > 1:
        return []

    parm = kwargs["parms"][0]
    ramp_type = _get_ramp_type(parm)

    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    preset_dict = _read_preset_file(preset_file_path)

    items = []
    for key in preset_dict:
        name = preset_dict[key]["name"]
        items.append(key)
        items.append(name)

    return items


def set_ramp_parm_from_chosen_ramp_preset(kwargs) -> None:
    parm = kwargs["parms"][0]
    token = kwargs["selectedtoken"]
    ramp_type = _get_ramp_type(parm)
    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    preset_dict = _read_preset_file(preset_file_path)

    preset = preset_dict.get(token, None)
    if preset is None:
        return

    ramp_preset = RampPreset.from_dict(preset)
    parm.set(ramp_preset.to_ramp())


def replace_preset(kwargs) -> None:
    parm = kwargs["parms"][0]
    ramp_type = _get_ramp_type(parm)
    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    preset_dict = _read_preset_file(preset_file_path)

    key = _user_choice_selection_from_preset_list(
        preset_dict, "Select preset to replace"
    )
    if not key:
        return

    preset = RampPreset.from_parm(parm, preset_dict[key]["name"])
    preset_dict[key] = preset.to_dict()

    _safe_save_preset_file(preset_file_path, preset_dict)


def remove_preset(kwargs) -> None:
    parm = kwargs["parms"][0]
    ramp_type = _get_ramp_type(parm)
    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    preset_dict = _read_preset_file(preset_file_path)

    key = _user_choice_selection_from_preset_list(
        preset_dict, "Select preset to remove"
    )
    if not key:
        return

    del preset_dict[key]
    _safe_save_preset_file(preset_file_path, preset_dict)


def _user_choice_selection_from_preset_list(
    preset_data: dict, message: Optional[str]
) -> Optional[str]:
    preset_names = tuple(preset["name"] for preset in preset_data.values())
    choices = hou.ui.selectFromList(
        preset_names,
        message=message,
        exclusive=True,
        column_header="Presets",
        clear_on_cancel=True,
    )

    if len(choices) == 0:
        return

    key = list(preset_data.keys())[choices[0]]
    return key


def _safe_save_preset_file(preset_file_path, presets_data):
    temp_preset_file_path = preset_file_path + "." + _create_random_end_str(7)
    with open(temp_preset_file_path, "w") as file:
        json.dump(presets_data, file, indent=4)

    os.replace(temp_preset_file_path, preset_file_path)
    _read_preset_file.cache_clear()


def _get_preset_file_path_from_ramp_type(ramp_type) -> str:
    rampage_preset_dir = os.environ["RAMPAGE_PRESETS_PATH"]
    if ramp_type == hou.rampParmType.Color:
        rampage_preset_file = rampage_preset_dir + "/color.json"
    else:
        rampage_preset_file = rampage_preset_dir + "/float.json"

    return rampage_preset_file


@lru_cache()
def _read_preset_file(filepath: str):
    with open(filepath) as file:
        data = json.load(file)
    return data
