# albums

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/4levity/albums/publish.yml?branch=main&event=push&label=publish)
![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/4levity/albums/docs.yml?branch=main&event=push&label=docs)
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=fff)
![PyPI - Version](https://img.shields.io/pypi/v/albums)
![PyPI - Status](https://img.shields.io/pypi/status/albums)
[![Buy Me a Coffee](https://img.shields.io/badge/donate-bb6600?&logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/4levity)

Manage a library of music: validate and fix tags and metadata, rename files,
adjust and embed album art, clean up and import albums, and sync parts of the
library to digital audio players or portable storage

- [Read the documentation](https://4levity.github.io/albums/)
- [Watch a video about how to use albums](https://www.youtube.com/watch?v=B5tBG_GaG7A)

## Overview

`albums` works with media files and tags, but primarily acts on "albums" rather
than individual files. Everything is done locally and an Internet connection is
not required (although it can be configured to use an external tool to download
cover art). It's a command-line app but it is designed to be user friendly, with
interactive menus, rich text formatting, tables and even blocky graphics.

It can work with a single folder or scan a whole media library into its database
to make subsequent operations fast. It has
[many automated checks and fixes](https://4levity.github.io/albums/all_checks/)
for metadata related issues such as track numbering (sequence, totals, disc
numbers), album-artist tags, embedding cover art, etc. It supports marking
albums as part of "collections," for example to make a list of albums to sync to
a digital audio player. It can also perform the sync.

## Why use `albums` instead of other music library tools?

Use them all, you don't have to decide. If you have missing metadata or
unidentified recordings and you want to use online databases to fill in the
blanks, [Beets](https://beets.io/) does that, and has some command line and
library management features similar to `albums`.
[MusicBrainz Picard](https://picard.musicbrainz.org/) does too. For manually
editing tags in a GUI with some fancy features and automation,
[puddletag](https://docs.puddletag.net/#) and
[MP3TAG](https://www.mp3tag.de/en/index.html) (proprietary but no cost for
Windows version) are nice, while [EasyTAG](https://wiki.gnome.org/Apps/EasyTAG)
is simple and quick.

`albums` is a little different. It works offline without external databases. It
uses a series of independent, configurable checks and automated fixes for basic
tags, cover art and filenames. You can review every change, or only the ones
that require your choice. It also reports on some problems it can't fix, like
missing tracks on an album. `albums` can help clean up and import new albums
into your library and keep digital audio players synced. Its CLI plus JSON and
SQL interfaces may enable some automation.

## Supported Media

**FLAC**, **Ogg Vorbis**, **MP3/ID3**, **M4A**, **ASF/WMA** and **AIFF**
containers/types are supported with standard tags. **ASF/WMA** embedded image
support is read-only. Image files (PNG, JPEG, GIF, BMP, WEBP, TIFF, etc) in the
album folder are scanned and can be automatically converted and embedded.

More formats and tag comprehension will likely be added if requested.

## System Requirements

Installation via pipx requires Python 3.12+ and should work on almost any 64-bit
x86 or ARM system with Linux, macOS or Windows.

Binary releases for 64-bit Linux or Windows do not have any Python requirement.

Albums is primarily tested on Linux and Windows.
