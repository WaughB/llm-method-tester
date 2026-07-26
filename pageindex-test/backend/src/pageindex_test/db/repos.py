"""Repository classes over the Core schema. Grows with each phase."""

from sqlalchemy import Engine, select

from pageindex_test.db.schema import app_settings


class SettingsRepo:
    """Key/value app settings (active location, pipeline knobs)."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, key: str, default=None):
        with self._engine.connect() as conn:
            row = conn.execute(
                select(app_settings.c.value).where(app_settings.c.key == key)
            ).fetchone()
        return row[0] if row else default

    def set(self, key: str, value) -> None:
        with self._engine.begin() as conn:
            existing = conn.execute(
                select(app_settings.c.key).where(app_settings.c.key == key)
            ).fetchone()
            if existing:
                conn.execute(
                    app_settings.update().where(app_settings.c.key == key).values(value=value)
                )
            else:
                conn.execute(app_settings.insert().values(key=key, value=value))

    def all(self) -> dict:
        with self._engine.connect() as conn:
            rows = conn.execute(select(app_settings)).fetchall()
        return {row.key: row.value for row in rows}
