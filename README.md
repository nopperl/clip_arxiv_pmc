# Training CLIP models on Data extracted from Scientific Papers

  * Data and Models: https://huggingface.co/nopperl/clip-arxiv-pmc
  * arXiv dataset: https://huggingface.co/datasets/nopperl/arxiv-image-text
  * PMC dataset: https://huggingface.co/datasets/nopperl/pmc-image-text

This repo contains code to collect image-text pairs from figures in scientific papers from the [arXiv](https://arxiv.org) and [PubMed Central](https://www.ncbi.nlm.nih.gov/pmc/) repositories. This data can be used to train [CLIP](https://arxiv.org/abs/2103.00020) models.

## Setup

### Requirements

Setup a [virtualenv](https://docs.python.org/3/library/venv.html) or [conda environment](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#creating-an-environment-with-commands). For example:

```
conda create --name clip_arxiv_pmc -c conda-forge python=3.11
conda activate clip_arxiv_pmc
```

Requires [Ghostscript](https://ghostscript.readthedocs.io/en/latest/Install.html) and [Poppler](https://poppler.freedesktop.org/). Can be installed e.g. using conda:

    conda install -c conda-forge ghostscript poppler

Install the required python packages:

    pip install -r requirements.txt

#### AWS
arXiv data is downloaded from an AWS S3 bucket. For this, set credentials using the environment variables `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. Alternatively, set them using `awscli`:

```
pip install awscli
awscli configure
```

## Data collection

### arXiv
Download all arXiv papers up to the end of 2020 from their S3 bucket.

    python src/download/arxiv.py

NOTE: since the data is in a requester-pays bucket, the download script by default only downloads 100GB of data (the free tier limit). To download all files (~1.4TB), call the script like:

    python src/download/arxiv.py --max_size 4000

This will incur charges to your AWS account (roughly 300$ at the time of writing). Alternatively, you can download the data in parts by using the `--start_item` and `--end_item` parameters.

Extract images and captions from the downloaded data. The images are automatically resized to 512px. This can be changed using the `--no_resize_images` and `--max_size` parameters.

    python src/process/arxiv.py

Since there may be errors during the script, run the following script to fix issues with the output:

    python src/postprocess/heal_tar_files.py data/processed/arxiv

Finally, rename the tar files to make them compatible with [WebDataset](https://github.com/webdataset/webdataset).

    src/postprocess/rename_tar.sh data/processed/arxiv

### PMC

Download PMC files and extract images and captions. Again, the images are automatically resized to 512px.

    python src/process/pmc.py

Convert the extracted data into the [WebDataset](https://github.com/webdataset/webdataset) format:

```
src/postprocess/convert_pmc_to_tar.sh data/processed/pmc
src/postprocess/heal_tar_files.py  data/processed/pmc
src/postprocess/rename_tar.sh data/processed/pmc
find data/processed/pmc -type d -delete
```

The last step is optional.

## Conversion to [img2dataset](https://github.com/rom1504/img2dataset) format

To use the dataset properly with existing packages (such as those provided by [DataComp](https://datacomp.ai), the collected WebDataset needs to be converted into the format specified by [img2dataset](https://github.com/rom1504/img2dataset). This can be done inplace using:

```
src/postprocess/convert_to_img2dataset.py data/processed/arxiv
src/postprocess/convert_to_img2dataset.py data/processed/pmc
```

## Decontamination

Since the dataset was assembled from a wide range of papers, it might contain images that are also present in evaluation datasets. In order to properly evaluate models trained using the dataset, it is important to remove those images. This decontamination is performed against the datasets contained in the [DataComp](https://datacomp.ai) evaluation suite, which covers most publically available CLIP evaluation datasets.

Following [Gadre et al.](https://arxiv.org/abs/2304.14108), the similarity of images in the dataset to the evaluation datasets is measured using [the model by Yokoo](https://github.com/lyakaap/ISC21-Descriptor-Track-1st). Similarity scores for all samples are calculated using the [dataset2metadata](https://github.com/mlfoundations/dataset2metadata) package:

```
dataset2metadata --yml config/decontamination_arxiv.yaml
dataset2metadata --yml config/decontamination_pmc.yaml
```

The resulting metadata containing sample uids and similarity scores can now be used to decontaminate the dataset. Following [Gadre et al.](https://arxiv.org/abs/2304.14108), samples with a score lower than 0.604169 are classified as clean. These uids are filtered and stored in a numpy file:

```
src/postprocess/apply_deduplication_filter.py data/postprocessed/arxiv/metadata data/postprocessed/arxiv/metadata/decontaminated.npy
src/postprocess/apply_deduplication_filter.py data/postprocessed/pmc/metadata data/postprocessed/arxiv/metadata/decontaminated.npy
```

Next, follow the installation steps of [the DataComp repo](https://github.com/mlfoundations/datacomp). Finally, the contaminated samples are removed from the dataset by resharding it using the filtered uids:

```
mkdir data/postprocessed/arxiv/shards
python $datacomp_dir/resharder.py -i data/processed/arxiv -o data/postprocessed/arxiv/shards -s data/postprocessed/arxiv/metadata/decontaminated.npy
mkdir data/postprocessed/pmc/shards
python $datacomp_dir/resharder.py -i data/processed/pmc -o data/postprocessed/pmc/shards -s data/postprocessed/arxiv/metadata/decontaminated.npy
```

The `$datacomp_dir` variable needs to point to the root directory of the DataComp repo.

The decontaminated datasets are now located at `data/postprocessed/arxiv` and `data/postprocessed/pmc`, respectively.

## Training

The data in the `/data/postprocessed` directory can be used to train CLIP models. This section gives instructions on how to do so using the code provided by [DataComp](https://datacomp.ai).

If not already done, install DataComp by following the installation steps of [the repo](https://github.com/mlfoundations/datacomp). To train on the collected data, append `/data/postprocessed/arxiv/shards` and `data/postprocessed/pmc/shards` to the `--data_dir` parameter.

For example, training the small scale CLIP on the CommonPool, arXiv and PMC datasets:

```
ARXIV_PMC_DIR=$HOME/clip_arxiv_pmc/data/postprocessed  # Set to the correct directory
data_dir=data/commonpool
scale=small
num_gpus=4  # Replace with actually available number of GPUs
output_dir=output
cd
git clone https://github.com/mlfoundations/datacomp
cd datacomp
bash create_env.sh
conda activate datacomp
python download_upstream.py --scale $scale --data_dir $COMMONPOOL_DIR
torchrun --nproc_per_node $num_gpus train.py --scale $scale --data_dir $ARXIV_PMC_DIR/arxiv/shards::$ARXIV_PMC_DIR/pmc/shards::$data_dir/shards --output_dir $output_dir --exp_name arxiv_and_pmc_and_commonpool
```

## Statistics

The average caption length of a dataset (in [WebDataset](https://github.com/webdataset/webdataset) format) can be calculated using:

    python scripts/calc_caption_len.py data/postprocessed/arxiv/shards

The total amount of image and text files in the dataset can be calculated using:

    scripts/count_tar_members.sh data/postprocessed/arxiv/shards 

