from typing import Final, Tuple

from mutagen._vorbis import VCommentDict

from .types import BasicTag

LEGACY_VORBIS_TAGS: Final[Tuple[Tuple[str, BasicTag], ...]] = (
    ("album artist", BasicTag.ALBUMARTIST),
    ("label", BasicTag.ORGANIZATION),
    ("publisher", BasicTag.ORGANIZATION),
    ("totaldiscs", BasicTag.DISCTOTAL),
)


def vorbis_comment_tags(file_tags: VCommentDict) -> Tuple[Tuple[Tuple[BasicTag, Tuple[str, ...]], ...], Tuple[Tuple[str, BasicTag], ...]]:
    # Use dict to track tags by BasicTag with list of values (for easy deduplication)
    tags: dict[BasicTag, list[str]] = {}

    # Process standard tags
    for tag in BasicTag:
        if tag != BasicTag.UNKNOWN and tag.value in file_tags:
            tags[tag] = [str(value) for value in file_tags[tag.value]]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]

    # Process legacy tags
    legacy_tags: list[tuple[str, BasicTag]] = []
    for legacy_name, basic_tag in LEGACY_VORBIS_TAGS:
        if legacy_name in file_tags:
            legacy_tags.append((legacy_name, basic_tag))
            # Also add to main tags list with the corresponding BasicTag, avoiding duplicates
            values = [str(value) for value in file_tags[legacy_name]]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
            if basic_tag in tags:
                # Extend existing values with non-duplicate new values
                for value in values:
                    if value not in tags[basic_tag]:
                        tags[basic_tag].append(value)
            else:
                # Add new tag with its values
                tags[basic_tag] = list(values)

    tags_flat = ((basic_tag, tuple(values)) for basic_tag, values in tags.items())

    # Basic tags as first item of tuple, legacy tags as second item
    return (tuple(tags_flat), tuple(legacy_tags))


def vorbis_comment_set_tag(file_tags: VCommentDict, tag: BasicTag, value: str | list[str] | None):
    if value is None:
        if tag != BasicTag.UNKNOWN and tag.value in file_tags:
            del file_tags[tag.value]
    else:
        value_list = value if isinstance(value, list) else [value]
        match tag:
            case BasicTag.UNKNOWN:
                raise ValueError("cannot set tag value UNKNOWN")
            case BasicTag.COMPILATION:
                if value_list and value_list[0]:
                    file_tags[tag.value] = ["1"]
                elif tag.value in file_tags:
                    del file_tags[tag.value]
            case _:
                file_tags[tag.value] = value_list
