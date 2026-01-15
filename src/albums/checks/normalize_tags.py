def normalized(source_tags: dict[str, list[str]]):
    """
    Returns a copy of a file's tags normalized to allow similar content checks across file formats.

    :param source_tags: the actual tags
    :type source_tags: dict[str, list[str]]
    """
    tags = source_tags.copy()

    # extract tracktotal from ID3 tags
    tracknumber_tag = tags.get("tracknumber", [None])[0]
    if tracknumber_tag and "tracktotal" not in tags and str.count(tracknumber_tag, "/") == 1:
        [tracknumber, tracktotal] = tags["tracknumber"].split("/")
        tags["tracknumber"] = [tracknumber]
        tags["tracktotal"] = [tracktotal]

    return tags
