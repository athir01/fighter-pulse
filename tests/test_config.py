import pytest

from ingest.config import Settings


def test_missing_required_fields_raises():
    with pytest.raises(Exception):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_defaults_applied_when_required_fields_present():
    settings = Settings(
        database_url="postgresql://u:p@localhost/db",
        anthropic_api_key="sk-ant-test",
        _env_file=None,
    )  # type: ignore[call-arg]
    assert settings.llm_cost_cap_usd == 5.00
    assert settings.ingest_rate_limit_rps == 1.0
