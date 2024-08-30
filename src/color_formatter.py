import logging

class CustomFormatter(logging.Formatter):
    reset = "\x1b[0m"
    bright = "\x1b[1m"
    dim = "\x1b[2m"
    underscore = "\x1b[4m"
    blink = "\x1b[5m"
    reverse = "\x1b[7m"
    hidden = "\x1b[8m"

    black = "\x1b[30m"
    red = "\x1b[31m"
    bold_red = "\x1b[31m;1"
    green = "\x1b[32m"
    yellow = "\x1b[33m"
    orange = "\x1b[33m"
    blue = "\x1b[34m"
    magenta = "\x1b[35m"
    cyan = "\x1b[36m"
    grey = "\x1b[38;20m"
    white = "\x1b[37m"

    BGblack = "\x1b[40m"
    BGred = "\x1b[41m"
    BGgreen = "\x1b[42m"
    BGyellow = "\x1b[43m"
    BGblue = "\x1b[44m"
    BGmagenta = "\x1b[45m"
    BGcyan = "\x1b[46m"
    BGwhite = "\x1b[47m"
    BGLightBlue = "\x1b[104m"

    dim_red = "\x1b[31m\x1b[2m"
    dim_blue = "\x1b[34m\x1b[2m"
    dim_green = "\x1b[32m\x1b[2m"

    hyperlink = blue + underscore

    format_string: str = "%(asctime)s.%(msecs)03d %(levelname)s: %(message)s"

    FORMATS = {
        logging.DEBUG: dim + format_string + reset,
        logging.INFO: grey + format_string + reset,
        logging.WARNING: yellow + format_string + reset,
        logging.ERROR: red + format_string + reset,
        logging.CRITICAL: white + BGred + format_string + reset,

        # INFO level
        # player
        21: green + "%(message)s" + reset,
        # NPC voiceline
        22: yellow + "%(message)s" + reset,
        # NPC info
        23: dim + "%(message)s" + reset,
        # Startup
        24: white + "%(message)s" + reset,
        # Hyperlink
        50: hyperlink + "%(message)s" + reset,

        # STT
        27: blue + format_string + reset,
        # LLM
        28: cyan + format_string + reset,
        # STT
        29: magenta + format_string + reset,

        # WARNING level
        # 30:

        # HTTP in
        40: dim_blue + format_string + reset,
        # HTTP out
        41: dim_green + format_string + reset,
        # sentence queue
        42: black + BGLightBlue + format_string + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%H:%M:%S")
        return formatter.format(record)