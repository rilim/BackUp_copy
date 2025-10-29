import os
import shutil
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from utils import Colors, format_win_path, get_file_hash, should_exclude_folder
from config import RETRY_ATTEMPTS, RETRY_DELAY

HASH_INDEX_FILE = "hash_index.json"  # persistent index file


def load_hash_index(index_path):
    """load or create persistent hash index"""
    if os.path.exists(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_hash_index(index, index_path):
    """save persistent hash index"""
    try:
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f)
    except Exception as e:
        print(f"{Colors.RED}Error saving hash index: {e}{Colors.END}")


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


def get_file_details(folder, base_folder, excluded_patterns=None, use_parallel=True):
    """Get files with their modification times, sizes, and hashes"""
    file_details = {}
    hash_index = load_hash_index(HASH_INDEX_FILE)
    files_to_hash = []
    metadata_map = {}

    for root, _, filenames in os.walk(folder):
        if should_exclude_folder(root, excluded_patterns):
            continue
        for filename in filenames:
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, base_folder)
            try:
                mtime = os.path.getmtime(abs_path)
                size = os.path.getsize(abs_path)
                metadata_map[rel_path] = (abs_path, mtime, size)
                prev = hash_index.get(rel_path)
                if prev and prev["mtime"] == mtime and prev["size"] == size:
                    file_details[rel_path] = {
                        "mtime": mtime,
                        "size": size,
                        "hash": prev["hash"],
                        "path": abs_path,
                    }
                else:
                    files_to_hash.append((rel_path, abs_path, mtime, size))
            except Exception as e:
                print(f"{Colors.RED}Error getting metadata for {format_win_path(abs_path)}: {e}{Colors.END}")

    if use_parallel and files_to_hash:
        with ThreadPoolExecutor() as executor:
            future_map = {
                executor.submit(get_file_hash, item[1]): item for item in files_to_hash
            }
            for future in as_completed(future_map):
                rel_path, abs_path, mtime, size = future_map[future]
                try:
                    hash_val = future.result()
                    file_details[rel_path] = {
                        "mtime": mtime,
                        "size": size,
                        "hash": hash_val,
                        "path": abs_path,
                    }
                    hash_index[rel_path] = {
                        "mtime": mtime,
                        "size": size,
                        "hash": hash_val,
                    }
                except Exception as e:
                    print(f"{Colors.RED}Error hashing {format_win_path(abs_path)}: {e}{Colors.END}")
    else:
        for rel_path, abs_path, mtime, size in files_to_hash:
            try:
                hash_val = get_file_hash(abs_path)
                file_details[rel_path] = {
                    "mtime": mtime,
                    "size": size,
                    "hash": hash_val,
                    "path": abs_path,
                }
                hash_index[rel_path] = {
                    "mtime": mtime,
                    "size": size,
                    "hash": hash_val,
                }
            except Exception as e:
                print(f"{Colors.RED}Error hashing {format_win_path(abs_path)}: {e}{Colors.END}")

    save_hash_index(hash_index, HASH_INDEX_FILE)
    return file_details


def robust_copy(src_path, dest_path, operation="copy"):
    """Retry wrapper for file operations with exponential backoff"""
    attempts = 0
    while attempts < RETRY_ATTEMPTS:
        try:
            if operation == "copy":
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
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


def copy_worker(src_path, dest_path, progress, progress_lock):
    """Thread worker for copy operations with thread-safe progress increment"""
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        src_hash = get_file_hash(src_path)
        dest_hash = get_file_hash(dest_path) if os.path.exists(dest_path) else None
        if src_hash != dest_hash:
            robust_copy(src_path, dest_path)
            print(f"{Colors.GREEN}Copied {format_win_path(src_path)} to {format_win_path(dest_path)}{Colors.END}")
        else:
            print(f"{Colors.CYAN}Skipped identical file: {format_win_path(src_path)}{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}Error copying {format_win_path(src_path)}: {e}{Colors.END}")
    finally:
        with progress_lock:
            progress[0] += 1
