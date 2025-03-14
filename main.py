import os
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from config import source_folder, destination_folder, excluded_folders, MAX_WORKERS
from utils import Colors, ensure_logs_dir, format_win_path, get_folder_size, format_time, should_exclude_folder
from ui import show_sample
from file_ops import get_relative_paths, get_file_details, robust_copy, copy_worker


def copy_files(src, dest):
    """Sync files from source to destination with parallel processing"""
    try:
        # Pre-flight check: verify source and destination exist
        if not os.path.exists(src):
            print(f"{Colors.RED}Source folder doesn't exist: {src}{Colors.END}")
            return

        os.makedirs(dest, exist_ok=True)

        # Check disk space availability
        src_size = get_folder_size(src)
        dest_free = shutil.disk_usage(dest).free

        if dest_free < src_size:
            print(
                f"{Colors.RED}Not enough space on destination drive. Need {src_size/1e9:.2f} GB, have {dest_free/1e9:.2f} GB{Colors.END}")
            return

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
                try:
                    total_size += os.path.getsize(src_path)
                except Exception as e:
                    print(
                        f"{Colors.YELLOW}Warning: Could not get size for {format_win_path(src_path)}: {e}{Colors.END}")

        print(f"{Colors.MAGENTA}Total to sync: {len(file_pairs)} files ({total_size/1024/1024:.2f} MB){Colors.END}")

        progress = [0]
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for i, (s, d) in enumerate(file_pairs):
                executor.submit(copy_worker, s, d, progress)
                if i % 10 == 0:
                    print(
                        f"{Colors.YELLOW}Progress: {progress[0]}/{len(file_pairs)} ({progress[0]/len(file_pairs):.1%}){Colors.END}",
                        end='\r')

        print(f"\n{Colors.GREEN}Synced {progress[0]} files successfully!{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Copy error: {e}{Colors.END}")


