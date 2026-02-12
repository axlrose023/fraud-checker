import logging
from typing import Literal

LOG_FORMAT_DEBUG = (
    "[%(levelname)7s]: %(name)s - %(message)s --- %(pathname)s:%(lineno)d"
)
LOG_FORMAT_PROD = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


def setup_logging(env: Literal["local", "dev", "prod"]) -> None:
    """Setup logging configuration based on the environment."""
    if env in ("local", "dev"):
        logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT_DEBUG)
    else:
        logging.basicConfig(level=logging.INFO, format=LOG_FORMAT_PROD)
    logging.getLogger("httpx").setLevel(logging.WARNING)
