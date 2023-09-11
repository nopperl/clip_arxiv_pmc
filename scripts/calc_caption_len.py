import argparse
import os
import tarfile

def calculate_average_text_length(directory):
    total_length = 0
    file_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".tar"):
                tar_path = os.path.join(root, file)
                with tarfile.open(tar_path, "r") as tar:
                    for member in tar.getmembers():
                        if member.name.endswith(".txt"):
                            txt_file = tar.extractfile(member)
                            if txt_file is not None:
                                text = txt_file.read().decode("utf-8")
                                total_length += len(text)
                                file_count += 1

    if file_count == 0:
        return 0

    average_length = total_length / file_count
    return average_length

def main():
    parser = argparse.ArgumentParser(description="Calculate the average text length of *.txt files in a directory of tar files.")
    parser.add_argument("directory", help="The directory containing the tar files.")
    args = parser.parse_args()

    average_length = calculate_average_text_length(args.directory)

    print(f"Average text length of *.txt files in {args.directory}: {average_length:.2f} characters")

if __name__ == "__main__":
    main()

