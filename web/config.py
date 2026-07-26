"""
Web layer configuration.

Deliberately separate from anything in services/ — this only configures
HOW the web frontend runs (host, port, debug mode), never business
logic or data. Reads from environment variables (or a local .env file,
for convenience in development), so the same code deploys to different
environments without edits — a real requirement once this moves beyond
a single developer's machine.

The JI_ prefix avoids collisions with generic env vars (DEBUG, PORT,
etc.) that a host platform or another process might already set.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    app_name: str = "Journal Intelligence"
    app_version: str = "0.2.0"
    github_url: str = "https://github.com/YasirM0/journal-intelligence"

    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="JI_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """
    Cached so Settings() (which reads the environment/.env file) only
    happens once per process, not once per request.
    """
    return Settings()
