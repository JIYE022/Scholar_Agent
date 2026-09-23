# set global timezone
import time

if hasattr(time, "tzset"):
    time.tzset()

from .get_logger import get_logger
logger = get_logger()
