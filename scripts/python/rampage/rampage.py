import json
import os
import string
import secrets

import hou

from enum import Enum, unique
from functools import lru_cache
from typing import Optional, Tuple, Dict, Union, List

from . import dialog


@unique
class RampType(Enum):
    FLOAT = "float"
    COLOR = "color"


class RampPreset:
    """
    Conversion class that allow easily converting between ramp parameter,
    rampage parm dict and hou.Ramp.

    >>> parm = hou.node("test_node")
    >>> ramp_preset = RampPreset.from_parm(parm)
    >>> ramp_dict = ramp_preset.to_dict()
    """

    def __init__(
        self,
        name: str,
        ramp_type: RampType,
        basis: Tuple[str],
        keys: Tuple[float],
        values: Tuple[Union[float, Tuple[float]]],
    ) -> None:
        """Initialize RampPreset

        Args:
            name (str): name of ramp
            ramp_type (RampType): type of ramp
            basis (Tuple[str]): tuple of strings of values with basis
            keys (Tuple[float]): tuple of key positions
            values (Tuple[Union[float, Tuple[float]]]): tuple of ramp values
        """
        if len(basis) != len(keys) != len(values):
            ValueError("basis, keys and values must have the same length!")
        self.name = name
        self.ramp_type = ramp_type
        self.basis = basis
        self.keys = keys
        self.values = values

    @classmethod
    def from_dict(cls, preset_dict: Dict) -> "RampPreset":
        """Alternative constructor that allow to create class form dict

        Args:
            preset_dict (Dict): preset dict

        Returns:
            RampPreset: instance of RampPreset class
        """
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
        """Converts class to preset dict

        Returns:
            Dict: preset dict
        """
        return {
            "name": self.name,
            "ramp_type": self.ramp_type.value,
            "keys": self.keys,
            "values": self.values,
            "basis": self.basis,
        }

    @classmethod
    def from_parm(cls, parm: hou.Parm, name: Optional[str] = None) -> "RampPreset":
        """alternative constructor that let construct class from ramp parm.

        Args:
            parm (hou.Parm): ramp parm
            name (Optional[str], optional): Name of preset if not given
                will be derive from parm name. Defaults to None.

        Raises:
            TypeError: when given parm is not ramp parm

        Returns:
            RampPreset: instance of RampPreset class
        """
        if not is_ramp_parm(parm):
            raise TypeError("Cannot use not ramp parameter type!")

        ramp: hou.Ramp = parm.evalAsRamp()
        if not name:
            name = parm.name()
        return cls.from_ramp(ramp, name)

    @classmethod
    def from_ramp(cls, ramp: hou.Ramp, name: str) -> "RampPreset":
        """Alternative constructor that let construct class from hou.Ramp

        Args:
            ramp (hou.Ramp): ramp
            name (str): name of RampPreset

        Returns:
            RampPreset: instance of RampPreset class
        """
        ramp_type = RampType.COLOR if ramp.isColor() else RampType.FLOAT
        basis = tuple(basis.name() for basis in ramp.basis())
        return cls(name, ramp_type, basis, ramp.keys(), ramp.values())

    def to_ramp(self) -> hou.Ramp:
        """Convert class to hou.Ramp

        Returns:
            hou.Ramp: houdini representation of ramp
        """
        ramp_basis = tuple(_convert_str_to_ramp_basis(base) for base in self.basis)
        return hou.Ramp(ramp_basis, self.keys, self.values)


def _convert_str_to_ramp_basis(basis_str: str):
    """Converts preset string to hou.rampBasis value

    Args:
        basis_str (str): basis in string form

    Raises:
        ValueError: when basis is not found in hou.rampBasis enum

    Returns:
        hou.rampBasis: basis in form of hou.rampBasis enum value
    """
    for method in dir(hou.rampBasis):
        if method.startswith("_"):
            continue

        if method[0].islower():
            continue

        basis = getattr(hou.rampBasis, method)
        if basis.name() == basis_str:
            return basis

    raise ValueError(f"Could not find {basis_str} in hou.rampBasis")


def is_ramp_parm(parm: hou.Parm) -> bool:
    """Checks if given parm is ramp parm

    Args:
        parm (hou.Parm): parameter

    Returns:
        bool: True if it is ramp parm
    """
    return parm.parmTemplate().type() == hou.parmTemplateType.Ramp


#######################################################################################
# Menu related functions
#######################################################################################


def should_display_rampage_menu(kwargs: dict) -> bool:
    """Checks if houdini should display rampage menu

    Args:
        kwargs (dict): kwargs given by PARMmenu.xml item

    Returns:
        bool: when True display rampage menu
    """
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
    """Callback for add ramp preset menu callback

    Args:
        kwargs (dict): kwargs given by PARMmenu.xml item
    """
    choice, name = hou.ui.readInput(
        "Name of the preset:",
    )
    if choice == -1:
        return

    _add_ramp_preset_to_presets_file(kwargs["parms"][0], name)


