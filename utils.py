import os
import hashlib
import fnmatch
from datetime import datetime
from config import excluded_folders

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'


def ensure_logs_dir():
    """Create logs directory if it doesn't exist"""
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def format_win_path(path):
    """Convert path to Windows-style with backslashes"""
    return os.path.normpath(path).replace(os.sep, '\\')


def should_exclude_folder(folder_path, excluded_patterns=None):
    """Check if folder should be excluded from processing"""
    patterns = excluded_patterns or excluded_folders
    for pattern in patterns:
        if fnmatch.fnmatch(folder_path.lower(), f"*{pattern.lower()}*"):
            return True
    return False


def get_file_hash(filepath):
    """Generate SHA-256 hash for file contents"""
    hash_sha = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha.update(chunk)
        return hash_sha.hexdigest()
    except Exception as e:
        print(f"{Colors.RED}Error hashing {format_win_path(filepath)}: {e}{Colors.END}")
        return None


def get_folder_size(path, excluded_patterns=None):
    """Calculate total size of all files in directory (in bytes)"""
    total = 0
    for root, _, filenames in os.walk(path):
        if should_exclude_folder(root, excluded_patterns):
            continue
        for f in filenames:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except:
                continue
    return total


def format_time(timestamp):
    """Convert timestamp to readable format"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
