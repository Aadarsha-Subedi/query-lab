"""Django models live only in the app database. The data database (querylab)
is never migrated: its schema comes from infra/sql via bootstrap_data_db."""

from typing import Any

APP_DB_ALIAS = "default"


class AppOnlyRouter:
    def db_for_read(self, model: type, **hints: Any) -> str:
        return APP_DB_ALIAS

    def db_for_write(self, model: type, **hints: Any) -> str:
        return APP_DB_ALIAS

    def allow_relation(self, obj1: object, obj2: object, **hints: Any) -> bool:
        return True

    def allow_migrate(self, db: str, app_label: str, **hints: Any) -> bool:
        return db == APP_DB_ALIAS
