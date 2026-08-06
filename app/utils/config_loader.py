from pathlib import Path
import yaml


class ConfigLoader:
    """
    Reads settings.yaml and returns the configuration.
    """

    def __init__(self):
        self.config_path = Path("configs/settings.yaml")
        self.config = self.load_config()

    def load_config(self):
        with open(self.config_path, "r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def get(self):
        return self.config