#!/usr/bin/env python3
from argparse import ArgumentParser
from glob import glob
from os.path import join

import numpy as np
import pandas as pd


def load_uids_with_duplicate_score(metadata_dir, out_filename, key="dedup-isc-ft-v107-score", threshold=0.604169):
    uids = []
    for parquet_file in glob(join(metadata_dir, "*.parquet")):
        df = pd.read_parquet(parquet_file, columns=["uid", key])
        uids += df[df[key] <= threshold]["uid"].values.tolist()
    processed_uids = np.array([(int(uid[:16], 16), int(uid[16:32], 16)) for uid in uids], np.dtype("u8,u8"))
    processed_uids.sort()
    np.save(out_filename, processed_uids)
    

def main():
    parser = ArgumentParser()
    parser.add_argument("metadata_dir", help="Directory containing the metadata parquet files of a img2dataset-style dataset.")
    parser.add_argument("out_filename", help="Name of the file to write the output to (consistingi of the uids of samples with a duplication score below the threshold).")
    parser.add_argument("-k", "--key", help="The column name used in the metadata parquet file(s) to identify the duplication score.", default="dedup-isc-ft-v107-score")
    parser.add_argument("-t", "--threshold", help="The treshold value used to classify a sample as duplicate.", default=0.604169)
    args = parser.parse_args()
    load_uids_with_duplicate_score(args.metadata_dir, args.out_filename, key=args.key, threshold=args.threshold)


if __name__ == "__main__":
    main()
