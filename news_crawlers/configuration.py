# from __future__ import annotations

import os
import pathlib
from typing import Union, Dict

import pydantic

DEFAULT_CONFIG_PATH = pathlib.Path("config") / "news_crawlers.yaml"


def find_config(config_path: Union[str, pathlib.Path]) -> pathlib.Path:
    config_path = pathlib.Path(config_path)

    if config_path != DEFAULT_CONFIG_PATH and not os.path.exists(config_path):
        raise FileNotFoundError(f"Could not find configuration file on {config_path}")

    config_path = DEFAULT_CONFIG_PATH if DEFAULT_CONFIG_PATH.exists() else pathlib.Path("news_crawlers.yaml")

    if not config_path.exists():
        raise FileNotFoundError(
            f"Could not find configuration file on {config_path} or in current working directory {os.getcwd()}."
        )

    return config_path


class NewsCrawlerConfig(pydantic.BaseModel):
    notifications: dict
    urls: Dict[str, str]
