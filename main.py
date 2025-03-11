import os
import shutil
import fnmatch
import hashlib
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# Configuration
source_folder = "D:/BackUp/origin"
destination_folder = "D:/BackUp/Copy"
excluded_folders = ["D:/BackUp/origin/Investavimas", "D:/BackUp/origin/Islaidos/Islaidos UK"]
MAX_WORKERS = 4  # Adjust based on your CPU cores
RETRY_ATTEMPTS = 3
RETRY_DELAY = 1  # Seconds


class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    END = '\033[0m'


def should_exclude_folder(folder_path):
    """Check if folder should be excluded from processing"""
    for pattern in excluded_folders:
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
        print(f"{Colors.RED}Error hashing {filepath}: {e}{Colors.END}")
        return None


def get_relative_paths(folder_path, base_folder):
    """Get all relative file paths and directory paths"""
    files = set()
    dirs = set()

    for root, dirnames, filenames in os.walk(folder_path, topdown=True):
        if should_exclude_folder(root):
            dirnames.clear()
            continue

        rel_root = os.path.relpath(root, base_folder)
        dirs.add(rel_root)

        for filename in filenames:
            rel_path = os.path.relpath(os.path.join(root, filename), base_folder)
            files.add(rel_path)

    return files, dirs


def get_folder_size(path):
    """Calculate total size of all files in directory (in bytes)"""
    total = 0
    for root, _, filenames in os.walk(path):
        if should_exclude_folder(root):
            continue
        for f in filenames:
            fp = os.path.join(root, f)
            try:
                total += os.path.getsize(fp)
            except:
                continue
    return total


def get_file_details(folder, base_folder):
    """Get files with their modification times, sizes, and hashes"""
    file_details = {}
    for root, _, filenames in os.walk(folder):
        if should_exclude_folder(root):
            continue
        for filename in filenames:
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, base_folder)
            file_details[rel_path] = {
                'mtime': os.path.getmtime(abs_path),
                'size': os.path.getsize(abs_path),
                'hash': get_file_hash(abs_path),
                'path': abs_path
            }
    return file_details


