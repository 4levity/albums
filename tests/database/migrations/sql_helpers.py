def make_track_sql(album_id: int = 1, filename: str = "1.flac") -> str:
    """Generate SQL to insert a track row."""
    return (
        f"INSERT INTO track (album_id, filename, file_size, modify_timestamp, stream_bitrate, "
        f"stream_channels, stream_codec, stream_length, stream_sample_rate, stream_error, stream_bits_per_sample) "
        f"VALUES ({album_id}, '{filename}', 0, 0, 0, 0, '', 0, 0, '', 0);"
    )


def split_sql_statements(sql: str) -> list[str]:
    """Split migration SQL into individual statements, ignoring comment lines."""
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    return [statement.strip() for statement in "\n".join(lines).split(";") if statement.strip()]
