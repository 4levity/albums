from typing import Mapping


def generate_check_renames_sql(renames: Mapping[str, str]) -> str:
    """Generate SQL to rename multiple checks in a single migration.

    Updates both the album_ignore_check table and the setting table (configuration keys).

    Args:
        renames: Mapping from old check names to new check names.

    Returns:
        SQL statement string containing all rename operations.
    """
    if not renames:
        raise ValueError("no renames specified")

    # Generate CASE statement for album_ignore_check for efficiency
    return (
        "UPDATE album_ignore_check SET check_name = CASE check_name\n"
        + "\n".join(f"    WHEN '{old_name}' THEN '{new_name}'" for old_name, new_name in renames.items())
        + "\n"
        + "END\n"
        + f"WHERE {' OR '.join(f"check_name = '{name}'" for name in renames.keys())};\n"
        + "\n".join(
            f"UPDATE setting SET name = REPLACE(name, '{old_name}.', '{new_name}.') WHERE name LIKE '{old_name}.%';"
            for old_name, new_name in renames.items()
        )
    )
