from core.routers import AppOnlyRouter


def test_only_the_app_database_is_migrated() -> None:
    router = AppOnlyRouter()
    assert router.allow_migrate("default", "accounts")
    assert not router.allow_migrate("data", "accounts")
    assert not router.allow_migrate("data_reader", "accounts")


def test_models_read_and_write_the_app_database() -> None:
    router = AppOnlyRouter()
    assert router.db_for_read(object) == "default"
    assert router.db_for_write(object) == "default"
