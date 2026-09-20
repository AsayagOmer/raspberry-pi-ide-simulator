import os
import glob
import importlib

COMPONENT_REGISTRY = {}

def register_component(name, color="#555555"):
    def decorator(cls):
        COMPONENT_REGISTRY[name] = {
            "class": cls,
            "color": color
        }
        return cls
    return decorator

# Dynamically import all .py files in this directory to run their decorators
_components_dir = os.path.dirname(__file__)
for _file in glob.glob(os.path.join(_components_dir, "*.py")):
    _basename = os.path.basename(_file)
    if _basename.startswith("__") or _basename == "base_component.py":
        continue
    _module_name = _basename[:-3]
    importlib.import_module(f"components.{_module_name}")
