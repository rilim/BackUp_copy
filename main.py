import os
import shutil
import fnmatch
from datetime import datetime

# Configuration
source_folder = "D:/BackUp/origin"
destination_folder = "D:/BackUp/Copy"
excluded_folders = ["D:/BackUp/origin/Investavimas", "D:/BackUp/origin/Islaidos/Islaidos UK"]


def should_exclude_folder(folder_path):
    """Check if folder should be excluded from processing"""
    for pattern in excluded_folders:
        if fnmatch.fnmatch(folder_path.lower(), f"*{pattern.lower()}*"):
            return True
    return False


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


def get_file_details(folder, base_folder):
    """Get files with their modification times and sizes"""
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
                'path': abs_path
            }
    return file_details


def format_time(timestamp):
    """Convert timestamp to readable format"""
    return datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')


def copy_files(src, dest):
    """Sync files from source to destination"""
    try:
        for root, dirs, files in os.walk(src, topdown=True):
            if should_exclude_folder(root):
                dirs.clear()
                continue

            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, src)
                dest_path = os.path.join(dest, rel_path)

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                copy_needed = (
                        not os.path.exists(dest_path) or
                        os.path.getmtime(src_path) > os.path.getmtime(dest_path)
                )

                if copy_needed:
                    print(f"Copying {src_path} to {dest_path}")
                    shutil.copy2(src_path, dest_path)

    except Exception as e:
        print(f"Copy error: {e}")


def delete_obsolete_items(src, dest):
    """Remove destination items not present in source"""
    try:
        src_files, src_dirs = get_relative_paths(src, src)
        dest_files, dest_dirs = get_relative_paths(dest, dest)

        obsolete_files = dest_files - src_files
        obsolete_dirs = dest_dirs - src_dirs

        if obsolete_files:
            print("\nObsolete files found:")
            for rel_path in obsolete_files:
                print(f"- {rel_path}")

            if input("Delete these files? (yes/no): ").lower() == "yes":
                for rel_path in obsolete_files:
                    abs_path = os.path.join(dest, rel_path)
                    os.remove(abs_path)
                    print(f"Deleted file: {abs_path}")

        if obsolete_dirs:
            print("\nObsolete directories found:")
            dirs_to_delete = sorted(
                [os.path.join(dest, d) for d in obsolete_dirs],
                key=lambda x: x.count(os.sep),
                reverse=True
            )
            for d in dirs_to_delete:
                print(f"- {d}")
                shutil.rmtree(d)

        if not obsolete_files and not obsolete_dirs:
            print("\nDestination is synchronized")

    except Exception as e:
        print(f"Cleanup error: {e}")


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

            if dest_data['mtime'] > src_data['mtime']:
                restore_candidates[rel_path] = ('newer', dest_data)
            elif dest_data['mtime'] < src_data['mtime']:
                restore_candidates[rel_path] = ('older', dest_data)

        _, src_dirs = get_relative_paths(src, src)
        _, dest_dirs = get_relative_paths(dest, dest)
        missing_dirs = dest_dirs - src_dirs

        if not restore_candidates and not missing_dirs:
            print("\nDestination is identical to source - nothing to restore")
            return

        print("\n[ Restoration Candidates ]")
        categories = {'missing': [], 'newer': [], 'older': []}
        for rel_path, (status, _) in restore_candidates.items():
            categories[status].append(rel_path)

        if categories['missing']:
            print(f"\nMissing files ({len(categories['missing'])}):")
            for f in categories['missing'][:3]:
                print(f" - {f}")

        if categories['newer']:
            print(f"\nNewer in backup ({len(categories['newer'])}):")
            for f in categories['newer'][:3]:
                print(f" - {f}")

        if categories['older']:
            print(f"\nOlder in backup ({len(categories['older'])}):")
            for f in categories['older'][:3]:
                src_time = format_time(src_files[f]['mtime'])
                dest_time = format_time(dest_files[f]['mtime'])
                print(f" - {f} (Source: {src_time}, Backup: {dest_time})")

        if missing_dirs:
            print("\nMissing directories:")
            for d in sorted(missing_dirs)[:3]:
                print(f" - {d}/")

        print("\n[ Restore Modes ]")
        print("1: Safe (missing/newer files only)")
        print("2: Force (all listed files)")
        mode = input("Choose restore mode (1/2): ").strip()

        if mode not in ('1', '2'):
            print("Restore cancelled")
            return

        to_restore = {}
        if mode == '1':
            to_restore = {k: v for k, v in restore_candidates.items() if v[0] in ('missing', 'newer')}
        else:
            to_restore = restore_candidates

        if not to_restore and not missing_dirs:
            print("No items to restore for selected mode")
            return

        if input("\nConfirm restore? (yes/no): ").lower() != "yes":
            print("Restore cancelled")
            return

        for rel_dir in sorted(missing_dirs, key=lambda x: x.count(os.sep)):
            target_dir = os.path.join(src, rel_dir)
            os.makedirs(target_dir, exist_ok=True)
            print(f"Restored directory: {target_dir}")

        for rel_path, (status, dest_data) in to_restore.items():
            src_path = os.path.join(src, rel_path)
            dest_path = dest_data['path']

            os.makedirs(os.path.dirname(src_path), exist_ok=True)
            shutil.copy2(dest_path, src_path)
            print(f"Restored file ({status}): {src_path}")

        print("\nRestore completed successfully")

    except Exception as e:
        print(f"Restore error: {e}")


