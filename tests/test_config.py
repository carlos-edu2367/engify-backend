from app.core.config import Settings


def test_settings_accepts_release_as_debug_false():
    settings = Settings(_env_file=None, jwt_secret="test-secret", debug="release")

    assert settings.debug is False
