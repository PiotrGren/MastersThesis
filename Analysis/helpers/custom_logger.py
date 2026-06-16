import logging

class CustomFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    format_str = "%(asctime)s - %(levelname)s - %(message)s"

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: green + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: red + format_str + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%H:%M:%S")
        return formatter.format(record)

def get_custom_logger(name: str, level=logging.DEBUG) -> logging.Logger:
    """Tworzy i zwraca skonfigurowany, kolorowy logger."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Zabezpieczenie przed powielaniem handlerów (jeśli funkcja zostanie wywołana kilka razy)
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setFormatter(CustomFormatter())
        logger.addHandler(ch)
        
    # Zapobiega propagacji logów do root loggera (unikamy podwójnych printów)
    logger.propagate = False 
    return logger