def show_differences():
    """Show detailed comparison between source and destination"""
    print("\n=== Analyzing Differences ===")

    src_files = get_file_details(source_folder, source_folder)
    dest_files = get_file_details(destination_folder, destination_folder)

    only_in_source = set(src_files.keys()) - set(dest_files.keys())
    only_in_dest = set(dest_files.keys()) - set(src_files.keys())
    newer_in_source = []
    newer_in_dest = []

    for f in set(src_files.keys()) & set(dest_files.keys()):
        if src_files[f]['mtime'] > dest_files[f]['mtime']:
            newer_in_source.append(f)
        elif dest_files[f]['mtime'] > src_files[f]['mtime']:
            newer_in_dest.append(f)

    src_dirs, _ = get_relative_paths(source_folder, source_folder)
    dest_dirs, _ = get_relative_paths(destination_folder, destination_folder)
    only_dirs_source = src_dirs - dest_dirs
    only_dirs_dest = dest_dirs - src_dirs

    print(f"\n{' Source Only ':-^50}")
    print(f"Files: {len(only_in_source)} | Directories: {len(only_dirs_source)}")

    print(f"\n{' Destination Only ':-^50}")
    print(f"Files: {len(only_in_dest)} | Directories: {len(only_dirs_dest)}")

    print(f"\n{' Modified Files ':-^50}")
    print(f"Newer in source: {len(newer_in_source)}")
    print(f"Newer in destination: {len(newer_in_dest)}")

    def show_sample(items, title, max=3):
        if items:
            print(f"\n{title} (showing {max}):")
            for item in list(items)[:max]:
                print(f" - {item}")
                if item in src_files and item in dest_files:
                    print(f"   Source: {format_time(src_files[item]['mtime'])}")
                    print(f"   Backup: {format_time(dest_files[item]['mtime'])}")

    show_sample(only_in_source, "Unique source files")
    show_sample(only_in_dest, "Unique destination files")
    show_sample(newer_in_source, "Files newer in source")
    show_sample(newer_in_dest, "Files newer in destination")

    print("\n" + "=" * 50)


if __name__ == "__main__":
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n" + "=" * 40)
        print("File Synchronization Tool")
        print("1. Sync (source → destination)")
        print("2. Restore (destination → source)")
        print("3. Show differences")
        print("4. Exit")
        choice = input("Choose operation (1/2/3/4): ").strip()

        if choice == "1":
            print("\n=== Synchronizing ===")
            copy_files(source_folder, destination_folder)
            delete_obsolete_items(source_folder, destination_folder)
        elif choice == "2":
            print("\n=== Restoring ===")
            restore_files(source_folder, destination_folder)
        elif choice == "3":
            print("\n=== Differences ===")
            show_differences()
        elif choice == "4":
            print("Exiting program...")
            break
        else:
            print("Invalid choice, please try again")

        input("\nPress Enter to continue...")
