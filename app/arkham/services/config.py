import os
import yaml
import logging

from config.settings import CONFIG_YAML_PATH

logger = logging.getLogger(__name__)

CONFIG_PATH = str(CONFIG_YAML_PATH)


def load_config():
    """Loads the config.yaml file."""
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"Config file not found at {CONFIG_PATH}. Using defaults.")
        return {}

    with open(CONFIG_PATH, "r") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config.yaml: {e}")
            return {}


# Global config object
_config = load_config()


def get_config(key, default=None):
    """Retrieves a config value using dot notation (e.g., 'ocr.paddle.use_gpu')."""
    keys = key.split(".")
    value = _config
    for k in keys:
        if isinstance(value, dict):
            value = value.get(k)
        else:
            return default

    return value if value is not None else default
