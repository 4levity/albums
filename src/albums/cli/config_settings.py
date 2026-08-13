import re
from string import Template

from rich.markup import escape

from albums.app import Context
from albums.config import PathCompatibilityOption, RescanOption, SettingValueType, config_save
from albums.interactive.setup_settings import set_library
from albums.tagger import ID3v1Policy


def render_setting(key: str, value: SettingValueType):
    if key == "settings.id3v1" and isinstance(value, int):
        return ID3v1Policy(int(value)).name
    if key == "settings.sync_destinations" and isinstance(value, list):
        return escape(",".join(str(v["collection"]) for v in value if isinstance(v, dict)))
    if isinstance(value, list):
        return escape(",".join(str(v) for v in value))
    return escape(str(value))


def _set_check(ctx: Context, check_name: str, name: str, value: str):
    if check_name not in ctx.config.checks:
        ctx.console.print(f"{check_name} is not a valid check name")
        raise SystemExit(1)

    config = ctx.config.checks[check_name]
    if name not in config:
        ctx.console.print(f"{name} is not a valid option for check {check_name}")
        raise SystemExit(1)
    if isinstance(config[name], list):
        config[name] = value.split(",")
    elif isinstance(config[name], str):
        config[name] = value
    elif isinstance(config[name], bool):
        if str.lower(value) not in {"true", "false", "t", "f"}:
            ctx.console.print(f"{check_name}.{name} must be true or false")
            raise SystemExit(1)
        config[name] = str.lower(value) in {"true", "t"}
    elif isinstance(config[name], float):
        if not re.fullmatch("\\d+(\\.\\d+)?", value):
            ctx.console.print(f"{check_name}.{name} must be a non-negative floating point number")
            raise SystemExit(1)
        config[name] = float(value)
    elif isinstance(config[name], int):
        if not re.fullmatch("\\d+", value):
            ctx.console.print(f"{check_name}.{name} must be a non-negative integer")
            raise SystemExit(1)
        config[name] = int(value)
    else:
        raise ValueError(f"{check_name}.{name} has unexpected type {type(config[name])}")


def set_setting(ctx: Context, setting_name: str, value: str) -> bool:
    keys = setting_name.split(".")
    if len(keys) != 2:
        ctx.console.print(f"invalid setting {setting_name}")
        return False

    [section, name] = keys
    if section == "settings":
        if name == "default_import_path":
            ctx.config.default_import_path = Template(value)
            config_save(ctx.db, ctx.config)
        elif name == "default_import_path_various":
            ctx.config.default_import_path_various = Template(value)
            config_save(ctx.db, ctx.config)
        elif name == "id3v1":
            ctx.config.id3v1 = ID3v1Policy[str.upper(value)]
            config_save(ctx.db, ctx.config)
        elif name == "import_scan_max_paths":
            ctx.config.import_scan_max_paths = int(value)
            config_save(ctx.db, ctx.config)
        elif name == "library":
            set_library(ctx, value)
        elif name == "more_import_paths":
            ctx.config.more_import_paths = [Template(v) for v in value.split(",")]
            config_save(ctx.db, ctx.config)
        elif name == "open_folder_command":
            ctx.config.open_folder_command = value
            config_save(ctx.db, ctx.config)
        elif name == "path_compatibility":
            ctx.config.path_compatibility = PathCompatibilityOption(value)
            config_save(ctx.db, ctx.config)
        elif name == "path_replace_invalid":
            ctx.config.path_replace_invalid = value
            config_save(ctx.db, ctx.config)
        elif name == "path_replace_slash":
            ctx.config.path_replace_slash = value
            config_save(ctx.db, ctx.config)
        elif name == "rescan":
            ctx.config.rescan = RescanOption(value)
            config_save(ctx.db, ctx.config)
        elif name == "tagger":
            ctx.config.tagger = value
            config_save(ctx.db, ctx.config)
        elif name == "sync_destinations":
            ctx.console.print("Use interactive config or import to create or update sync destinations")
            return False
        else:
            ctx.console.print(f"{setting_name} is not a valid setting")
            return False

    else:
        _set_check(ctx, section, name, value)
        config_save(ctx.db, ctx.config)
    return True
