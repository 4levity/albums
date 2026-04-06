import re
from pathlib import Path
from string import Template
from typing import Literal

import humanize
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter
from prompt_toolkit.shortcuts import choice, confirm

from ..app import Context
from ..config import ID3v1Policy, PathCompatibilityOption, RescanOption
from ..database import db_config
from ..library.paths import show_template_path_help


def configure_settings(ctx: Context):
    option = "_"
    while option and option != "back":
        option = choice(
            message="edit a setting",
            options=[
                ("library", f"library ({str(ctx.config.library)})"),
                ("path_compatibility", f"path_compatibility ({ctx.config.path_compatibility})"),
                ("path_replace_slash", f"path_replace_slash ({ctx.config.path_replace_slash})"),
                ("path_replace_invalid", f"path_replace_invalid ({ctx.config.path_replace_invalid})"),
                ("rescan", f"rescan ({ctx.config.rescan})"),
                ("tagger", f"tagger ({ctx.config.tagger if ctx.config.tagger else 'not set'})"),
                (
                    "open_folder_command",
                    f"open_folder_command ({ctx.config.open_folder_command if ctx.config.open_folder_command else 'not set'})",
                ),
                ("default_import_path", f"default_import_path ({ctx.config.default_import_path.template})"),
                ("default_import_path_various", f"default_import_path_various ({ctx.config.default_import_path_various.template})"),
                ("more_import_paths", f"more_import_paths ({','.join(t.template for t in ctx.config.more_import_paths)})"),
                ("import_scan_max_paths", f"import_scan_max_paths ({ctx.config.import_scan_max_paths})"),
                ("id3v1", f"id3v1 ({ctx.config.id3v1.name})"),
                ("transcoder_cache", f"transcoder_cache ({str(ctx.config.transcoder_cache)}"),
                ("transcoder_cache_size", f"transcoder_cache_size ({humanize.naturalsize(ctx.config.transcoder_cache_size, binary=True)}"),
                ("back", "<< go back"),
            ],
        )
        if option and option != "back":
            _configure_setting(ctx, option)


def set_library(ctx: Context, new_library: str):
    if new_library and Path(new_library).is_dir():
        ctx.config.library = Path(new_library)
        db_config.save(ctx.db, ctx.config)
    else:
        ctx.console.print("Error: library must be a directory that exists and is accessible")


def _configure_setting(
    ctx: Context,
    setting: Literal[
        "library",
        "path_compatibility",
        "path_replace_slash",
        "path_replace_invalid",
        "rescan",
        "tagger",
        "open_folder_command",
        "default_import_path",
        "default_import_path_various",
        "more_import_paths",
        "import_scan_max_paths",
        "id3v1",
        "transcoder_cache",
        "transcoder_cache_size",
    ],
):
    match setting:
        case "library":
            path_completer = PathCompleter()
            new_library = prompt("Location/path of the music library: ", completer=path_completer, default=str(ctx.config.library))
            set_library(ctx, new_library)
        case "path_compatibility":
            options = [(opt, opt.value) for opt in PathCompatibilityOption]
            option = choice(message="select file system compatibility level", options=options, default=ctx.config.path_compatibility.value)
            ctx.config.path_compatibility = PathCompatibilityOption(option)
            db_config.save(ctx.db, ctx.config)
        case "path_replace_slash":
            ctx.config.path_replace_slash = prompt("Replace slash '/' character in path element with: ", default=ctx.config.path_replace_slash)
            db_config.save(ctx.db, ctx.config)
        case "path_replace_invalid":
            ctx.config.path_replace_invalid = prompt("Replace invalid character in path or filename with: ", default=ctx.config.path_replace_invalid)
            db_config.save(ctx.db, ctx.config)
        case "rescan":
            options = [(opt, opt.value) for opt in RescanOption]
            option = choice(message="select when to rescan the library", options=options, default=ctx.config.rescan.value)
            ctx.config.rescan = RescanOption(option)
            db_config.save(ctx.db, ctx.config)
        case "tagger":
            ctx.config.tagger = prompt("Command to run external tagger: ", default=ctx.config.tagger)
            db_config.save(ctx.db, ctx.config)
        case "open_folder_command":
            ctx.config.open_folder_command = prompt("Command to open a folder: ", default=ctx.config.open_folder_command)
            db_config.save(ctx.db, ctx.config)
        case "default_import_path":
            show_template_path_help(ctx)
            ctx.config.default_import_path = Template(
                prompt("Template for default (not compilation) import path: ", default=ctx.config.default_import_path.template)
            )
            db_config.save(ctx.db, ctx.config)
        case "default_import_path_various":
            show_template_path_help(ctx)
            ctx.config.default_import_path_various = Template(
                prompt("Template for compilation import path: ", default=ctx.config.default_import_path_various.template)
            )
            db_config.save(ctx.db, ctx.config)
        case "more_import_paths":
            show_template_path_help(ctx)
            default_str = ",".join(t.template for t in ctx.config.more_import_paths)
            more_paths = prompt("Enter more import path templates separated by comma: ", default=default_str)
            ctx.config.more_import_paths = [Template(path.strip()) for path in more_paths.split(",")]
            db_config.save(ctx.db, ctx.config)
        case "import_scan_max_paths":
            while not str.isdecimal(
                max_paths := prompt("Maximum number of paths to scan for import command: ", default=str(ctx.config.import_scan_max_paths))
            ):
                pass
            ctx.config.import_scan_max_paths = int(max_paths)
            db_config.save(ctx.db, ctx.config)
        case "id3v1":
            options = [(opt, opt.name) for opt in ID3v1Policy]
            option = choice(
                message="(MP3 only) ID3 version 2 tags are always used. What to do with ID3 version 1 tags?",
                options=options,
                default=ctx.config.id3v1,
            )
            ctx.config.id3v1 = ID3v1Policy(option)
            db_config.save(ctx.db, ctx.config)
        case "transcoder_cache":
            path_completer = PathCompleter()
            cache = Path(prompt("Location/path for transcoder cache: ", completer=path_completer, default=str(ctx.config.transcoder_cache)))
            if cache.exists():
                if not cache.is_dir():
                    ctx.console.print("[bold red]Error: the specified path exists and is not a directory[/bold red]")
                    return
                if not (cache / "index.json").exists():
                    if not confirm("This destination already exists. Any files here may be deleted! Are you sure you want to use this path?"):
                        return
            elif not cache.parent.exists():
                ctx.console.print("[bold red]Error: The parent directory of the transcoder cache does not exist.[/bold red]")
                return
            ctx.config.transcoder_cache = Path(cache)
        case "transcoder_cache_size":
            gb = prompt("Transcoder cache soft limit in gigabytes: ", default=f"{ctx.config.transcoder_cache_size / pow(2, 30):.1f}")
            if not re.match("\\d+(\\.\\d+)?$", gb):
                ctx.console.print("[bold red]Error: Enter a number of gigabytes.[/bold red]")
                return
            ctx.config.transcoder_cache_size = int(float(gb) * pow(2, 30))
