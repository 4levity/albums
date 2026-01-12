import json
import logging
from pathlib import Path
import subprocess
import sys


logger = logging.getLogger(__name__)


METADATA_TOOL_NAME = "exiftool"


def check_metadata_tool():
    try:
        process = subprocess.Popen(args=[METADATA_TOOL_NAME, "-ver"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError:
        logger.error(f"{METADATA_TOOL_NAME} is not available")
        sys.exit(1)

    stdout, stderr = process.communicate()
    if stderr:
        logger.error(f"{METADATA_TOOL_NAME} error: {stderr}")
        sys.exit(1)
    return f"{METADATA_TOOL_NAME} version {stdout.strip()}"


def get_exif_data(cwd: str, filepaths: list[str]):
    args = [
        METADATA_TOOL_NAME,
        "-q",  # no status output
        "-j",  # json to stdout
        "-FileSize#",  # specify file size in bytes
        "-All",  # include all metadata except fields excluded below
        "--FileName",
        "--FileInodeChangeDate",
        "--FileModifyDate",
        "--Directory",
        "--FileAccessDate",
        "--FilePermissions",
        "--Directory",
        "--FileTypeExtension",
        "--MIMEType",
        "--BlockSizeMin",
        "--BlockSizeMax",
        "--FrameSizeMin",
        "--FrameSizeMax",
        "--TotalSamples",
        "--MD5Signature",
        "--Vendor",
        "--MPEGAudioVersion",
        "--AudioLayer",
        "--ChannelMode",
        "--MSStereo",
        "--IntensityStereo",
        "--CopyrightFlag",
        "--OriginalMedia",
        "--Emphasis",
        "--ID3Size",
    ]
    args.extend(filepaths)
    process = subprocess.Popen(args=args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=cwd)
    stdout, stderr = process.communicate()

    if stderr:
        logger.error(f"{METADATA_TOOL_NAME} error: {stderr}")
        sys.exit(1)
    return json.loads(stdout)


def with_track_metadata(library_root: Path, album: dict):
    metadata = get_exif_data(library_root / album["path"], [track["source_file"] for track in album["tracks"]])
    if len(album["tracks"]) == len(metadata):
        for index, track in enumerate(album["tracks"]):
            if track["source_file"] == metadata[index]["SourceFile"]:
                album["tracks"][index]["metadata"] = metadata[index]
            else:
                logger.warning(
                    f"track metadata out of order at index {index}: {track['source_file']} != {metadata[index]['source_file']} -- in album {album['path']}"
                )
    else:
        logger.warning(f"track count {len(album['tracks'])} does not match metadata count {len(metadata)} for album {album['path']}")
    return album