def delete_obsolete_items(src, dest):
    """Remove destination items not present in source"""
    try:
        src_files, src_dirs = get_relative_paths(src, src)
        dest_files, dest_dirs = get_relative_paths(dest, dest)

        obsolete_files = [format_win_path(os.path.join(dest, f)) for f in (dest_files - src_files)]
        obsolete_dirs = [format_win_path(os.path.join(dest, d)) for d in (dest_dirs - src_dirs)]

        if obsolete_files:
            show_sample(obsolete_files, "Obsolete files found")
            if input(f"{Colors.YELLOW}Delete these files? (yes/no): {Colors.END}").lower() == "yes":
                for abs_path in obsolete_files:
                    try:
                        robust_copy(abs_path, None, "delete")
                        print(f"{Colors.GREEN}Deleted file: {abs_path}{Colors.END}")
                    except Exception as e:
                        print(f"{Colors.RED}Delete failed: {abs_path} - {e}{Colors.END}")

        if obsolete_dirs:
            # Sort directories by depth (deepest first) to avoid dependency issues
            sorted_dirs = sorted(obsolete_dirs, key=lambda x: x.count('\\'), reverse=True)
            show_sample(sorted_dirs, "Obsolete directories found")
            if input(f"{Colors.YELLOW}Delete these directories? (yes/no): {Colors.END}").lower() == "yes":
                for d in sorted_dirs:
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
        # Pre-flight check: verify source and destination exist
        if not os.path.exists(dest):
            print(f"{Colors.RED}Backup folder doesn't exist: {dest}{Colors.END}")
            return

        os.makedirs(src, exist_ok=True)

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
            show_sample([format_win_path(os.path.join(dest, p)) for p in categories['missing']],
                        "Missing files", dest)

        if categories['modified']:
            modified_list = []
            for f in categories['modified']:
                src_time = format_time(src_files[f]['mtime'])
                dest_time = format_time(dest_files[f]['mtime'])
                modified_list.append(
                    f"{format_win_path(os.path.join(dest, f))} (Source: {src_time}, Backup: {dest_time})")
            show_sample(modified_list, "Modified files")

        if missing_dirs:
            show_sample([format_win_path(os.path.join(dest, d)) for d in sorted(missing_dirs)],
                        "Missing directories")

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

        # Create a restore point of the current state if user wants
        if input(
                f"{Colors.YELLOW}Create backup of current state before restoring? (yes/no): {Colors.END}").lower() == "yes":
            backup_dir = os.path.join(src, f"backup_before_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            os.makedirs(backup_dir, exist_ok=True)
            print(f"{Colors.CYAN}Creating backup at: {format_win_path(backup_dir)}{Colors.END}")

            # Only backup files that will be modified
            for rel_path in to_restore.keys():
                src_path = os.path.join(src, rel_path)
                if os.path.exists(src_path):
                    backup_path = os.path.join(backup_dir, rel_path)
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    try:
                        shutil.copy2(src_path, backup_path)
                    except Exception as e:
                        print(f"{Colors.YELLOW}Could not backup {format_win_path(src_path)}: {e}{Colors.END}")

        # Restore directories first
        for rel_dir in sorted(missing_dirs, key=lambda x: x.count(os.sep)):
            target_dir = os.path.join(src, rel_dir)
            os.makedirs(target_dir, exist_ok=True)
            print(f"{Colors.GREEN}Restored directory: {format_win_path(target_dir)}{Colors.END}")

        # Restore files with progress tracking
        successful_restores = 0
        total_restores = len(to_restore)

        # Restore files in parallel
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            restore_tasks = []
            restore_paths = []  # Track paths for reporting

            for rel_path, (status, dest_data) in to_restore.items():
                src_path = os.path.join(src, rel_path)
                dest_path = dest_data['path']
                restore_paths.append(src_path)  # Store path for reporting
                restore_tasks.append(executor.submit(
                    robust_copy, dest_path, src_path, "copy"
                ))

            for i, (task, path) in enumerate(zip(restore_tasks, restore_paths)):
                try:
                    task.result()
                    successful_restores += 1
                    print(f"{Colors.GREEN}Restored file: {format_win_path(path)}{Colors.END}")
                except Exception as e:
                    print(f"{Colors.RED}Restore failed: {format_win_path(path)} - {e}{Colors.END}")
                if i % 10 == 0:
                    print(
                        f"{Colors.YELLOW}Progress: {i+1}/{len(restore_tasks)} ({((i+1)/len(restore_tasks)):.1%}){Colors.END}",
                        end='\r')

        print(f"\n{Colors.GREEN}Restore completed: {successful_restores}/{total_restores} files restored!{Colors.END}")

    except Exception as e:
        print(f"{Colors.RED}Restore error: {e}{Colors.END}")


def show_differences():
    """Show detailed comparison between source and destination"""
    print(f"\n{Colors.MAGENTA}=== Analyzing Differences ==={Colors.END}")

    # Pre-flight check: verify source and destination exist
    if not os.path.exists(source_folder) or not os.path.exists(destination_folder):
        print(f"{Colors.RED}Source or destination folder doesn't exist{Colors.END}")
        return

    src_files = get_file_details(source_folder, source_folder)
    dest_files = get_file_details(destination_folder, destination_folder)

    only_in_source = sorted(set(src_files.keys()) - set(dest_files.keys()))
    only_in_dest = sorted(set(dest_files.keys()) - set(src_files.keys()))
    modified_files = sorted([f for f in src_files if f in dest_files and src_files[f]['hash'] != dest_files[f]['hash']])

    # Convert to absolute paths for display
    abs_only_source = [format_win_path(os.path.join(source_folder, p)) for p in only_in_source]
    abs_only_dest = [format_win_path(os.path.join(destination_folder, p)) for p in only_in_dest]
    abs_modified = [format_win_path(os.path.join(source_folder, p)) for p in modified_files]

    src_size = get_folder_size(source_folder)
    dest_size = get_folder_size(destination_folder)

    print(f"\n{Colors.CYAN}Directory Sizes:{Colors.END}")
    print(f"Source: {src_size/1024/1024:.2f} MB")
    print(f"Destination: {dest_size/1024/1024:.2f} MB")

    print(f"\n{Colors.CYAN}{' Source Only ':-^50}{Colors.END}")
    print(f"Files: {len(abs_only_source)} | Size: {sum(src_files[f]['size'] for f in only_in_source)/1024/1024:.2f} MB")

    print(f"\n{Colors.CYAN}{' Destination Only ':-^50}{Colors.END}")
    print(f"Files: {len(abs_only_dest)} | Size: {sum(dest_files[f]['size'] for f in only_in_dest)/1024/1024:.2f} MB")

    print(f"\n{Colors.CYAN}{' Modified Files ':-^50}{Colors.END}")
    print(f"Count: {len(abs_modified)} | Size Difference: "
          f"{(sum(src_files[f]['size'] for f in modified_files) - sum(dest_files[f]['size'] for f in modified_files))/1024/1024:.2f} MB")

    show_sample(abs_only_source, "Unique source files", source_folder)
    show_sample(abs_only_dest, "Unique destination files", destination_folder)
    show_sample(abs_modified, "Modified files", source_folder)

    print(f"\n{Colors.MAGENTA}{'='*50}{Colors.END}")


if __name__ == "__main__":
    ensure_logs_dir()
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
