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


def get_relative_files(folder_path, base_folder):
    """Get relative paths of all files compared to base folder"""
    files = []
    for root, dirs, filenames in os.walk(folder_path):
        if should_exclude_folder(root):
            dirs.clear()
            continue
        for filename in filenames:
            abs_path = os.path.join(root, filename)
            rel_path = os.path.relpath(abs_path, base_folder)
            files.append(rel_path)
    return files


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


def delete_obsolete_files(src, dest):
    try:
        # Get relative paths from their respective base folders
        src_rel_files = set(get_relative_files(src, src))
        dest_rel_files = set(get_relative_files(dest, dest))

        # Find files that exist in destination but not in source
        obsolete_files = dest_rel_files - src_rel_files

        if not obsolete_files:
            print("No obsolete files found")
            return

        print(f"Found {len(obsolete_files)} obsolete files:")
        for rel_path in obsolete_files:
            print(f"- {rel_path}")

        confirm = input("Delete these files? (yes/no): ").lower()
        if confirm == "yes":
            for rel_path in obsolete_files:
                abs_path = os.path.join(dest, rel_path)
                if os.path.isfile(abs_path):
                    os.remove(abs_path)
                    print(f"Deleted file: {abs_path}")
                elif os.path.isdir(abs_path):
                    shutil.rmtree(abs_path)
                    print(f"Deleted directory: {abs_path}")
            print("Cleanup complete")
        else:
            print("Deletion cancelled")

    except Exception as e:
        print(f"Error during cleanup: {e}")


if __name__ == "__main__":
    # First copy all files
    copy_files(source_folder, destination_folder)

    # Then check for obsolete files
    delete_obsolete_files(source_folder, destination_folder)
