import os
import shutil
import time
from utils import Colors, format_win_path, get_file_hash, should_exclude_folder
from config import RETRY_ATTEMPTS, RETRY_DELAY


def get_relative_paths(folder_path, base_folder, excluded_patterns=None):
    """Get all relative file paths and directory paths"""
    files = set()
    dirs = set()

    for root, dirnames, filenames in os.walk(folder_path, topdown=True):
        if should_exclude_folder(root, excluded_patterns):
            dirnames.clear()
            continue

        rel_root = os.path.relpath(root, base_folder)
        dirs.add(rel_root)

        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), base_folder)
            files.add(rel_path)

    return files, dirs


def get_file_details(folder, base_folder, excluded_patterns=None):
    """Get files with their modification times, sizes, and hashes"""
    file_details = {}
    for root, _, filenames in os.walk(folder):
        if should_exclude_folder(root, excluded_patterns):
            continue
        for filename in filenames:
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, base_folder)
            try:
                file_details[rel_path] = {
                    'mtime': os.path.getmtime(abs_path),
                    'size': os.path.getsize(abs_path),
                    'hash': get_file_hash(abs_path),
                    'path': abs_path
                }
            except Exception as e:
                print(f"{Colors.RED}Error getting details for {format_win_path(abs_path)}: {e}{Colors.END}")
    return file_details


def robust_copy(src_path, dest_path, operation="copy"):
    """Retry wrapper for file operations with exponential backoff"""
    attempts = 0
    while attempts < RETRY_ATTEMPTS:
        try:
            if operation == "copy":
                shutil.copy2(src_path, dest_path)
            elif operation == "delete":
                os.remove(src_path)
            return True
        except Exception as e:
            attempts += 1
            if attempts >= RETRY_ATTEMPTS:
                raise
            time.sleep(RETRY_DELAY * (2 ** (attempts - 1)))
    return False


def copy_worker(src_path, dest_path, progress):
    """Thread worker for copy operations"""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        src_hash = get_file_hash(src_path)
        dest_hash = get_file_hash(dest_path) if os.path.exists(dest_path) else None

        if src_hash != dest_hash:
            robust_copy(src_path, dest_path)
            progress[0] += 1
            print(f"{Colors.GREEN}Copied {format_win_path(src_path)} to {format_win_path(dest_path)}{Colors.END}")
        else:
            print(f"{Colors.CYAN}Skipped identical file: {format_win_path(src_path)}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error copying {format_win_path(src_path)}: {e}{Colors.END}")
