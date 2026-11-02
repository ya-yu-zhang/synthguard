"""Machine-specific settings. Everything host-dependent lives in `.env` / environment.

Relative paths are resolved against the repository root, so the same `.env`
semantics hold on any machine.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").exists() and (parent / "configs").is_dir():
            return parent
    return Path.cwd()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(repo_root() / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    comfy_url: str = "http://127.0.0.1:8188"
    comfy_root: str = ""
    skip_diffusion: bool = False
    cuda_visible_devices: str = "0"
    train_devices: str = "0"
    synthguard_data_root: str = "./data"
    synthguard_runs_root: str = "./runs"
    gen_profile: str = "dev_5070"
    hf_endpoint: str = ""

    def _resolve(self, p: str) -> Path:
        path = Path(p)
        return path if path.is_absolute() else (repo_root() / path).resolve()

    @property
    def data_root(self) -> Path:
        return self._resolve(self.synthguard_data_root)

    @property
    def runs_root(self) -> Path:
        return self._resolve(self.synthguard_runs_root)

    @property
    def configs_dir(self) -> Path:
        return repo_root() / "configs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
