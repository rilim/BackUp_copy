1.	User Input and Configuration:
    • Allow the user to specify the source folders and destination folders.
    • Create a list of exceptions (folders/subfolders to exclude) where users can specify paths they want to skip during copying and deletion.

2.	Copy Files from Source to Destination:
    • Recursively traverse the source folder to find all files and subfolders.
    • For each file found in the source folder, check if it exists in the destination folder:
  	 •• If the file does not exist in the destination folder, copy it over.
  	 •• If the file exists in the destination folder, compare modification timestamps:
  	  ••• If the source file is newer, copy it over to update the destination file.
    • Maintain the folder structure during copying.

3.	Delete Files in Destination Folder:
    • After copying new or updated files, check if there are any files in the destination folder that no longer exist in the source folder.
    • Optionally, prompt the user for confirmation before deleting files in the destination folder.
    • Delete files in the destination folder that no longer exist in the source folder.

4.	Restore Files from Destination to Source:
    • Allow the user to restore deleted files from the destination folder back to the source folder.
    • Optionally, prompt the user for confirmation before restoring files.
  	
5.	Safety Mechanism for Deletions:
    • Implement a safety feature to prevent accidental deletion of files/folders in the source or destination.
    • This could involve asking for confirmation before performing any deletion actions.

6.	Handling Multiple Source and Destination Folders:
    • Allow users to specify multiple source and destination folder pairs.
    • Apply the same copy, delete, and safety mechanisms to each pair.
  	
7.	Logging and Reporting:
    • Log the actions taken by the application, such as which files were copied, deleted, or restored.
  	• Provide a summary report of actions taken and any errors encountered.
