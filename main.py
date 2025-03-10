import os
import shutil
import fnmatch

# Define source and destination folders
source_folder = "D:/BackUp/origin"
destination_folder = "D:/BackUp/Copy"

# List of patterns for folders to exclude from copying
excluded_folders = ["D:/BackUp/origin/Investavimas", "D:/BackUp/origin/Islaidos/Islaidos UK"]

def should_exclude_folder(folder_path):
    """
    Check if a folder should be excluded based on the excluded folders list.
    """
    for pattern in excluded_folders:
        if fnmatch.fnmatch(folder_path.lower(), f"*{pattern.lower()}*"):
            return True
    return False

def copy_files(src, dest):
    """
    Recursively copy files from source to destination, maintaining folder structure.
    """
    try:
        for root, dirs, files in os.walk(src, topdown=True):
            if should_exclude_folder(root):
                # Skip this folder and its contents
                dirs.clear()
                continue

            for file in files:
                source_path = os.path.join(root, file)
                relative_path = os.path.relpath(source_path, src)
                destination_path = os.path.join(dest, relative_path)

                # Ensure the destination directory exists, create it if not
                destination_dir = os.path.dirname(destination_path)
                if not os.path.exists(destination_dir):
                    os.makedirs(destination_dir)

                # Check if the file exists in the destination folder
                if not os.path.exists(destination_path):
                    # File doesn't exist in the destination, so copy it
                    print(f"Copying {source_path} to {destination_path}")
                    shutil.copy2(source_path, destination_path)
                else:
                    # File exists; compare modification timestamps
                    source_mtime = os.path.getmtime(source_path)
                    dest_mtime = os.path.getmtime(destination_path)
                    if source_mtime > dest_mtime:
                        # Source file is newer; copy it to update the destination file
                        print(f"Copying {source_path} to {destination_path} (modified)")
                        shutil.copy2(source_path, destination_path)
    except Exception as e:
        print(f"An error occurred: {e}")

# Example usage:
if __name__ == "__main__":
    copy_files(source_folder, destination_folder)
