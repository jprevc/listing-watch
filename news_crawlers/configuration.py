import os
import pathlib
from typing import Dict, Optional

import pydantic

DEFAULT_CONFIG_PATH = pathlib.Path("config") / "news_crawlers.yaml"


def find_config(config_path: Optional[pathlib.Path] = None) -> pathlib.Path:
    def_config_paths: list[pathlib.Path] = [DEFAULT_CONFIG_PATH, pathlib.Path("news_crawlers.yaml")]

    if config_path is not None:
        config_path = pathlib.Path(config_path)
        if config_path.exists():
            return config_path
        raise FileNotFoundError(f"Could not find configuration file {config_path}.")

    for def_config_path in def_config_paths:
        if def_config_path.exists():
            return def_config_path

    raise FileNotFoundError(
        f"Could not find configuration file in config folder or in current working directory {os.getcwd()}."
    )


class NewsCrawlerConfig(pydantic.BaseModel):
    notifications: dict
    urls: Dict[str, str]
