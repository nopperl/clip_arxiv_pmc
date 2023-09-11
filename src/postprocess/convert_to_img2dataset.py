#!/usr/bin/env python3
from argparse import ArgumentParser
from glob import glob
from io import BytesIO
from json import dump, dumps
import os
from os.path import basename, join, splitext
import tarfile
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq


def process_tar_file(tar_file):
    tar_base_name = os.path.splitext(os.path.basename(tar_file))[0]

    with tarfile.open(tar_file, 'r') as tar:
        member_names = tar.getnames()
        jpg_members = [member for member in tar.getmembers() if member.name.endswith('.jpg') and splitext(member.name)[0] + ".txt" in member_names]
        jpg_members.sort(key=lambda x: x.name)
        metadata = {"uid": [], "key": [], "paper_id": [], "original_image_filename": []}
        # TODO: could save all metadata listed in https://github.com/rom1504/img2dataset/blob/main/README.md

        # Create a new in-memory tar file for the updated members
        new_tar_data = BytesIO()
        new_tar = tarfile.open(fileobj=new_tar_data, mode='w')

        for i, member in enumerate(jpg_members):
            new_basename = f"{tar_base_name}{i:06d}"
            new_jpg_name = new_basename + ".jpg"
            new_txt_name = new_basename + ".txt"

            # Extract and rename .jpg and .txt members
            jpg_data = tar.extractfile(member).read()
            new_tarinfo = tarfile.TarInfo(new_jpg_name)
            new_tarinfo.size = len(jpg_data)
            new_tar.addfile(new_tarinfo, BytesIO(jpg_data))

            txt_member = tar.getmember(os.path.splitext(member.name)[0] + ".txt")
            txt_data = tar.extractfile(txt_member).read()
            new_tarinfo = tarfile.TarInfo(new_txt_name)
            new_tarinfo.size = len(txt_data)
            new_tar.addfile(new_tarinfo, BytesIO(txt_data))

            metadata_member = {
                "uid": uuid4().hex,
                "key": new_basename,
                "paper_id": splitext(basename(member.name))[0].split("-")[0],
                "original_image_filename": "-".join(basename(member.name).split("-")[1:]),
            }

            json_tarinfo = tarfile.TarInfo(new_basename + ".json")
            json_bytes = dumps(metadata_member).encode("utf-8")
            json_tarinfo.size = len(json_bytes)
            new_tar.addfile(json_tarinfo, BytesIO(json_bytes))

            # Add metadata
            metadata["uid"].append(metadata_member["uid"])
            metadata["key"].append(metadata_member["key"])
            metadata["paper_id"].append(metadata_member["paper_id"])
            metadata["original_image_filename"].append(metadata_member["original_image_filename"])

        new_tar.close()

    # Replace the original .tar file with the new in-memory tar data
    with open(tar_file, 'wb') as new_tar_file:
        new_tar_file.write(new_tar_data.getvalue())

    return metadata


def save_metadata_to_parquet(tar_filename, metadata):
    base_name = os.path.splitext(tar_filename)[0]
    parquet_filename = base_name + ".parquet"
    table = pa.Table.from_pydict(metadata)
    pq.write_table(table, parquet_filename)


def save_stats_json(tar_filename, count):
    stats_json_filename = splitext(tar_filename)[0] + "_stats.json"
    stats_json = {"count": count, "successes": count}
    with open(stats_json_filename, "w") as stats_json_file:
        dump(stats_json, stats_json_file)


def main():
    parser = ArgumentParser()
    parser.add_argument("input_directory", help="Directory containing .tar files")

    args = parser.parse_args()

    input_directory = args.input_directory

    # Process all .tar files in the directory
    for tar_filename in sorted(glob(join(input_directory, "*.tar"))):
        metadata = process_tar_file(tar_filename)
        save_metadata_to_parquet(tar_filename, metadata)
        save_stats_json(tar_filename, len(next(iter(metadata.values()))))

if __name__ == "__main__":
    main()
