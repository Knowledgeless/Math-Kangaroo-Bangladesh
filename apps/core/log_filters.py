import logging


class OmitTraceback(logging.Filter):
    """Log the message without its traceback.

    Used for expected noise such as requests for unknown host names, where a
    full traceback per request would only fill the log.
    """

    def filter(self, record):
        record.exc_info = None
        record.exc_text = None
        return True
