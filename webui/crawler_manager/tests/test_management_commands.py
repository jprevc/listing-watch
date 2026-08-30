import pathlib

import pytest
import yaml
from django.core.management import call_command

from crawler_manager.models import Query, QueryNotificationConfig

pytestmark = pytest.mark.django_db

SAMPLE_CONFIG = {
    "schedule": {"every": 15, "units": "minutes"},
    "spiders": {
        "example": {
            "urls": {"kia": "https://example.com/kia"},
            "notifications": {
                "email": {
                    "email_user": "__env_EMAIL_USER",
                    "email_password": "__env_EMAIL_PASS",
                    "recipients": "a@b.com",
                    "message_body_format": "{title}",
                }
            },
        },
        "unknown_spider": {
            "urls": {"whatever": "https://example.com"},
            "notifications": {},
        },
    },
}


@pytest.fixture(name="config_file")
def config_file_fixture(tmp_path: pathlib.Path) -> pathlib.Path:
    path = tmp_path / "news_crawlers.yaml"
    with open(path, "w", encoding="utf8") as f:
        yaml.safe_dump(SAMPLE_CONFIG, f)
    return path


def test_migrate_yaml_config_imports_known_spiders(config_file: pathlib.Path) -> None:
    call_command("migrate_yaml_config", config=str(config_file))

    query = Query.objects.get(spider_name="example", name="kia")
    assert query.url == "https://example.com/kia"
    assert query.cron_schedule == "*/15 * * * *"
    assert QueryNotificationConfig.objects.filter(query=query, notificator_name="email").exists()


def test_migrate_yaml_config_skips_unknown_spider(config_file: pathlib.Path) -> None:
    call_command("migrate_yaml_config", config=str(config_file))

    assert not Query.objects.filter(spider_name="unknown_spider").exists()


def test_migrate_yaml_config_dry_run_writes_nothing(config_file: pathlib.Path) -> None:
    call_command("migrate_yaml_config", config=str(config_file), dry_run=True)

    assert Query.objects.count() == 0
