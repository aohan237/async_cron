import logging


def get_logger(log_level=None):
    logger = logging.getLogger(__package__)
    FORMAT = "%(asctime)s - %(name)s - %(levelname)s - \n%(message)s"
    logging.basicConfig(format=FORMAT)
    if log_level == 'debug':
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    return logger
