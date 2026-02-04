import albums


class TestApp:
    def test_app_version(self):
        assert albums.__version__ == "0.0.0"  # poetry-dynamic-versioning does not substitute version during `poetry run pytest ...`
