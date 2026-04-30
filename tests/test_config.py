from app.core.config import Settings


def test_settings_accepts_release_as_debug_false():
    settings = Settings(_env_file=None, jwt_secret="test-secret", debug="release")

    assert settings.debug is False


def test_prod_defaults_use_production_frontend_origin():
    settings = Settings(_env_file=None, jwt_secret="test-secret", environment="prod")

    assert settings.frontend_url == "https://engify-frontend.vercel.app"
    assert settings.allowed_origins == ["https://engify-frontend.vercel.app"]
