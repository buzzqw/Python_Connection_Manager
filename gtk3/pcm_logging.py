import os
import logging
from logging.handlers import RotatingFileHandler

_logger_registry = {}
_initialized = False


def init_from_env():
    global _initialized
    if _initialized:
        return
    _initialized = True

    livello_nome = os.environ.get("PCM_LOG_LEVEL", None)
    livello = logging.INFO
    if livello_nome:
        try:
            livello = getattr(logging, livello_nome.upper())
        except AttributeError:
            livello = logging.INFO

    root = logging.getLogger("pcm")
    root.setLevel(livello)
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    log_dir = os.path.join(
        os.path.expanduser("~"), ".local", "share", "pcm"
    )
    os.makedirs(log_dir, mode=0o700, exist_ok=True)
    log_file = os.path.join(log_dir, "pcm.log")
    fh = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
    fh.setFormatter(fmt)
    fh.setLevel(livello)
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(livello)
    root.addHandler(sh)


def init_from_settings(settings):
    livello_nome = (
        os.environ.get("PCM_LOG_LEVEL")
        or settings.get("general", {}).get("log_level", "INFO")
    )
    livello = logging.INFO
    if livello_nome:
        try:
            livello = getattr(logging, livello_nome.upper())
        except AttributeError:
            livello = logging.INFO

    root = logging.getLogger("pcm")
    root.setLevel(livello)
    for h in root.handlers:
        h.setLevel(livello)


def get_logger(name):
    init_from_env()
    return logging.getLogger(f"pcm.{name}")


def get_log_dir():
    return os.path.join(os.path.expanduser("~"), ".local", "share", "pcm")
