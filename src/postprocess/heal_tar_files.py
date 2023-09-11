import os
from glob import iglob
import argparse
from shutil import move
import io
import tarfile


def list_unreadable_tar_files(directory):
    unreadable_tar_files = []

    # Iterate through files in the directory
    for file_path in iglob(os.path.join(directory, "*.tar")):
       try:
           # Attempt to open the tar file
           with tarfile.open(file_path, 'r') as tar_file:
               tar_file.getmembers()
       except tarfile.ReadError:
           # Handle the exception if the tar file is unreadable
           unreadable_tar_files.append(file_path)

    return unreadable_tar_files


def extract_and_compress_files(tar_filenames):
    for tar_filename in tar_filenames:
        # Extract the tar file
        with tarfile.open(tar_filename, 'r') as tar:
            # Create a new tar file to store the compressed files
            output_tar_filename = f"{os.path.splitext(tar_filename)[0]}_compressed.tar"
            with tarfile.open(output_tar_filename, 'w') as output_tar:
                while True:
                    try:
                        member = tar.next()
                        if member is None:
                            break
                        # Extract the file
                        file_content = tar.extractfile(member).read()
                    except tarfile.ReadError:
                        break
                    # Create a new member with the same name in the output tar file
                    new_member = tarfile.TarInfo(name=member.name)
                    new_member.size = len(file_content)
                    # Compress and add the file to the output tar
                    output_tar.addfile(new_member, fileobj=io.BytesIO(file_content))
            move(output_tar_filename, tar_filename)

        print(f"Files from {tar_filename} extracted and compressed to {output_tar_filename}")


def main():
    parser = argparse.ArgumentParser(description="List unreadable tar files in a directory.")
    parser.add_argument("directory", help="The directory to search for tar files.")
    args = parser.parse_args()

    unreadable_files = list_unreadable_tar_files(args.directory)
    for unreadable_file in unreadable_files:
        print(unreadable_file)
    extract_and_compress_files(unreadable_files)


if __name__ == "__main__":
    main()
