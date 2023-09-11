#!/usr/bin/env python3
import argparse
import os
import tarfile
import jsonlines

def extract_info_from_tar(tar_file, output_file, use_archive_filename):
    with tarfile.open(tar_file, 'r') as archive, jsonlines.open(output_file, mode='a') as writer:
        entries = archive.getnames()
        papers_data = {}
        
        for entry in entries:
            if entry.endswith('.jpg'):
                image_filename_parts = entry.split("-")
                paper_id = image_filename_parts[0]
                image_filename = "-".join(image_filename_parts[1:])
                caption_filename = entry.replace('.jpg', '.txt')
                if caption_filename in entries:
                    with archive.extractfile(caption_filename) as caption_file:
                        caption = caption_file.read().decode('utf-8').strip()
                    if paper_id not in papers_data:
                        papers_data[paper_id] = {"paper_id": paper_id, "figures": []}
                        if use_archive_filename:
                           papers_data[paper_id].update({"archive_filename": os.path.basename(tar_file)})
                    papers_data[paper_id]["figures"].append({
                        "image_filename": image_filename,
                        "caption": caption
                    })
        if papers_data:
             writer.write_all(papers_data.values())

def extract_dataset_metadata(input_dir, output_file, use_archive_filename):
    if os.path.isfile(output_file):
       os.remove(output_file)
    for tar_file in os.listdir(input_dir):
        if tar_file.endswith('.tar'):
            tar_path = os.path.join(input_dir, tar_file)
            extract_info_from_tar(tar_path, output_file, use_archive_filename)

def main():
    parser = argparse.ArgumentParser(description="Process tar files and generate JSONL output")
    parser.add_argument("input_dir", help="Directory containing tar files")
    parser.add_argument("output_file", help="Output JSONL file")
    parser.add_argument("-n", "--use_archive_filename", action="store_true")
    
    args = parser.parse_args()
    
    input_dir = args.input_dir
    output_file = args.output_file
    
    extract_dataset_metadata(input_dir, output_file, args.use_archive_filename)

if __name__ == "__main__":
    main()
