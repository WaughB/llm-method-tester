"""Storage-location discovery, activation, and API tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from pageindex_test.config import Settings
from pageindex_test.db.repos import SettingsRepo
from pageindex_test.locations import LocationService, library_dir, list_locations
from pageindex_test.main import AppDeps, create_app


@pytest.fixture
def two_roots(tmp_path: Path) -> Settings:
    (tmp_path / "desktop").mkdir()
    # "external" intentionally NOT created -> unavailable
    raw = f"{tmp_path / 'desktop'}=C:\\Users\\brett\\Desktop;{tmp_path / 'external'}=E:\\archive"
    return Settings(_env_file=None, mount_roots_raw=raw)


class TestListLocations:
    def test_reports_availability_and_free_space(self, two_roots: Settings) -> None:
        locations = list_locations(two_roots)
        assert len(locations) == 2
        desktop, external = locations
        assert desktop.available is True
        assert desktop.free_bytes and desktop.free_bytes > 0
        assert desktop.host_label == "C:\\Users\\brett\\Desktop"
        assert external.available is False
        assert external.free_bytes is None

    def test_location_ids_stable_and_distinct(self, two_roots: Settings) -> None:
        first = list_locations(two_roots)
        second = list_locations(two_roots)
        assert [x.location_id for x in first] == [x.location_id for x in second]
        assert first[0].location_id != first[1].location_id

    def test_unset_optional_root_skipped(self, tmp_path: Path) -> None:
        settings = Settings(_env_file=None, mount_roots_raw=f"{tmp_path}=D:\\data;/mnt/store1=")
        assert len(list_locations(settings)) == 1


class TestLibraryDir:
    def test_creates_structure(self, two_roots: Settings) -> None:
        [desktop, _] = list_locations(two_roots)
        lib = library_dir(desktop)
        assert (lib / "docs").is_dir()
        assert (lib / "trees").is_dir()


class TestLocationService:
    def test_defaults_to_first_available(self, two_roots: Settings, engine: Engine) -> None:
        service = LocationService(two_roots, SettingsRepo(engine))
        active = service.active()
        assert active is not None
        assert active.host_label == "C:\\Users\\brett\\Desktop"

    def test_activate_persists(self, two_roots: Settings, engine: Engine) -> None:
        repo = SettingsRepo(engine)
        service = LocationService(two_roots, repo)
        target = service.list()[0]
        service.activate(target.location_id)
        assert repo.get("active_location_id") == target.location_id
        assert service.active().location_id == target.location_id

    def test_activate_unavailable_raises(self, two_roots: Settings, engine: Engine) -> None:
        service = LocationService(two_roots, SettingsRepo(engine))
        unavailable = service.list()[1]
        with pytest.raises(ValueError, match="not available"):
            service.activate(unavailable.location_id)

    def test_activate_unknown_raises(self, two_roots: Settings, engine: Engine) -> None:
        service = LocationService(two_roots, SettingsRepo(engine))
        with pytest.raises(KeyError):
            service.activate("nope")

    def test_stored_but_vanished_location_falls_back(
        self, two_roots: Settings, engine: Engine
    ) -> None:
        repo = SettingsRepo(engine)
        repo.set("active_location_id", "vanished99999")
        service = LocationService(two_roots, repo)
        assert service.active().available is True


class TestLocationsApi:
    @pytest.fixture
    def client(self, two_roots: Settings, engine: Engine) -> TestClient:
        return TestClient(create_app(AppDeps(settings=two_roots, engine=engine)))

    def test_list_marks_active(self, client: TestClient) -> None:
        data = client.get("/api/locations").json()
        assert len(data["locations"]) == 2
        assert data["locations"][0]["active"] is True
        assert data["locations"][1]["active"] is False

    def test_activate_roundtrip(self, client: TestClient) -> None:
        locations = client.get("/api/locations").json()["locations"]
        response = client.put(
            "/api/locations/active", json={"location_id": locations[0]["location_id"]}
        )
        assert response.status_code == 200

    def test_activate_unavailable_409(self, client: TestClient) -> None:
        locations = client.get("/api/locations").json()["locations"]
        response = client.put(
            "/api/locations/active", json={"location_id": locations[1]["location_id"]}
        )
        assert response.status_code == 409

    def test_activate_unknown_404(self, client: TestClient) -> None:
        assert client.put("/api/locations/active", json={"location_id": "zz"}).status_code == 404

    def test_settings_roundtrip(self, client: TestClient) -> None:
        data = client.get("/api/settings").json()
        assert data["default_model"] == "llama3.1:8b"
        updated = client.put("/api/settings", json={"default_model": "gpt-oss:20b"}).json()
        assert updated["default_model"] == "gpt-oss:20b"

    def test_settings_rejects_unknown_keys(self, client: TestClient) -> None:
        assert client.put("/api/settings", json={"hax": 1}).status_code == 400
