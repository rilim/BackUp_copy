import os
import shutil
import fnmatch

source_folder = "D:/BackUp/origin"
destination_folder = "D:/BackUp/Copy"
excluded_folders = ["D:/BackUp/origin/Investavimas", "D:/BackUp/origin/Islaidos/Islaidos UK"]


def should_exclude_folder(folder_path):
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


def copy_files(src, dest):
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

                if not os.path.exists(dest_path) or \
                        os.path.getmtime(src_path) > os.path.getmtime(dest_path):
                    print(f"Copying {src_path} to {dest_path}")
                    shutil.copy2(src_path, dest_path)

    except Exception as e:
        print(f"Error during copy: {e}")


def delete_obsolete_items(src, dest):
    try:
        src_files, src_dirs = get_relative_paths(src, src)
        dest_files, dest_dirs = get_relative_paths(dest, dest)

        obsolete_files = dest_files - src_files
        obsolete_dirs = dest_dirs - src_dirs

        if obsolete_files:
            print("\nObsolete files:")
            for rel_path in obsolete_files:
                print(f"- {rel_path}")

            if input("Delete these files? (yes/no): ").lower() == "yes":
                for rel_path in obsolete_files:
                    abs_path = os.path.join(dest, rel_path)
                    os.remove(abs_path)
                    print(f"Deleted file: {abs_path}")

        if obsolete_dirs:
            print("\nObsolete directories:")
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
    """Restore missing files and directories from backup"""
    try:
        src_files, src_dirs = get_relative_paths(src, src)
        dest_files, dest_dirs = get_relative_paths(dest, dest)

        # Find files/dirs that exist in backup but not in source
        restore_files = dest_files - src_files
        restore_dirs = dest_dirs - src_dirs

        if not restore_files and not restore_dirs:
            print("\nNothing to restore - destination matches source")
            return

        print("\nFiles to restore:")
        for f in restore_files:
            print(f"- {f}")

        print("\nDirectories to restore:")
        for d in restore_dirs:
            print(f"- {d}")

        if input("\nConfirm restore? (yes/no): ").lower() == "yes":
            # Restore directories first
            for rel_dir in sorted(restore_dirs, key=lambda x: x.count(os.sep)):
                target_dir = os.path.join(src, rel_dir)
                os.makedirs(target_dir, exist_ok=True)
                print(f"Restored directory: {target_dir}")

            # Restore files
            for rel_path in restore_files:
                src_file = os.path.join(src, rel_path)
                backup_file = os.path.join(dest, rel_path)

                os.makedirs(os.path.dirname(src_file), exist_ok=True)
                shutil.copy2(backup_file, src_file)
                print(f"Restored file: {src_file}")

            print("\nRestore completed successfully")

    except Exception as e:
        print(f"Restore error: {e}")


if __name__ == "__main__":
    print("1. Sync (source → destination)")
    print("2. Restore (destination → source)")
    choice = input("Choose operation (1/2): ").strip()

    if choice == "1":
        print("\n=== Synchronizing ===")
        copy_files(source_folder, destination_folder)
        delete_obsolete_items(source_folder, destination_folder)
    elif choice == "2":
        print("\n=== Restoring ===")
        restore_files(source_folder, destination_folder)
    else:
        print("Invalid choice")
