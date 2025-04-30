import inspect
import json
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

# Dictionary mapping class names to actual classes
CLASS_MAP = {}

TEST_DATA_DIR = Path("tests_data")
TEST_DATA_DIR.mkdir(exist_ok=True)  # Creates the folder if it doesn't exist


def from_dict(d):
    if "__class__" in d:
        class_name = d.pop("__class__")  # Retrieves the class name
        if class_name in CLASS_MAP:
            return CLASS_MAP[class_name](**d)  # Reconstructs the object
    return d


def to_dict(obj):
    """Converts an object to a dictionary."""
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [to_dict(v) for v in obj]
    elif hasattr(obj, "__dict__"):  # C'est un objet custom
        result = {k: to_dict(v) for k, v in vars(obj).items()}
        result["__class__"] = obj.__class__.__name__
        return result
    else:
        return obj  # Valeur primitive (int, str, etc.)


def load_data(file_path):
    """Loads the JSON file containing existing inputs and outputs."""
    try:
        with open(file_path, "r") as file:
            return json.load(file, object_hook=from_dict)
    except FileNotFoundError:
        return {}  # Returns an empty dictionary if the file doesn't exist


def execute_class_methods(instance, data):
    """Executes instance methods with multiple sets of input data and updates the outputs."""
    cls = type(instance)

    for method_name, content in data.items():
        inputs = content.get("inputs", [])  # List of argument sets
        mocks = content.get("mocks", {})  # Dictionary of mocked values
        outputs = []

        with patch_multiple(cls, mocks):  # Applies mocks (internal and external)
            if hasattr(instance, method_name):
                method = getattr(instance, method_name)
                if callable(method):
                    for args in inputs:
                        outputs.append(method(**args))  # Executes each iteration and stores the result
        print(data)
        data[instance.__class__.__name__][method_name]["outputs"] = to_dict(outputs)  # Stores all outputs

    return data


def patch_multiple(cls, mocks):
    """Creates a patch context for multiple elements to mock, both internal and external."""
    stack = ExitStack()

    for attr, value in mocks.items():
        if "." in attr:
            stack.enter_context(patch(attr, return_value=value))
        else:
            stack.enter_context(patch.object(cls, attr, return_value=value))

    return stack  # À utiliser dans un `with`


def save_data(data, file_path):
    """Saves the results to a JSON file."""
    with open(file_path, "w") as f:
        json.dump(data, f, indent=4)


def main(instance: object):
    """Loads the data, runs the functions, and saves the outputs."""
    class_file_name = Path(inspect.getfile(instance.__class__)).name.split(".")[0]
    data_file = TEST_DATA_DIR / f"{class_file_name}.json"
    data = load_data(data_file)
    updated_data = execute_class_methods(instance, data)
    save_data(updated_data, data_file)


from JMapCloud.temp.Calculator import Calculator

if __name__ == "__main__":
    instance = Calculator("Hello")  # Instantiate the class with arguments if needed
    main(instance)
