"""Application configuration types, defaults and serialization logic.

Configuration values are persisted to the SQLite database as JSON-encoded rows
in the ``setting`` table and reloaded into a ``Configuration`` dataclass at startup.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import StrEnum, auto
from pathlib import Path
from string import Template
from typing import Dict, Final, Iterator, List, Mapping, Sequence, Tuple, Union

from platformdirs import PlatformDirs
from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from albums.tagger import ID3v1Policy

from .checks.check_types import CheckConfiguration
from .database.orm import Base, SerializableValueAsJson

logger: Final = logging.getLogger(__name__)

# OS-specific directories for storing application data and caches.
PLATFORM_DIRS: Final = PlatformDirs("albums", "4levity")


type SerializedSyncDestination = dict[str, Union[str, int, float, bool, Sequence[str]]]
type SettingValueType = Union[str, int, float, bool, Sequence[str], Sequence[SerializedSyncDestination]]


class SettingEntity(Base):
    """SQLAlchemy model mapping to the ``setting`` table.

    Each row stores one configuration item keyed by a dotted ``section.name`` string.

    Attributes:
        name: Configuration key in ``"section.option"`` format (primary key).
        value: JSON-serializable setting value. The raw type is stored as-is for simple scalars,
               complex structures are round-tripped through the :class:`~.orm.SerializableValueAsJson` type.
    """

    __tablename__ = "setting"

    name: Mapped[str] = mapped_column(Text, nullable=False, primary_key=True)
    value: Mapped[SettingValueType] = mapped_column("value_json", SerializableValueAsJson[SettingValueType], nullable=False)


class PathCompatibilityOption(StrEnum):
    """Target platform restrictions applied when constructing safe file/folder names.

    Choosing a stricter target (e.g. ``WINDOWS``) prevents generation path components that
    would be rejected by that OS's filesystem rules.
    """

    LINUX = "Linux"
    WINDOWS = "Windows"
    MACOS = "macOS"
    POSIX = "POSIX"
    UNIVERSAL = "universal"


class RescanOption(StrEnum):
    """Policy controlling automatic library re-scans when albums change.

    Values correspond to CLI ``--rescan`` argument choices and are persisted in settings.
    """

    ALWAYS = auto()
    NEVER = auto()
    AUTO = auto()


# Default directory structure template applied when importing music into the library via ``albums import``.
DEFAULT_IMPORT_PATH: Final = Template("$artist/$album")

# Default directory structure for compilation albums where there is no single artist.
DEFAULT_IMPORT_PATH_VARIOUS: Final = Template("Compilations/$album")

# Additional import path template options to present by default.
DEFAULT_MORE_IMPORT_PATHS: Final = (Template("$A1/$artist/$album"), Template("Soundtracks/$album"))

# Maximum number of directories scanned during ``import --scan`` before proceeding to import.
DEFAULT_IMPORT_SCAN_MAX_PATHS: Final = 250


def default_checks_config() -> Mapping[str, CheckConfiguration]:
    """Return a fresh dict of factory-default check configurations keyed by check name.

    Returns:
        A mapping from each registered check's ``name`` to a mutable copy of its default config dict.
    """
    from .checks.all import ALL_CHECKS  # local import because .checks.all imports every check, which will import this module

    return dict((check.name, check.default_config.copy()) for check in ALL_CHECKS)


# Audio file conversion profile used by default when syncing to destinations that require transcoding.
DEFAULT_FILE_CONVERT_PROFILE: Final = "mp3"

# Marker string placed in UI lists to signify the "no-collection" option (all albums).
ALL_ALBUMS = "< use all albums >"


@dataclass
class SyncDestination:
    """Describes a single device or folder that library albums can be synced to.

    When syncing, albums belonging to the specified collection are copied into
    *path_root* using either *relpath_template_artist* or *relpath_template_compilation*.
    Files may be transcoded based on the provided profile and technical caps.

    Attributes:
        collection: Collection name whose albums populate this destination (``ALL_ALBUMS`` for everything).
        path_root: Root filesystem path where synced files are written.
        relpath_template_artist: Path template for artist albums; supports ``$artist``, ``$album``, etc.
        relpath_template_compilation: Path template for compilation albums with multiple artists.
        allow_file_types: Whitelist of audio file extensions to include (empty accepts all supported types).
        convert_profile: Transcoding profile identifier for the destination player or device.
        max_kbps: Target bitrate cap in kilobits per second (0 = no limit).
        max_sample_rate: Target sample rate cap in Hz (0 = no limit).
        max_bits_per_sample: Target sample depth cap (0 = no limit).
    """

    collection: str
    path_root: Path
    relpath_template_artist: Template = Template("")
    relpath_template_compilation: Template = Template("")
    allow_file_types: List[str] = field(default_factory=list[str])
    convert_profile: str = DEFAULT_FILE_CONVERT_PROFILE
    max_kbps: int = 0
    max_sample_rate: int = 0
    max_bits_per_sample: int = 0

    def __str__(self) -> str:
        return f"sync {self.collection or 'all albums'} -> {self.path_root}"

    def __lt__(self, other: SyncDestination) -> bool:
        return self.collection < other.collection or (self.collection == other.collection and str(self.path_root) < str(other.path_root))

    def to_dict(self) -> SerializedSyncDestination:
        """Serialize the destination into a JSON-safe dictionary for database storage.

        Returns:
            A dict suitable for inclusion in ``SerializedSyncDestination`` lists.
        """
        return {
            "collection": self.collection,
            "path_root": str(self.path_root),
            "relpath_template_artist": self.relpath_template_artist.template,
            "relpath_template_compilation": self.relpath_template_compilation.template,
            "allow_file_types": self.allow_file_types,
            "convert_profile": self.convert_profile,
            "max_kbps": self.max_kbps,
            "max_sample_rate": self.max_sample_rate,
            "max_bits_per_sample": self.max_bits_per_sample,
        }

    @classmethod
    def from_dict(cls, values: SerializedSyncDestination) -> SyncDestination:  # noqa: ANN102
        """Construct a ``SyncDestination`` from JSON-serializable data loaded from the database.

        Args:
            values: Dict previously produced by :meth:`to_dict` or equivalent structure.

        Returns:
            A fully initialized sync destination instance.
        """
        return SyncDestination(
            str(values["collection"]),
            Path(str(values["path_root"])),
            Template(str(values.get("relpath_template_artist", ""))),
            Template(str(values.get("relpath_template_compilation", ""))),
            values["allow_file_types"] if ("allow_file_types" in values and isinstance(values["allow_file_types"], list)) else [],
            str(values.get("convert_profile", DEFAULT_FILE_CONVERT_PROFILE)),
            int(str(values.get("max_kbps", 0))),
            int(str(values.get("max_sample_rate", 0))),
            int(str(values.get("max_bits_per_sample", 0))),
        )


@dataclass
class Configuration:
    """In-memory representation of user-facing application configuration.

    Attributes:
        checks: Per-check tuning options keyed by check name.
        default_import_path: Path template for new artist albums when using ``albums import``.
        default_import_path_various: Path template for compilation albums during import.
        more_import_paths: Extra path template options shown to user when importing.
        import_scan_max_paths: Limit on directories explored by ``import`` scan.
        library: Root directory scanned and managed as the music library.
        transcoder_cache: On-disk folder caching transcoded audio files to avoid repeated work.
        transcoder_cache_size: Maximum cache size in bytes (default 16 GiB).
        open_folder_command: Shell command to run to open a file manager on a folder.
        path_compatibility: Filesystem character restrictions applied to generated filenames.
        path_replace_slash: Replacement character used for ``/`` and ``\\`` in folder names.
        path_replace_invalid: Replacement substring for other filesystem-illegal characters (empty to strip).
        rescan: Automatic scan policy whenever a command is about to be invoked.
        tagger: Shell command to invoke to run an external tagger on a folder.
        id3v1: Policy for legacy ID3v1 tags when saving MP3 files.
        sync_destinations: Destination folders to which albums can be synced.
    """

    checks: Mapping[str, CheckConfiguration] = field(default_factory=default_checks_config)
    default_import_path: Template = DEFAULT_IMPORT_PATH
    default_import_path_various: Template = DEFAULT_IMPORT_PATH_VARIOUS
    more_import_paths: Sequence[Template] = DEFAULT_MORE_IMPORT_PATHS
    import_scan_max_paths: int = DEFAULT_IMPORT_SCAN_MAX_PATHS
    library: Path = Path(".")
    transcoder_cache: Path = PLATFORM_DIRS.user_data_path / "albums_transcoder_cache"
    transcoder_cache_size: int = 16 * pow(2, 30)  # 16 GiB
    open_folder_command: str = ""
    path_compatibility: PathCompatibilityOption = PathCompatibilityOption.UNIVERSAL
    path_replace_slash = "-"
    path_replace_invalid = ""
    rescan: RescanOption = RescanOption.AUTO
    tagger: str = ""
    id3v1: ID3v1Policy = ID3v1Policy.UPDATE
    sync_destinations: List[SyncDestination] = field(default_factory=list[SyncDestination])

    def to_values(self) -> Mapping[str, SettingValueType]:
        """Serialize configuration into a flat dict of dotted keys for database storage.

        Returns:
            A mapping of ``"section.option"`` keys to serializable values ready for insertion
            into the ``setting`` table via ``SettingEntity`` rows.

        Raises:
            ValueError: If *checks* contains an unknown check name or a setting with a type mismatch.
        """
        values: Dict[str, SettingValueType] = {
            "settings.default_import_path": self.default_import_path.template,
            "settings.default_import_path_various": self.default_import_path_various.template,
            "settings.more_import_paths": [path_T.template for path_T in self.more_import_paths],
            "settings.import_scan_max_paths": self.import_scan_max_paths,
            "settings.library": str(self.library),
            "settings.transcoder_cache": str(self.transcoder_cache),
            "settings.transcoder_cache_size": self.transcoder_cache_size,
            "settings.open_folder_command": self.open_folder_command,
            "settings.path_compatibility": self.path_compatibility.value,
            "settings.path_replace_invalid": str(self.path_replace_invalid),
            "settings.path_replace_slash": str(self.path_replace_slash),
            "settings.rescan": str(self.rescan),
            "settings.tagger": self.tagger,
            "settings.id3v1": self.id3v1.value,
            "settings.sync_destinations": [dest.to_dict() for dest in self.sync_destinations],
        }
        defaults = default_checks_config()
        for check_name, check_config in self.checks.items():
            for name, value in check_config.items():
                if check_name not in defaults or name not in defaults[check_name]:
                    raise ValueError(f"can't save unknown check configuration {check_name}.{name}")
                if type(value) is not type(defaults[check_name][name]):
                    raise ValueError(
                        f"can't save {check_name}.{name} because wrong data type {type(value)} (expected {type(defaults[check_name][name])})"
                    )
                values[f"{check_name}.{name}"] = value
        return values

    @classmethod
    def from_values(cls, values: Iterator[Tuple[str, SettingValueType]]) -> tuple[Configuration, bool]:
        """Reconstruct application configuration from raw database ``setting`` rows.

        Settings with unexpected keys or type mismatches are logged as warnings and ignored
        so that older or corrupted databases do not crash the app on load.

        Args:
            values: Iterable of ``(key, value)`` pairs where *key* is a dotted configuration name.

        Returns:
            A two-element tuple containing the populated ``Configuration`` object and a boolean flag
            indicating whether any database rows were skipped due to validation failures.
        """
        config = Configuration()
        ignored_values = False
        for k, value in values:
            tokens = k.split(".")
            if len(tokens) != 2:
                logger.warning(f"ignoring invalid configuration key {k} (expected section.name)")
                ignored_values = True
                continue
            [section, name] = tokens
            if section == "settings":
                # TODO validate templates when loaded from DB
                if name == "default_import_path":
                    config.default_import_path = Template(str(value))
                elif name == "default_import_path_various":
                    config.default_import_path_various = Template(str(value))
                elif name == "more_import_paths":
                    if isinstance(value, list) and all(isinstance(item, str) for item in value):
                        config.more_import_paths = tuple(Template(v) for v in value)  # pyright: ignore[reportArgumentType]
                    else:
                        logger.warning(f"ignoring {k}={str(value)}, not a list of strings - using default {json.dumps(config.more_import_paths)}")
                        ignored_values = True
                elif name == "import_scan_max_paths":
                    max_paths = str(value)
                    if str.isdecimal(max_paths):
                        config.import_scan_max_paths = int(max_paths)
                    else:
                        logger.warning(f"ignoring {k}={max_paths}, not a number - using default {config.import_scan_max_paths}")
                        ignored_values = True
                elif name == "library":
                    config.library = Path(str(value))
                elif name == "transcoder_cache":
                    config.transcoder_cache = Path(str(value))
                elif name == "transcoder_cache_size":
                    config.transcoder_cache_size = int(str(value))
                elif name == "open_folder_command":
                    config.open_folder_command = str(value)
                elif name == "path_compatibility":
                    config.path_compatibility = PathCompatibilityOption(value)
                elif name == "path_replace_invalid":
                    config.path_replace_invalid = str(value)
                elif name == "path_replace_slash":
                    config.path_replace_slash = str(value)
                elif name == "rescan":
                    config.rescan = RescanOption(value)
                elif name == "tagger":
                    config.tagger = str(value)
                elif name == "id3v1":
                    config.id3v1 = ID3v1Policy(value)
                elif name == "sync_destinations":
                    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
                        config.sync_destinations = [SyncDestination.from_dict(dest) for dest in value]  # pyright: ignore[reportArgumentType]
                    else:
                        logger.warning(f"ignoring {k}={str(value)}, not a list of sync destination dictionaries")
                        ignored_values = True
                else:
                    logger.warning(f"ignoring unknown configuration item {k} = {str(value)}")
                    ignored_values = True
            else:
                if section not in config.checks or name not in config.checks[section]:
                    logger.warning(f"ignoring unknown configuration item {k} = {str(value)}")
                    ignored_values = True
                elif type(value) is not type(config.checks[section][name]):
                    logger.warning(f"ignoring configuration item {k} with wrong type {type(value)} (expected {type(config.checks[section][name])})")
                    ignored_values = True
                elif not isinstance(value, list) or all(isinstance(item, str) for item in value):
                    config.checks[section][name] = value  # pyright: ignore[reportArgumentType]
        return (config, ignored_values)
