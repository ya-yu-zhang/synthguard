import pytest


@pytest.fixture
def isolated_data(tmp_path, monkeypatch):
    """Point data/runs roots at a temp dir so tests never touch real pools."""
    from synthguard import settings

    settings.get_settings.cache_clear()
    monkeypatch.setenv("SYNTHGUARD_DATA_ROOT", str(tmp_path / "data"))
    monkeypatch.setenv("SYNTHGUARD_RUNS_ROOT", str(tmp_path / "runs"))
    yield tmp_path
    settings.get_settings.cache_clear()
