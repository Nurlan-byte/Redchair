import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings


def test_settings_reject_short_secret_key():
    with pytest.raises(ValidationError) as exc:
        Settings(database_url=settings.sqlalchemy_url, secret_key="x" * 31)

    assert exc.value.errors()[0]["loc"] == ("secret_key",)
