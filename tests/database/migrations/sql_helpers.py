def make_track_sql(album_id: int = 1, filename: str = "1.flac") -> str:
    """Generate SQL to insert a track row."""
    return (
        f"INSERT INTO track (album_id, filename, file_size, modify_timestamp, stream_bitrate, "
        f"stream_channels, stream_codec, stream_length, stream_sample_rate, stream_error, stream_bits_per_sample) "
        f"VALUES ({album_id}, '{filename}', 0, 0, 0, 0, '', 0, 0, '', 0);"
    )
