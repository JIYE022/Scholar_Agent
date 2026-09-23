import logging
import colorlog
import os
from logging.handlers import RotatingFileHandler


def get_logger():

    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'DEFAULT')

    #########################
    ## color logger define ##
    #########################

    log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "backend.log")

    # Logger instance
    logger = colorlog.getLogger(__name__)
    if logger.handlers:
        return logger

    stream_handler = colorlog.StreamHandler()
    stream_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(asctime)s.%(msecs)03d - %(levelname)s - [%(funcName)s] - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S',
        log_colors={
            'DEBUG': 'cyan',
            'INFO': 'green',
            'WARNING': 'yellow',
            'ERROR': 'red',
            'CRITICAL': 'red,bg_white',
        }
    )
    stream_handler.setFormatter(stream_formatter)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(levelname)s - [%(funcName)s] - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    logger.propagate = False

    # Logger level
    LOG_LEVEL_OPTION = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL,
        'DEFAULT': logging.INFO
    }
    logger.setLevel(LOG_LEVEL_OPTION.get(LOG_LEVEL.upper(), 'DEFAULT'))

    return logger
