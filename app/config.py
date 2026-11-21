"""Settings read from environment variables."""

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path
    password: str | None
    secret_key: str
    contact_email: str | None       # in effect: the one from Settings, else BUBO_CONTACT_EMAIL
    env_contact_email: str | None   # BUBO_CONTACT_EMAIL, the fallback
    secure_cookies: bool
    session_days: int
    radar_hours: float = 12      # how often to look for new work by followed people (0: never)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "library.db"

    @property
    def papers_dir(self) -> Path:
        return self.data_dir / "papers"

    @property
    def legacy_files_dir(self) -> Path:
        # Where PDFs were kept (as <uuid>.pdf) before readable names; migrated on start-up.
        return self.data_dir / "files"


def _load_secret(data_dir: Path) -> str:
    env = os.environ.get("BUBO_SECRET")
    if env:
        return env
    # If not set, generate one once and store it alongside the data so that
    # sessions survive restarts.
    path = data_dir / ".secret_key"
    if path.exists():
        return path.read_text().strip()
    key = secrets.token_urlsafe(48)
    path.write_text(key)
    try:
        path.chmod(0o600)
    except OSError:
        pass  # exFAT/NTFS have no Unix permissions
    return key


def load_settings() -> Settings:
    data_dir = Path(os.environ.get("BUBO_DATA", "./data")).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "papers").mkdir(exist_ok=True)
    return Settings(
        data_dir=data_dir,
        password=os.environ.get("BUBO_PASSWORD") or None,
        secret_key=_load_secret(data_dir),
        contact_email=os.environ.get("BUBO_CONTACT_EMAIL") or None,
        env_contact_email=os.environ.get("BUBO_CONTACT_EMAIL") or None,
        secure_cookies=_bool(os.environ.get("BUBO_SECURE_COOKIES"), False),
        session_days=int(os.environ.get("BUBO_SESSION_DAYS", "30")),
        radar_hours=float(os.environ.get("BUBO_RADAR_HOURS", "12")),
    )


settings = load_settings()
