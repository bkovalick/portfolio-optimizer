import logging
import sys

LOG_FILE = "app.log"
LOG_FORMAT = "%(asctime)s  %(name)-30s  %(levelname)-8s  %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configures the root logger with a file handler (INFO+) and a console
    handler (WARNING+). Call once at application startup.
    """
    root = logging.getLogger()
    if root.handlers:
        return  # already configured; avoid duplicate handlers on reload

    root.setLevel(level)

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.WARNING)
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)
