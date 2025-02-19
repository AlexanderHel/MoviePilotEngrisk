import logging
from logging.handlers import RotatingFileHandler

import click

from app.core.config import settings

# logger
logger = logging.getLogger()
if settings.DEBUG:
    logger.setLevel(logging.DEBUG)
else:
    logger.setLevel(logging.INFO)

#  Creating terminal outputHandler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)

#  Creating file outputHandler
file_handler = RotatingFileHandler(filename=settings.LOG_PATH / 'moviepilot.log',
                                   mode='w',
                                   maxBytes=5 * 1024 * 1024,
                                   backupCount=3,
                                   encoding='utf-8')
file_handler.setLevel(logging.INFO)
level_name_colors = {
    logging.DEBUG: lambda level_name: click.style(str(level_name), fg="cyan"),
    logging.INFO: lambda level_name: click.style(str(level_name), fg="green"),
    logging.WARNING: lambda level_name: click.style(str(level_name), fg="yellow"),
    logging.ERROR: lambda level_name: click.style(str(level_name), fg="red"),
    logging.CRITICAL: lambda level_name: click.style(
        str(level_name), fg="bright_red"
    ),
}


#  Defining the log output format
class CustomFormatter(logging.Formatter):
    def format(self, record):
        seperator = " " * (8 - len(record.levelname))
        record.leveltext = level_name_colors[record.levelno](record.levelname + ":") + seperator
        return super().format(record)


#  Terminal log
console_formatter = CustomFormatter("%(leveltext)s%(filename)s - %(message)s")
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

#  File log
file_formater = CustomFormatter("【%(levelname)s】%(asctime)s - %(filename)s - %(message)s")
file_handler.setFormatter(file_formater)
logger.addHandler(file_handler)
