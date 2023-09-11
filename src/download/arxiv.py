#!/usr/bin/env python
from argparse import ArgumentParser
from glob import glob
from hashlib import md5
from os import makedirs
from os.path import dirname, exists, getsize, isfile, join
from tarfile import is_tarfile
import xml.etree.ElementTree as ET

from boto3 import client


def md5sum(file_path):
    file_hash = md5()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            file_hash.update(chunk)
    return file_hash.hexdigest()


def verify_integrity(file_path, original_md5sum):
    return md5sum(file_path) == original_md5sum


def directory_size(dir_path):
    return sum(getsize(f) for f in glob(join(dir_path, "**/*"), recursive=True))


def download_file_from_bucket(bucket_name, object_name, file_path):
    s3 = client("s3")
    s3.download_file(bucket_name, object_name, file_path, ExtraArgs={"RequestPayer": "requester"})


def get_manifest(bucket_name, manifest_path="data/download/src/arXiv_src_manifest.xml", manifest_key="src/arXiv_src_manifest.xml"):
    if not exists(manifest_path):
        makedirs(dirname(manifest_path), exist_ok=True)
        download_file_from_bucket(bucket_name, manifest_key, manifest_path)
    return ET.parse(manifest_path).getroot()


def download_arxiv_tars(bucket_name="arxiv", start_item="2001.00001", end_item="2012.15864", max_size=100, output_dir="data/download"):
    max_size_byte = max_size * 1024 ** 3
    downloaded_size = directory_size(output_dir)
    print(f"Already downloaded {downloaded_size} bytes")
    manifest = get_manifest(bucket_name, join(output_dir, "src/arXiv_src_manifest.xml"))
    start_item_found = False
    end_item_found = False
    for file_element in manifest.findall("file"):
        first_item = file_element.find("first_item").text
        if first_item == start_item:
            start_item_found = True
        last_item = file_element.find("last_item").text
        if last_item == end_item:
            end_item_found = True
        if first_item == start_item:
        if start_item_found and not end_item_found:
            filename = file_element.find("filename").text
            print(f"Downloading {filename}")
            size = int(file_element.find("size").text)
            if downloaded_size + size >= max_size_byte:
                print(f"Max size of {max_size} GB reached, stopping.") 
                break
            file_path = join(output_dir, filename)
            if isfile(file_path) and is_tarfile(file_path):
                continue
            makedirs(dirname(file_path), exist_ok=True)
            md5_sum = file_element.find("md5sum").text
            download_file_from_bucket(bucket_name, filename, file_path)
            success = verify_integrity(file_path, md5_sum)
            if not success:
                print(f"Downloading {filename} not successful.")
                continue
            downloaded_size += size


if __name__ == "__main__":
    parser = ArgumentParser()
    parser.add_argument("-m", "--max_size", default=100, type=int)
    parser.add_argument("-s", "--start_item", default="astro-ph0001001")
    parser.add_argument("-e", "--end_item", default="2012.15864")
    parser.add_argument("-o", "--output_dir", default="data/download/arxiv")
    args = parser.parse_args()
    download_arxiv_tars(max_size=args.max_size, start_item=args.start_item)
