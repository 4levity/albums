"""Exceptions for long-running operations (scan, check, import, sync, configuration changes).

Operation code raises these instead of ``SystemExit`` so a frontend can handle the outcome
per-operation: the one-shot CLI converts them at its entry point into the usual "print the
message and exit non-zero" behavior, while a TUI catches them around a single operation,
reports the message, and stays running.
"""


class OperationError(Exception):
    """An operation failed; the exception message is the user-facing explanation.

    The message may contain rich markup; a frontend that prints it as plain text should strip
    it, and any path or other dynamic value embedded in a message must be escaped
    (``rich.markup.escape``).
    """


class OperationCancelled(OperationError):
    """The user cancelled the operation (refused a confirmation or interrupted it).

    Completed work has been committed, so the state is consistent and the frontend may
    simply report the cancellation and continue.
    """


class QuitApp(Exception):
    """The user asked to quit the whole application, not just the current operation.

    Deliberately not an :class:`OperationError`, so per-operation handlers must not catch
    it; it propagates to the application's main loop (e.g. a TUI), which performs any final
    cleanup and exits.
    """
