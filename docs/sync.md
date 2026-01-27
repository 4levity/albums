---
icon: lucide/arrow-big-right-dash
---

# Synchronize

The `albums sync` command will copy some or all of the configured music library
to another location. Only files that have been updated are copied. This enables
updating portable collections and digital audio players as long as they can be
accessed by the operating system like a regular storage device.

> Only music files that `albums` knows about are copied. If there are other
> files in the library album directory, `sync` ignores them!

## Use a collection

`albums` can associate specific albums with "collection" tags (see
[Usage](./usage.md)). A collection could define a subset of the library to copy
to a digital audio player, phone or memory card. The command
`albums --collection top100 sync <destination>` would copy all albums in the
"top100" collection to the destination.

## Sync and delete

If albums are removed from the collection, or folders/files are renamed, running
another sync to the same destination could leave unwanted or duplicate files.
Alternatively, the `--delete` option and `albums` will **delete every file in
the destination that is not being synced!** This is good if the destination is,
for example, a folder on a memory card for a digital audio player, which doesn't
contain any other data, and `albums sync` will manage everything there.
