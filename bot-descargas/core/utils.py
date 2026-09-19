import time
import os

def get_readable_size(size) -> str:
    if size is None or size == 0: return "0B"
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return "0B"

def get_readable_time(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60: return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(seconds, 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"

def make_bar(percentage: float, width: int = 13) -> str:
    filled = int(percentage / 100 * width)
    if filled >= width: return "⬢" * width
    return "⬢" * filled + "◉" + "◌" * (width - filled - 1)
