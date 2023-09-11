#!/usr/bin/env python
from argparse import ArgumentParser
from ftplib import FTP
from io import BytesIO
from multiprocessing import Process, Pool
from os import cpu_count, makedirs
from os.path import basename, isdir, join, splitext
from pathlib import Path
import tarfile
from typing import Optional, Tuple
from urllib.parse import urljoin
from urllib.request import urlopen

from lxml import etree
from PIL import Image


def add_bytes_to_tar(tar_file, name, file_bytes):
    info = tarfile.TarInfo(name)
    info.size = len(file_bytes)
    tar.addfile(info, fileobj=BytesIO(file_bytes))


def extract_caption_per_figure_from_xml(xml_file, image_filenames=None):
    tree = etree.parse(xml_file)
    captions = {}
    for figure in tree.findall(".//fig"):
        result = extract_caption(figure)
        if result is None:
            continue
        caption, figure_id = result
        if image_filenames is not None:
            graphic_exists = figure_id in (splitext(basename(i))[0] for i in image_filenames)
            if not graphic_exists:
                continue
        captions[figure_id] = caption
    return captions

def extract_caption(figure: etree.Element) -> Optional[Tuple[str, str]]:
    if figure.get("fig-type", "Figure") != "Figure":
        return None  # do not consider tables etc, fail open
    lang_attr = next((k for k in figure.attrib if k.endswith("lang")), None)
    if lang_attr is not None and figure.get(lang_attr).lower().startswith("en"):
        return None  # filter non-english captions, fail open
    caption_element = figure.find("caption")
    if caption_element is None:
        return None
    caption = "".join(caption_element.itertext())
    if caption.isspace():
        return None
    graphic = figure.find("graphic")
    if graphic is None:
        return None
    href = graphic.get(next(k for k in graphic.attrib if k.endswith("href")))
    return caption, href


def extract_figures_and_captions_from_archive(archive_fileobj, output_dir, resize_images=True, max_size=512):
    with tarfile.open(fileobj=archive_fileobj, mode="r:gz") as input_tar:
        image_filenames = []
        image_members = []
        xml_file = None
        for tar_info in input_tar:
            if tar_info.name.endswith(".nxml"):
                xml_file = input_tar.extractfile(tar_info)
                # xml_filepath = join(temp_dir, tar_info.name)
            if tar_info.name.endswith(".jpg"):
                image_members.append(tar_info)
                image_filenames.append(tar_info.name)
        if xml_file is None:
            return
        captions = extract_caption_per_figure_from_xml(xml_file, image_filenames)
        if len(captions) == 0:
            return
        makedirs(output_dir, exist_ok=True)
        for tar_info in image_members:
            figure_id = splitext(basename(tar_info.name))[0]
            caption = captions.get(figure_id)
            if caption is None:
                continue
            image_file = input_tar.extractfile(tar_info)
            img = Image.open(image_file)
            if resize_images:
                img.thumbnail((max_size, max_size))
            img.save(join(output_dir, figure_id + ".jpg"), format="JPEG")
            with open(join(output_dir, figure_id + ".txt"), "w", encoding="utf-8") as caption_file:
                caption_file.write(caption)


def process_ftp_subdir(paper_filenames, https_url, output_dir, resize_images=True, max_size=512, temp_dir=None):
    if temp_dir is not None:
        makedirs(temp_dir, exist_ok=True)
    for paper_filename in paper_filenames:
        paper_output_dir = join(output_dir, basename(paper_filename)[:-len(".tar.gz")])
        if isdir(paper_output_dir):
            continue
        paper_url = urljoin(https_url, paper_filename)
        paper_fileobj = BytesIO(urlopen(paper_url).read())  # download using TLS 
        extract_figures_and_captions_from_archive(paper_fileobj, paper_output_dir, resize_images, max_size)


def main(output_dir, ftp_root_dir, ftp_domain, https_url, resize_images=True, max_size=512):
    ftp = FTP(ftp_domain)
    ftp.login()
    ftp.cwd(ftp_root_dir)
    pool = Pool(processes=round(1.5 * cpu_count()))
    for level_1_dir in ftp.nlst():
        for level_2_dir in ftp.nlst(level_1_dir):
            tar_output_dir = join(output_dir, level_2_dir)
            paper_filenames = [join(ftp_root_dir, i) for i in ftp.nlst(level_2_dir) if i.endswith(".tar.gz")]
            makedirs(tar_output_dir, exist_ok=True)
            pool.apply_async(func=process_ftp_subdir, args=(paper_filenames, https_url, tar_output_dir, resize_images, max_size))
    pool.close()
    pool.join()
    print("done")


if __name__ == "__main__":
    parser = ArgumentParser(description="PubMed Central retrieval script")
    parser.add_argument("--no_resize_images", action="store_true", help="Resize images")
    parser.add_argument("--max_size", type=int, default=512, help="Maximum size for mage resizing")
    parser.add_argument("--output_dir", type=str, default="data/processed/pmc", help="Output directory")
    parser.add_argument("--ftp_root_dir", type=str, default="pub/pmc/oa_package", help="PubMed FTP service root directory")
    parser.add_argument("--ftp_domain", type=str, default="ftp.ncbi.nlm.nih.gov", help="PubMed FTP service domain")
    parser.add_argument("--https_url", type=str, default="https://ftp.ncbi.nlm.nih.gov", help="PubMed FTP service HTTPS URL")
    
    args = parser.parse_args()
    main(args.output_dir, args.ftp_root_dir, args.ftp_domain, args.https_url, not args.no_resize_images, args.max_size)
