from prompt_toolkit.shortcuts import confirm
from sqlalchemy.orm import Session

import albums.cli.click_rich as click
from albums.app import Context
from albums.checks.all import ALL_CHECK_NAMES, check_run_order, implicitly_ignored_checks, transitive_dependencies
from albums.checks.helpers import album_display_name
from albums.words import pluralize

from .cli_context import pass_context, require_configured, require_persistent_context


@click.command("notice", help="selected albums stop ignoring specified checks", add_help_option=False)
@click.option("--force", "-f", is_flag=True, help="always skip confirmation")  # pyright: ignore[reportUnknownMemberType]
@click.argument("check_names", nargs=-1)  # pyright: ignore[reportUnknownMemberType]
@click.help_option("--help", "-h", help="show this message and exit")  # pyright: ignore[reportUnknownMemberType]
@pass_context
def checks_notice(ctx: Context, force: bool, check_names: list[str]):
    require_configured(ctx)
    require_persistent_context(ctx)
    with Session(ctx.db) as session:
        for album in ctx.select_album_entities(session):
            changed = False
            error = False
            for target_check in check_names:
                if target_check not in ALL_CHECK_NAMES:
                    ctx.console.print(f'"{target_check}" is not a valid check name. See [bold]albums check --help[/bold]')
                    error = True
                if target_check in album.ignore_checks:
                    album.ignore_checks.remove(target_check)
                    ctx.console.print(f"album {album_display_name(ctx, album)} will stop ignoring {target_check}")
                    changed = True
                elif ctx.is_filtered:  # don't show individual albums if operating on all albums (confirm below)
                    if target_check in implicitly_ignored_checks(set(album.ignore_checks)):
                        ignored_dependencies = [
                            f'"{name}"' for name in check_run_order(transitive_dependencies(target_check) & set(album.ignore_checks))
                        ]
                        ctx.console.print(
                            f"album {album_display_name(ctx, album)} does not explicitly ignore {target_check}: it is implicitly ignored because it depends on ignored {pluralize('check', ignored_dependencies)} {' and '.join(ignored_dependencies)}"
                        )
                    else:
                        ctx.console.print(f"album {album_display_name(ctx, album)} does not ignore {target_check}")

            if changed and not error:
                if force or ctx.is_filtered or confirm(f"stop ignoring {pluralize('check', check_names)} {', '.join(check_names)} for all albums?"):
                    session.commit()
            elif not error and ctx.is_filtered:
                ctx.console.print(f"no changes to album {album_display_name(ctx, album)}")
            elif error:
                ctx.console.print("changes not saved because some options were invalid")
