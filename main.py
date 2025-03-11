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

        # Process directories first
        rel_root = os.path.relpath(root, base_folder)
        dirs.add(rel_root)

        # Process files
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

                copy_condition = (
                        not os.path.exists(dest_path) or
                        os.path.getmtime(src_path) > os.path.getmtime(dest_path)
                )

                if copy_condition:
                    print(f"Copying {src_path} to {dest_path}")
                    shutil.copy2(src_path, dest_path)

    except Exception as e:
        print(f"Error during copy: {e}")


def delete_obsolete_items(src, dest):
    try:
        # Get relative paths
        src_files, src_dirs = get_relative_paths(src, src)
        dest_files, dest_dirs = get_relative_paths(dest, dest)

        # Find obsolete items
        obsolete_files = dest_files - src_files
        obsolete_dirs = dest_dirs - src_dirs

        # Delete obsolete files
        if obsolete_files:
            print("\nFound obsolete files:")
            for rel_path in obsolete_files:
                print(f"- {rel_path}")

            if input("Delete these files? (yes/no): ").lower() == "yes":
                for rel_path in obsolete_files:
                    abs_path = os.path.join(dest, rel_path)
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        print(f"Deleted file: {abs_path}")
                print("File cleanup complete")

        # Delete obsolete directories (deepest first)
        if obsolete_dirs:
            print("\nFound obsolete directories:")
            dirs_to_delete = sorted(
                [os.path.join(dest, d) for d in obsolete_dirs],
                key=lambda x: x.count(os.sep),
                reverse=True
            )

            for d in dirs_to_delete:
                print(f"- {d}")

            if input("Delete these directories? (yes/no): ").lower() == "yes":
                for abs_dir in dirs_to_delete:
                    if os.path.exists(abs_dir):
                        shutil.rmtree(abs_dir)
                        print(f"Deleted directory: {abs_dir}")
                print("Directory cleanup complete")

        if not obsolete_files and not obsolete_dirs:
            print("\nDestination is fully synchronized - nothing to delete")

    except Exception as e:
        print(f"Cleanup error: {e}")


if __name__ == "__main__":
    print("=== Starting synchronization ===")
    copy_files(source_folder, destination_folder)
    delete_obsolete_items(source_folder, destination_folder)
    print("=== Synchronization complete ===")