def format_time(timestamp):
    """Convert timestamp to readable format"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


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

        # Check if copy needed using hash comparison
        src_hash = get_file_hash(src_path)
        dest_hash = get_file_hash(dest_path) if os.path.exists(dest_path) else None

        if src_hash != dest_hash:
            robust_copy(src_path, dest_path)
            progress[0] += 1
            print(f"{Colors.GREEN}Copied {src_path} to {dest_path}{Colors.END}")
        else:
            print(f"{Colors.CYAN}Skipped identical file: {src_path}{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Error copying {src_path}: {e}{Colors.END}")


def copy_files(src, dest):
    """Sync files from source to destination with parallel processing"""
    try:
        # Get list of files to copy
        file_pairs = []
        total_size = 0
        for root, dirs, files in os.walk(src, topdown=True):
            if should_exclude_folder(root):
                dirs.clear()
                continue
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, src)
                dest_path = os.path.join(dest, rel_path)
                file_pairs.append((src_path, dest_path))
                total_size += os.path.getsize(src_path)

        print(f"{Colors.MAGENTA}Total to sync: {len(file_pairs)} files ({total_size/1024/1024:.2f} MB){Colors.END}")

        # Shared progress counter
        progress = [0]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i, (s, d) in enumerate(file_pairs):
                executor.submit(copy_worker, s, d, progress)
                if i % 10 == 0:  # Update progress every 10 files
                    print(f"{Colors.YELLOW}Progress: {progress[0]}/{len(file_pairs)} "
                          f"({progress[0]/len(file_pairs):.1%}){Colors.END}", end='\r')

        print(f"\n{Colors.GREEN}Synced {progress[0]} files successfully!{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Copy error: {e}{Colors.END}")


def delete_obsolete_items(src, dest):
    """Remove destination items not present in source"""
    try:
        src_files, src_dirs = get_relative_paths(src, src)
        dest_files, dest_dirs = get_relative_paths(dest, dest)

        obsolete_files = dest_files - src_files
        obsolete_dirs = dest_dirs - src_dirs

        if obsolete_files:
            print(f"{Colors.YELLOW}\nObsolete files found ({len(obsolete_files)}):{Colors.END}")
            for rel_path in list(obsolete_files)[:5]:
                print(f" - {rel_path}")

            if input(f"{Colors.YELLOW}Delete these files? (yes/no): {Colors.END}").lower() == "yes":
                for rel_path in obsolete_files:
                    abs_path = os.path.join(dest, rel_path)
                    try:
                        robust_copy(abs_path, None, "delete")
                        print(f"{Colors.GREEN}Deleted file: {abs_path}{Colors.END}")
                    except Exception as e:
                        print(f"{Colors.RED}Delete failed: {abs_path} - {e}{Colors.END}")

        if obsolete_dirs:
            print(f"{Colors.YELLOW}\nObsolete directories found ({len(obsolete_dirs)}):{Colors.END}")
            dirs_to_delete = sorted(
                [os.path.join(dest, d) for d in obsolete_dirs],
                key=lambda x: x.count(os.sep),
                reverse=True
            )
            for d in dirs_to_delete[:5]:
                print(f" - {d}")

            if input(f"{Colors.YELLOW}Delete these directories? (yes/no): {Colors.END}").lower() == "yes":
                for d in dirs_to_delete:
                    try:
                        shutil.rmtree(d)
                        print(f"{Colors.GREEN}Deleted directory: {d}{Colors.END}")
                    except Exception as e:
                        print(f"{Colors.RED}Delete failed: {d} - {e}{Colors.END}")

        if not obsolete_files and not obsolete_dirs:
            print(f"{Colors.GREEN}\nDestination is synchronized{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Cleanup error: {e}{Colors.END}")


def restore_files(src, dest):
    """Restore items from backup to source with overwrite options"""
    try:
        src_files = get_file_details(src, src)
        dest_files = get_file_details(dest, dest)

        restore_candidates = {}
        for rel_path, dest_data in dest_files.items():
            src_data = src_files.get(rel_path)

            if not src_data:
                restore_candidates[rel_path] = ('missing', dest_data)
                continue

            if dest_data['hash'] != src_data.get('hash'):
                restore_candidates[rel_path] = ('modified', dest_data)

        _, src_dirs = get_relative_paths(src, src)
        _, dest_dirs = get_relative_paths(dest, dest)
        missing_dirs = dest_dirs - src_dirs

        if not restore_candidates and not missing_dirs:
            print(f"{Colors.GREEN}\nDestination is identical to source - nothing to restore{Colors.END}")
            return

        print(f"\n{Colors.MAGENTA}[ Restoration Candidates ]{Colors.END}")
        categories = {'missing': [], 'modified': []}
        for rel_path, (status, _) in restore_candidates.items():
            categories[status].append(rel_path)

        if categories['missing']:
            print(f"{Colors.YELLOW}\nMissing files ({len(categories['missing'])}):{Colors.END}")
            for f in categories['missing'][:3]:
                print(f" - {f}")

        if categories['modified']:
            print(f"{Colors.YELLOW}\nModified files ({len(categories['modified'])}):{Colors.END}")
            for f in categories['modified'][:3]:
                src_time = format_time(src_files[f]['mtime'])
                dest_time = format_time(dest_files[f]['mtime'])
                print(f" - {f} (Source: {src_time}, Backup: {dest_time})")

        if missing_dirs:
            print(f"{Colors.YELLOW}\nMissing directories:{Colors.END}")
            for d in sorted(missing_dirs)[:3]:
                print(f" - {d}/")

        print(f"\n{Colors.MAGENTA}[ Restore Modes ]{Colors.END}")
        print(f"{Colors.CYAN}1: Safe (missing files only)")
        print(f"2: Force (all listed files){Colors.END}")
        mode = input("Choose restore mode (1/2): ").strip()

        to_restore = {}
        if mode == '1':
            to_restore = {k: v for k, v in restore_candidates.items() if v[0] == 'missing'}
        else:
            to_restore = restore_candidates

        if not to_restore and not missing_dirs:
            print(f"{Colors.YELLOW}No items to restore for selected mode{Colors.END}")
            return

        if input(f"{Colors.RED}\nConfirm restore? (yes/no): {Colors.END}").lower() != "yes":
            print(f"{Colors.YELLOW}Restore cancelled{Colors.END}")
            return

        # Restore directories first
        for rel_dir in sorted(missing_dirs, key=lambda x: x.count(os.sep)):
            target_dir = os.path.join(src, rel_dir)
            os.makedirs(target_dir, exist_ok=True)
            print(f"{Colors.GREEN}Restored directory: {target_dir}{Colors.END}")

        # Restore files in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            restore_tasks = []
            for rel_path, (status, dest_data) in to_restore.items():
                src_path = os.path.join(src, rel_path)
                dest_path = dest_data['path']
                restore_tasks.append(executor.submit(
                    robust_copy, dest_path, src_path, "copy"
                ))

            for i, task in enumerate(restore_tasks):
                try:
                    task.result()
                    print(f"{Colors.GREEN}Restored file: {src_path}{Colors.END}")
                except Exception as e:
                    print(f"{Colors.RED}Restore failed: {src_path} - {e}{Colors.END}")
                if i % 10 == 0:
                    print(
                        f"{Colors.YELLOW}Progress: {i+1}/{len(restore_tasks)} ({((i+1)/len(restore_tasks)):.1%}){Colors.END}",
                        end='\r')

        print(f"\n{Colors.GREEN}Restore completed successfully!{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Restore error: {e}{Colors.END}")


def show_differences():
    """Show detailed comparison between source and destination"""
    print(f"\n{Colors.MAGENTA}=== Analyzing Differences ==={Colors.END}")

    src_files = get_file_details(source_folder, source_folder)
    dest_files = get_file_details(destination_folder, destination_folder)

    only_in_source = set(src_files.keys()) - set(dest_files.keys())
    only_in_dest = set(dest_files.keys()) - set(src_files.keys())
    modified_files = [f for f in src_files if f in dest_files and src_files[f]['hash'] != dest_files[f]['hash']]

    src_size = get_folder_size(source_folder)
    dest_size = get_folder_size(destination_folder)

    print(f"\n{Colors.CYAN}Directory Sizes:{Colors.END}")
    print(f"Source: {src_size/1024/1024:.2f} MB")
    print(f"Destination: {dest_size/1024/1024:.2f} MB")

    print(f"\n{Colors.CYAN}{' Source Only ':-^50}{Colors.END}")
    print(f"Files: {len(only_in_source)} | Size: {sum(src_files[f]['size'] for f in only_in_source)/1024/1024:.2f} MB")

    print(f"\n{Colors.CYAN}{' Destination Only ':-^50}{Colors.END}")
    print(f"Files: {len(only_in_dest)} | Size: {sum(dest_files[f]['size'] for f in only_in_dest)/1024/1024:.2f} MB")

    print(f"\n{Colors.CYAN}{' Modified Files ':-^50}{Colors.END}")
    print(f"Count: {len(modified_files)} | Size Difference: "
          f"{(sum(src_files[f]['size'] for f in modified_files) - sum(dest_files[f]['size'] for f in modified_files))/1024/1024:.2f} MB")

    def show_sample(items, title, max=3):
        if items:
            print(f"\n{Colors.YELLOW}{title} (showing {max}):{Colors.END}")
            for item in list(items)[:max]:
                print(f" - {item}")
                if item in src_files and item in dest_files:
                    print(f"   Source: {format_time(src_files[item]['mtime'])} | "
                          f"Hash: {src_files[item]['hash'][:8]}")
                    print(f"   Dest:   {format_time(dest_files[item]['mtime'])} | "
                          f"Hash: {dest_files[item]['hash'][:8]}")

    show_sample(only_in_source, "Unique source files")
    show_sample(only_in_dest, "Unique destination files")
    show_sample(modified_files, "Modified files")

    print(f"\n{Colors.MAGENTA}{'='*50}{Colors.END}")


if __name__ == "__main__":
    try:
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"\n{Colors.MAGENTA}{'='*40}{Colors.END}")
            print(f"{Colors.CYAN}File Synchronization Tool{Colors.END}")
            print(f"{Colors.GREEN}1. Sync (source → destination)")
            print(f"{Colors.YELLOW}2. Restore (destination → source)")
            print(f"{Colors.CYAN}3. Show differences")
            print(f"{Colors.RED}4. Exit{Colors.END}")
            choice = input(f"{Colors.MAGENTA}Choose operation (1/2/3/4): {Colors.END}").strip()

            if choice == "1":
                print(f"\n{Colors.GREEN}=== Synchronizing ==={Colors.END}")
                copy_files(source_folder, destination_folder)
                delete_obsolete_items(source_folder, destination_folder)
            elif choice == "2":
                print(f"\n{Colors.YELLOW}=== Restoring ==={Colors.END}")
                restore_files(source_folder, destination_folder)
            elif choice == "3":
                print(f"\n{Colors.CYAN}=== Differences ==={Colors.END}")
                show_differences()
            elif choice == "4":
                print(f"{Colors.RED}Exiting program...{Colors.END}")
                break
            else:
                print(f"{Colors.RED}Invalid choice, please try again{Colors.END}")

            input(f"\n{Colors.MAGENTA}Press Enter to continue...{Colors.END}")
    except KeyboardInterrupt:
        print(f"\n{Colors.RED}Operation cancelled by user.{Colors.END}")
