"""
Defines main entry point for ETL process.
"""

import sys
import logging
import time
import os
logging.basicConfig(filename="/home/savchuki/projects/dzne-llm/text-extraction/logs/log.txt", level=logging.INFO)

from .execute import Execute

#indir, url, config=None, replace=False
if __name__ == "__main__":
    # print(sys.argv[0], sys.argv[1], sys.argv[2])
    if len(sys.argv) == 2:
        # Running from config
        Execute.run(
            None, # indir
            None, # url
            None, # dbname
            sys.argv[1], # config path
            None # replace
        )
    if len(sys.argv) > 2:
        # Running from command line
        Execute.run(
            sys.argv[1], # indir
            sys.argv[2], # url
            sys.argv[3], # dbname
            None, # keep config as None, originally sys.argv[3] if len(sys.argv) > 3 else None
            False, # keep replace as False, originally sys.argv[4] == "True" if len(sys.argv) > 4 else False
        )
