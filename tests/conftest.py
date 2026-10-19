import pytest

from threadsense import config


@pytest.fixture(autouse=True)
def isolate_local_credentials(monkeypatch, tmp_path):
    """Keep tests independent of the developer's saved API keys and model."""
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for name in ("OPENAI_API_KEY", "OPENROUTER_API_KEY", "THREADSENSE_MODEL"):
        monkeypatch.delenv(name, raising=False)