def _add_ramp_preset_to_presets_file(parm: hou.Parm, name: str) -> None:
    """Adds ramp preset to presets file.

    Args:
        parm (hou.Parm): ramp parm
        name (str): name of ramp preset

    Raises:
        ValueError: when given name already exists in file
    """
    preset = RampPreset.from_parm(parm, name)
    preset_key = hou.text.alphaNumeric(name.lower())
    ramp_type = _get_ramp_type(parm)
    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    presets_data = _read_preset_file(preset_file_path)

    if preset_key in presets_data:
        raise ValueError(f"Name {name} already exists in presets file")

    presets_data[preset_key] = preset.to_dict()

    _safe_save_preset_file(preset_file_path, presets_data)


def replace_preset(kwargs: dict) -> None:
    """Replace preset with current ramp value

    Args:
        kwargs (dict): kwargs given by PARMmenu.xml item
    """
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


def remove_preset(kwargs: dict) -> None:
    """Remove chosen preset from preset file.

    Args:
        kwargs (dict): kwargs given by PARMmenu.xml item
    """
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
    """Prompt user with selection menu with list of all ramp preset for given
    ramp type.

    Args:
        preset_data (dict): preset data dict
        message (Optional[str]): optional message to display for selection

    Returns:
        Optional[str]: name of preset, when user quit menu without selection None.
    """
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


def create_menu_strip(kwargs: dict) -> List[str]:
    """Create menu strip for rampage presets submenu.

    Args:
        kwargs (dict): kwargs given by PARMmenu.xml item

    Returns:
        List[str]: list of strings representing parm_name and parm_label of menu item
    """
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


def set_ramp_parm_from_chosen_ramp_preset(kwargs: dict) -> None:
    """Set value of ramp parameter base on value chosen by user
    in rampage presets submenu.

    Args:
        kwargs (dict): kwargs given by PARMmenu.xml item
    """
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


def rename_preset_menu_callback(kwargs: dict) -> None:
    """Callback called from PARMmenu.xml to rename ramp preset.

    Args:
        kwargs (dict): PARMmenu kwargs
    """
    parm = kwargs["parms"][0]
    ramp_type = _get_ramp_type(parm)
    preset_file_path = _get_preset_file_path_from_ramp_type(ramp_type)
    preset_dict = _read_preset_file(preset_file_path)

    menu_labels: List[str] = []
    menu_items: List[str] = []
    for key in preset_dict:
        label = preset_dict[key]["name"]
        menu_items.append(key)
        menu_labels.append(label)

    result = dialog.show_rename_dialog(menu_labels, menu_items)
    if not result:
        return

    old_menu_name, new_menu_name = result
    new_preset_dict = rename_ramp_preset(old_menu_name, new_menu_name, preset_dict)
    _safe_save_preset_file(preset_file_path, new_preset_dict)


def rename_ramp_preset(old_name: str, new_name: str, preset_dict: dict) -> dict:
    """Rename ramp preset from preset dict. Same data will be save but
    with different name.

    Args:
        old_name (str): old name of preset
        new_name (str): new name of preset
        preset_dict (dict): dict that have all of preset data

    Returns:
        dict: modified preset dict containing old version of data
    """
    if old_name not in preset_dict:
        return None

    preset = preset_dict.pop(old_name)
    preset["name"] = new_name
    key_name = hou.text.alphaNumeric(new_name.lower())
    preset_dict[key_name] = preset

    return preset_dict


def _safe_save_preset_file(preset_file_path: str, presets_data: dict):
    """Save modified preset file in safe way and clear read cache. At first
    preset file is saved as the same name with random characters on the end
    ie. `color.json.tam25l` and then is moved to replace json file. This way
    even if write fail original preset file should be fine.

    One other things that is done by this function is clearing cache of
    `_read_preset_file` function.

    Args:
        preset_file_path (str): path to preset file
        presets_data (dict): dictionary containing presets
    """
    temp_preset_file_path = preset_file_path + "." + _create_random_end_str(7)
    with open(temp_preset_file_path, "w") as file:
        json.dump(presets_data, file, indent=4)

    os.replace(temp_preset_file_path, preset_file_path)
    # TODO: Should it be really here?
    _read_preset_file.cache_clear()


def _create_random_end_str(num_of_chars: int) -> str:
    """Create string with random characters

    Args:
        num_of_chars (int): num of characters to add

    Returns:
        str: string to random characters
    """
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(num_of_chars))


def _get_ramp_type(parm: hou.Parm):
    """Get ramp type from parm

    Args:
        parm (hou.Parm): ramp parm

    Returns:
        hou.rampParmType: value of enum of given parm
    """
    parm_template = parm.parmTemplate()
    ramp_parm_type = parm_template.parmType()

    return ramp_parm_type


def _get_preset_file_path_from_ramp_type(ramp_type) -> str:
    """Get path to file containing preset base on ramp type.

    Args:
        ramp_type (hou.rampParmType): type of ramp

    Returns:
        str: filepath to to preset file
    """
    rampage_preset_dir = os.environ["RAMPAGE_PRESETS_PATH"]
    if ramp_type == hou.rampParmType.Color:
        rampage_preset_file = rampage_preset_dir + "/color.json"
    else:
        rampage_preset_file = rampage_preset_dir + "/float.json"

    return rampage_preset_file


@lru_cache()
def _read_preset_file(filepath: str) -> dict:
    """Cached function for reading preset from disc

    Args:
        filepath (str): path to file

    Returns:
        dict: dict of presets
    """
    with open(filepath) as file:
        data = json.load(file)
    return data
