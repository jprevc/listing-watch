import os
import pathlib
from typing import Union, Dict, Optional

import pydantic

DEFAULT_CONFIG_PATH = pathlib.Path("config") / "news_crawlers.yaml"


def find_config(config_path: Optional[Union[str, pathlib.Path]] = None) -> pathlib.Path:
    def_config_paths: list[Union[str, pathlib.Path]] = [DEFAULT_CONFIG_PATH, "news_crawlers.yaml"]

    if config_path is not None:
        config_path = pathlib.Path(config_path)
        if config_path.exists():
            return config_path
        raise FileNotFoundError(f"Could not find configuration file {config_path}.")

    for def_config_path in def_config_paths:
        if pathlib.Path(def_config_path).exists():
            return pathlib.Path(def_config_path)

    raise FileNotFoundError(
        f"Could not find configuration file on {config_path} or in current working directory {os.getcwd()}."
    )


class NewsCrawlerConfig(pydantic.BaseModel):
    notifications: dict
    urls: Dict[str, str]
