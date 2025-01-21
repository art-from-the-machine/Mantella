import logging

class CustomFormatter(logging.Formatter):
    reset = "\x1b[0m"
    bright = "\x1b[1m"
    dim = "\x1b[2m"
    underscore = "\x1b[4m"
    blink = "\x1b[5m"
    reverse = "\x1b[7m"
    hidden = "\x1b[8m"

    # Foreground colors
    black = "\x1b[90m"
    red = "\x1b[91m"
    green = "\x1b[92m"
    yellow = "\x1b[93m"
    blue = "\x1b[94m"
    magenta = "\x1b[95m"
    cyan = "\x1b[96m"
    white = "\x1b[97m"
    grey = "\x1b[37m"

    # Background colors
    BGblack = "\x1b[40m"
    BGred = "\x1b[41m"
    BGgreen = "\x1b[42m"
    BGyellow = "\x1b[43m"
    BGblue = "\x1b[44m"
    BGmagenta = "\x1b[45m"
    BGcyan = "\x1b[46m"
    BGwhite = "\x1b[47m"
    BGLightBlue = "\x1b[104m"

    # Custom combinations - avoiding dim for better visibility
    error_style = bright + red
    warning_style = bright + yellow
    info_style = white
    debug_style = cyan + dim

    # Special purpose combinations
    player_style = magenta
    tts_style = green + dim
    npc_voice_style = green
    npc_info_style = dim
    startup_style = white
    hyperlink_style = blue + underscore

    format_string: str = "%(asctime)s.%(msecs)03d %(levelname)s: %(message)s"

    FORMATS = {
        logging.DEBUG: debug_style + format_string + reset,
        logging.INFO: info_style + format_string + reset,
        logging.WARNING: warning_style + format_string + reset,
        logging.ERROR: error_style + format_string + reset,
        logging.CRITICAL: white + BGred + bright + format_string + reset,

        # INFO level
        # player
        21: player_style + "%(message)s" + reset,
        # NPC voiceline
        22: npc_voice_style + "%(message)s" + reset,
        # NPC info
        23: npc_info_style + "%(message)s" + reset,
        # Startup
        24: startup_style + "%(message)s" + reset,
        # Hyperlink
        25: hyperlink_style + "%(message)s" + reset,

        # STT
        27: blue + format_string + reset,
        # LLM
        28: cyan + format_string + reset,
        # TTS
        29: tts_style + format_string + reset,

        # HTTP in
        41: blue + format_string + reset,
        # HTTP out
        42: green + format_string + reset,
        # sentence queue
        43: white + BGblue + format_string + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, "%H:%M:%S")
        return formatter.format(record)