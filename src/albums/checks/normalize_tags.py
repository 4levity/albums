# TODO: we call this a lot, should cache or restructure
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
        tags[""] = tracknumber_tag
        [tracknumber, tracktotal] = tracknumber_tag.split("/")
        tags["tracknumber"] = [tracknumber]
        tags["tracktotal"] = [tracktotal]

    # extract disctotal from ID3 tags
    discnumber_tag = tags.get("discnumber", [None])[0]
    if discnumber_tag and "disctotal" not in tags and str.count(discnumber_tag, "/") == 1:
        tags["discnumber_original"] = tracknumber_tag
        [discnumber, disctotal] = discnumber_tag.split("/")
        tags["discnumber"] = [discnumber]
        tags["disctotal"] = [disctotal]

    return tags
