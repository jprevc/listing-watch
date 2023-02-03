import os
import pathlib
import shutil
from typing import Callable

import pytest

from news_crawlers import configuration

# pylint: disable=unused-argument


@pytest.fixture(name="change_cwd")
def change_cwd_fixture(tmp_path):
    init_cwd = os.getcwd()
    os.chdir(tmp_path)

    yield

    os.chdir(init_cwd)


@pytest.fixture(name="create_root_tmp_config_file")
def create_root_tmp_config_file_fixture(change_cwd: Callable):
    with open("news_crawlers.yaml", "w+", encoding="utf8"):
        pass

    yield

    os.remove("news_crawlers.yaml")


@pytest.fixture(name="create_tmp_default_config_file")
def create_tmp_default_config_file_fixture(change_cwd: Callable):
    os.mkdir("config")
    config_path = pathlib.Path("config") / "news_crawlers.yaml"
    with open(config_path, "w+", encoding="utf8"):
        pass

    yield

    os.remove(config_path)
    shutil.rmtree("config")


@pytest.fixture(name="create_custom_tmp_config_file")
def create_custom_tmp_config_file_fixture(change_cwd: Callable):
    os.mkdir("custom_config")
    config_path = pathlib.Path("custom_config") / "news_crawlers.yaml"
    with open(config_path, "w+", encoding="utf8"):
        pass

    yield

    os.remove(config_path)


def test_find_config_if_specified(create_custom_tmp_config_file: Callable):
    config_path = pathlib.Path("custom_config") / "news_crawlers.yaml"
    assert configuration.find_config(config_path) == config_path


def test_find_config_raises_file_not_found_error_if_provided_path_does_not_exist(
    change_cwd: Callable, create_root_tmp_config_file: Callable
):
    with pytest.raises(FileNotFoundError):
        configuration.find_config("some/nonexisting/path/news_crawlers.yaml")


def test_find_config_raises_file_not_found_error_if_default_config_does_not_exist(change_cwd: Callable):
    with pytest.raises(FileNotFoundError):
        configuration.find_config("news_crawlers.yaml")


def test_find_config_returns_config_on_root_if_not_found_on_default(
    change_cwd: Callable, create_root_tmp_config_file: Callable
):
    assert configuration.find_config() == pathlib.Path("news_crawlers.yaml")


def test_find_config_returns_config_on_default_if_on_root_is_also_present(
    change_cwd: Callable, create_root_tmp_config_file: Callable, create_tmp_default_config_file: Callable
):
    assert configuration.find_config() == pathlib.Path("config/news_crawlers.yaml")
