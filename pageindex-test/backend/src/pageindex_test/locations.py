"""User-selectable storage locations.

Roots are bind-mounted host directories (configured in .env). Each gets a
stable id derived from its host label; every stored artifact and DB row is
keyed by that id, so switching the active location swaps whole libraries
without migrating anything. A missing mount (unplugged external drive,
path not shared with Docker) shows as unavailable instead of crashing.
"""

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from pageindex_test.config import Settings

LIBRARY_DIRNAME = ".pageindex-test"


@dataclass(frozen=True)
class LocationInfo:
    location_id: str
    container_path: str
    host_label: str
    available: bool
    free_bytes: int | None = None
    total_bytes: int | None = None

    def as_dict(self) -> dict:
        return {
            "location_id": self.location_id,
            "host_label": self.host_label,
            "available": self.available,
            "free_bytes": self.free_bytes,
            "total_bytes": self.total_bytes,
        }


def location_id_for(host_label: str) -> str:
    return hashlib.sha1(host_label.encode("utf-8")).hexdigest()[:12]


def list_locations(settings: Settings) -> list[LocationInfo]:
    infos = []
    for root in settings.mount_roots:
        available = root.container_path.is_dir()
        free = total = None
        if available:
            try:
                usage = shutil.disk_usage(root.container_path)
                free, total = usage.free, usage.total
            except OSError:
                available = False
        infos.append(
            LocationInfo(
                location_id=location_id_for(root.host_label),
                container_path=str(root.container_path),
                host_label=root.host_label,
                available=available,
                free_bytes=free,
                total_bytes=total,
            )
        )
    return infos


def library_dir(location: LocationInfo) -> Path:
    """Root of everything we store under a location; created on demand."""
    path = Path(location.container_path) / LIBRARY_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    (path / "docs").mkdir(exist_ok=True)
    (path / "trees").mkdir(exist_ok=True)
    return path


class LocationService:
    """Active-location selection persisted in app_settings."""

    ACTIVE_KEY = "active_location_id"

    def __init__(self, settings: Settings, settings_repo) -> None:
        self._settings = settings
        self._repo = settings_repo

    def list(self) -> list[LocationInfo]:
        return list_locations(self._settings)

    def active(self) -> LocationInfo | None:
        locations = self.list()
        if not locations:
            return None
        stored = self._repo.get(self.ACTIVE_KEY)
        for location in locations:
            if location.location_id == stored and location.available:
                return location
        return next((loc for loc in locations if loc.available), None)

    def activate(self, location_id: str) -> LocationInfo:
        for location in self.list():
            if location.location_id == location_id:
                if not location.available:
                    raise ValueError(f"Location {location.host_label!r} is not available")
                self._repo.set(self.ACTIVE_KEY, location_id)
                return location
        raise KeyError(f"Unknown location {location_id!r}")
