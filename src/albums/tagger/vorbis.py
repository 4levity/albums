from typing import Final, Tuple

from mutagen._vorbis import VCommentDict

from .types import BasicField

# Mapping of legacy Vorbis comment names to their canonical BasicField equivalents
LEGACY_VORBIS_FIELDS: Final[Tuple[Tuple[str, BasicField], ...]] = (
    ("album artist", BasicField.ALBUMARTIST),
    ("disc number", BasicField.DISCNUMBER),
    ("totaldiscs", BasicField.DISCTOTAL),
    ("label", BasicField.ORGANIZATION),
    ("publisher", BasicField.ORGANIZATION),
    ("track number", BasicField.TRACKNUMBER),
    ("numtracks", BasicField.TRACKTOTAL),
    ("number_of_tracks", BasicField.TRACKTOTAL),
    ("totaltracks", BasicField.TRACKTOTAL),
)


def vorbis_comment_legacy_fields(file_tags: VCommentDict) -> Tuple[Tuple[str, BasicField], ...]:
    legacy_tags: list[tuple[str, BasicField]] = []
    for legacy_name, basic_tag in LEGACY_VORBIS_FIELDS:
        if legacy_name in file_tags:
            legacy_tags.append((legacy_name, basic_tag))
    # Basic tags as first item of tuple, legacy tags as second item
    return tuple(legacy_tags)


def vorbis_comment_fields(file_tags: VCommentDict) -> Tuple[Tuple[BasicField, Tuple[str, ...]], ...]:
    # Use dict to track tags by BasicField with list of values (for easy deduplication)
    fields: dict[BasicField, list[str]] = {}

    # Process standard tags
    for field in BasicField:
        if field != BasicField.UNKNOWN and field.value in file_tags:
            fields[field] = [str(value) for value in file_tags[field.value]]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]

    # Read values from legacy tags if present
    for legacy_name, basic_field in vorbis_comment_legacy_fields(file_tags):
        values = [str(value) for value in file_tags[legacy_name]]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
        if basic_field in fields:
            # Extend existing values with non-duplicate new values
            for value in values:
                if value not in fields[basic_field]:
                    fields[basic_field].append(value)
        else:
            # Add new tag with its values
            fields[basic_field] = list(values)

    fields_flat = ((basic_field, tuple(values)) for basic_field, values in fields.items())

    # Basic tags as first item of tuple, legacy tags as second item
    return tuple(fields_flat)


def vorbis_comment_set_field(file_fields: VCommentDict, field: BasicField | str, value: str | list[str] | None):
    field_name = field.value if isinstance(field, BasicField) else field
    if value is None:
        if field != BasicField.UNKNOWN and field_name in file_fields:
            del file_fields[field_name]
    else:
        value_list = value if isinstance(value, list) else [value]
        match field:
            case BasicField.UNKNOWN:
                raise ValueError("cannot set tag value UNKNOWN")
            case BasicField.COMPILATION:
                if value_list and value_list[0]:
                    file_fields[field_name] = ["1"]
                elif field_name in file_fields:
                    del file_fields[field_name]
            case _:
                file_fields[field_name] = value_list
