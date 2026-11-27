"""Terminal output of the data-collection tools: sharklog for events, one live status line under them.

    import log
    log.setup()                 # once, in main()
    sharklog.info("recording ...")     # anywhere: coloured level, time, file and line
    log.status("ENGAGED | REC #3 4.2 s | ...")   # the line that is rewritten in place

sharklog's handler is put on the root logger, so the messages of rebot_control and iMuninn come out in the same
form. A log message first wipes the status line and the next status() call draws it again, so the two do not run
into each other.
"""

from __future__ import annotations

import logging
import sys

import sharklog

_state = {'text': '', 'stream': sys.stderr, 'ready': False}


def setup(debug: bool = False) -> None:
    if _state['ready']:
        return
    root = sharklog.init(
        name='root',
        debug=debug,
        format='[%(levelname)s]: %(message)s [%(asctime)s](%(filename)s:%(lineno)d)',
        datefmt='%H:%M:%S',
    )
    handler = root.handlers[-1]
    _state['stream'] = handler.stream
    emit = handler.emit

    def emit_clear(record: logging.LogRecord) -> None:
        if _state['text']:
            handler.stream.write('\r\x1b[K')
            _state['text'] = ''
        emit(record)

    handler.emit = emit_clear
    logging.getLogger('imuninn').setLevel(logging.WARNING)  # its clock-sync lines would flood the screen
    _state['ready'] = True


def status(text: str) -> None:
    """Rewrite the status line (only when it changed)."""
    if text != _state['text']:
        stream = _state['stream']
        stream.write('\r\x1b[K' + text)
        stream.flush()
        _state['text'] = text


def end_status() -> None:
    """Leave the status line (before plain printing or at exit)."""
    if _state['text']:
        _state['stream'].write('\n')
        _state['stream'].flush()
        _state['text'] = ''
