#!/usr/bin/env python

from argparse import ArgumentParser
from glob import iglob
from io import BytesIO
from multiprocessing import Process, Pool
from os import cpu_count, makedirs
from os.path import basename, isfile, join, splitext
import re
from subprocess import Popen
import tarfile
from tempfile import NamedTemporaryFile

from PIL import Image, UnidentifiedImageError
from TexSoup import TexSoup
from TexSoup.tokens import MATH_ENV_NAMES
from pdf2image import convert_from_bytes
from pylatexenc.latex2text import LatexNodes2Text


ACCEPTED_IMG_EXTENSIONS = (".jpg", ".jpeg", ".gif", ".png", ".pdf", ".eps", ".ps")


def extract_includegraphics_with_captions(tex_source, graphics, accepted_img_extensions=ACCEPTED_IMG_EXTENSIONS, blacklist_terms=["\\href", "\\url", "\\email"]):
    graphics_wo_ext = [splitext(g)[0] for g in graphics]
    tex_source = re.sub(r'.*\\newcommand.*\n', '', tex_source)  # TODO: handle user defined commmands better
    tex_source = re.sub(r'\\caption[\s\t\n]*{', r'\\caption{', tex_source)
    try:
        soup = TexSoup(tex_source, tolerance=1, skip_envs=MATH_ENV_NAMES + ("$","$$", "itemize", "enumerate"))
    except Exception as e:
        print("Failed parsing tex source, error message:")
        print(e)
        return {}
    graphic_nodes = soup.find_all("includegraphics")
    captions = {}
    for graphic_node in graphic_nodes:
        if len(graphic_node.contents) < 1:
            continue
        graphic_url = graphic_node.text[-1]  # get \includegraphics[...]{URL}
        if graphic_url.endswith(accepted_img_extensions):
            if graphic_url not in graphics:
                continue
        else:
            if graphic_url not in graphics_wo_ext:
                continue
            graphic_url = graphics[graphics_wo_ext.index(graphic_url)]
        figure = graphic_node.parent
        if len(figure.find_all("includegraphics")) > 1:  # skip figures containing multiple graphics
            continue
        caption_node = figure.find("caption")
        if caption_node is None or len(caption_node.args) <= 0:
            continue
        caption = caption_node.args[-1].string
        if any(term in caption for term in blacklist_terms):
            continue
        caption = LatexNodes2Text().latex_to_text(caption)  # tex macros to unicode chars
        caption = " ".join(caption.split())  # sanitize new lines, tabs etc to single white spaces
        captions[graphic_url] = caption
    return captions


def process_tex_file(tex_source, graphics_filenames):
    tex_source = tex_source.decode("ISO-8859-1")
    captions = extract_includegraphics_with_captions(tex_source, graphics_filenames)
    return captions


def process_paper(arxiv_id, paper_fileobj, output_tar, resize_images=True, max_size=512, accepted_img_extensions=ACCEPTED_IMG_EXTENSIONS):
    if not tarfile.is_tarfile(paper_fileobj):
        return  # Non-tar (i.e. single source file) papers are unlikely to contain graphics, so skip
    with tarfile.open(fileobj=paper_fileobj, mode="r:gz") as input_tar:
        image_filenames = []
        image_members = []
        tex_members = []
        for tar_info in input_tar:
            if tar_info.name.endswith(".tex"):
                tex_members.append(tar_info)
            if tar_info.name.endswith(accepted_img_extensions):
                image_members.append(tar_info)
                image_filenames.append(tar_info.name)
        if len(image_filenames) < 1:
            return
        captions = {}
        for tar_info in tex_members:
            tex_file = input_tar.extractfile(tar_info)
            captions.update(process_tex_file(tex_file.read(), image_filenames))  # TODO: join captions of the same graphic if multiple are found
        for tar_info in image_members:
            image_path = tar_info.name
            image_out_path = f"{arxiv_id}-{splitext(basename(image_path))[0]}.jpg"
            caption_out_path = splitext(image_out_path)[0] + ".txt"
            caption = captions.get(image_path)
            if caption is None:
                continue
            image_file = input_tar.extractfile(tar_info)
            if image_path.endswith((".eps", ".ps")):  # EPS files need to be extracted to disk
                image_file_disk = NamedTemporaryFile()
                image_file_disk.write(image_file.read())
                image_file_disk.seek(0)
                image_file = image_file_disk
            with image_file:
                image_file_out = BytesIO()
                try:
                    img = convert_from_bytes(image_file.read())[0] if image_path.endswith(".pdf") else Image.open(image_file)
                except (Image.DecompressionBombError, OSError, UnidentifiedImageError) as e:
                    print(f"Could not load image {image_path}, error message:")
                    print(e)
                    continue
                if resize_images:
                    img.thumbnail((max_size, max_size))
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")
                img.save(image_file_out, format="JPEG")
            figure_info = tarfile.TarInfo(image_out_path)
            figure_info.size = image_file_out.getbuffer().nbytes
            image_file_out.seek(0)
            output_tar.addfile(figure_info, fileobj=image_file_out)
            caption_bytes = caption.encode("utf-8")
            caption_info = tarfile.TarInfo(caption_out_path)
            caption_info.size = len(caption_bytes)
            output_tar.addfile(caption_info, fileobj=BytesIO(caption_bytes))
    return captions


def process_archive(archive_filepath, output_filepath, resize_images=True, max_size=512):
    with tarfile.open(archive_filepath, mode="r") as input_tar, tarfile.open(output_filepath, mode="w") as output_tar:
        for tar_info in input_tar:
            if tar_info.name.endswith(".gz"):
                arxiv_id = splitext(basename(tar_info.name))[0]
                paper_file = input_tar.extractfile(tar_info)
                process_paper(arxiv_id, paper_file, output_tar, resize_images=resize_images, max_size=max_size)


def main(input_dir, output_dir, resize_images=True, max_size=512):
    makedirs(output_dir, exist_ok=True)
    pool = Pool(processes=round(1.5 * cpu_count()))
    for archive_filepath in iglob(join(input_dir, "*.tar")):
        output_filepath = join(output_dir, basename(archive_filepath))
        if isfile(output_filepath) and tarfile.is_tarfile(output_filepath):
            continue
        pool.apply_async(func=process_archive, args=(archive_filepath, output_filepath, resize_images, max_size))
    pool.close()
    pool.join()
    print("done")

# fs = SSHFileSystem("127.0.0.1", username="user", client_keys=["~/.ssh/id_ed25519"], port=52223)  # not thread safe
# fs.find("/home/user/Public/arxiv/src")
# fs.download()  # to local disk
# fs.upload()  # from local disk

if __name__ == "__main__":
    parser = ArgumentParser(description="arXiv data extraction script")
    parser.add_argument("--input_dir", type=str, default="data/download/arxiv/src", help="Input directory")
    parser.add_argument("--output_dir", type=str, default="data/processed/arxiv", help="Output directory")
    parser.add_argument("--no_resize_images", action="store_true", help="Resize images")
    parser.add_argument("--max_size", type=int, default=512, help="Maximum size for mage resizing")
    
    args = parser.parse_args()
    main(args.input_dir, args.output_dir, not args.no_resize_images, args.max_size)
