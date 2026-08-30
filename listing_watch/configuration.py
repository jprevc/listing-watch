from __future__ import annotations

import os
import pathlib

from typing import Literal

import pydantic

DEFAULT_CONFIG_PATH = pathlib.Path("config") / "listing_watch.yaml"


def find_config(config_path: pathlib.Path | None = None) -> pathlib.Path:
    def_config_paths: list[pathlib.Path] = [DEFAULT_CONFIG_PATH, pathlib.Path("listing_watch.yaml")]

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


class ScheduleConfig(pydantic.BaseModel):
    every: int = 1
    units: Literal["seconds", "minutes", "hours", "days", "weeks"] = "minutes"


class SpiderConfig(pydantic.BaseModel):
    notifications: dict[str, dict[str, str | bool]]
    urls: dict[str, str]


class ListingWatchConfig(pydantic.BaseModel):
    schedule: ScheduleConfig | None = None
    spiders: dict[str, SpiderConfig]
