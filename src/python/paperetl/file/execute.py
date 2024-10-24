"""
Transforms and loads medical/scientific files into an articles database.
"""

import gzip
import os

from multiprocessing import Process, Queue
import psutil
import json

from ..factory import Factory

from .arx import ARX
from .csvf import CSV
from .pdf import PDF
from .pmb import PMB
from .tei import TEI

import logging
logging.getLogger(__name__)


class Execute:
    """
    Transforms and loads medical/scientific files into an articles database.
    """

    # Completion process signal
    COMPLETE = 1

    @staticmethod
    def mode(source, extension):
        """
        Determines file open mode for source file.

        Args:
            source: text string describing stream source
            extension: data format

        Returns:
            file open mode
        """

        return (
            "rb"
            if extension == "pdf" or (source and source.lower().startswith("pubmed"))
            else "r"
        )

    @staticmethod
    def parse(path, filename, extension, compress, config):
        """
        Parses articles from file at path.

        Args:
            path: path to input file
            filename: text string describing stream source
            extension: data format
            config: path to config directory
        """

        logging.info(f"Processing: {path}")

        # Determine if file needs to be open in binary or text mode
        mode = Execute.mode(filename, extension)

        with gzip.open(path, mode) if compress else open(
            path, mode, encoding="utf-8" if mode == "r" else None
        ) as stream:
            if extension == "pdf":
                yield PDF.parse(stream, filename, config)
            elif extension == "xml":
                if filename and filename.lower().startswith("arxiv"):
                    yield from ARX.parse(stream, filename)
                elif filename and filename.lower().startswith("pubmed"):
                    yield from PMB.parse(stream, filename, config)
                else:
                    yield TEI.parse(stream, filename)
            elif extension == "csv":
                yield from CSV.parse(stream, filename)

    @staticmethod
    def process(inputs, outputs):
        """
        Main worker process loop. Processes file paths stored in inputs and writes articles
        to outputs. Writes a final message upon completion.

        Args:
            inputs: inputs queue
            outputs: outputs queue
        """

        try:
            # Process until inputs queue is exhausted
            while not inputs.empty():
                params = inputs.get()
                for result in Execute.parse(*params):
                    outputs.put(result)
        finally:
            # Write message that process is complete
            outputs.put(Execute.COMPLETE)

    @staticmethod
    def scan(indir, config, inputs):
        """
        Scans for files in indir and writes to inputs queue.

        Args:
            indir: input directory
            config: path to config directory, if any
            inputs: inputs queue

        Returns:
            total number of items put into inputs queue
        """

        # Total number of files put into input queue
        total = 0

        # Recursively walk directory looking for files
        for root, _, files in sorted(os.walk(indir)):
            for f in sorted(files):
                # Extract file extension
                parts = f.lower().split(".")
                extension, compress = (
                    (parts[-2], True) if parts[-1] == "gz" else (parts[-1], False)
                )

                # Check if file ends with accepted extension
                if any(extension for ext in ["csv", "pdf", "xml"] if ext == extension):
                    # Build full path to file
                    path = os.path.join(root, f)

                    # Write parameters to inputs queue
                    inputs.put((path, f, extension, compress, config))
                    total += 1

        return total

    @staticmethod
    def save(processes, outputs, db):
        """
        Main consumer loop that saves articles created by worker processes.

        Args:
            processes: list of worker processes
            outputs: outputs queue
            db: output database
        """

        # Read output from worker processes
        empty, complete = False, 0
        while not empty:
            # Get next result
            result = outputs.get()

            # Mark process as complete if all workers are complete and output queue is empty
            if result == Execute.COMPLETE:
                complete += 1
                empty = len(processes) == complete and outputs.empty()

            # Save article, this method will skip duplicates based on entry date
            elif result:
                db.save(result)

    @staticmethod
    def least_used_cpus():
        # Get per-core CPU utilization
        cpu_usage = psutil.cpu_percent(percpu=True)
        cpu_usage = list(zip(range(len(cpu_usage)), cpu_usage)) # Add core number
        cpu_usage = sorted(cpu_usage, key=lambda x: x[1], reverse=True)
        least_used_cpus = [x[0] for x in cpu_usage]
        return least_used_cpus
    
    @staticmethod
    def run(indir, url, dbname, config=None, replace=False):
        """
        Main execution method.

        Args:
            indir: input directory
            url: database url
            config: path to config directory, if any
            replace: if true, a new database will be created, overwriting any existing database
        """

        if config:
            logging.info(f"Using config: {config}")
            with open(config) as fd:
                config = json.load(fd)
            indir = config["indir"]
            url = config["url"]
            dbname = config["dbname"]
            replace = config["replace"]

        # Build database connection
        db = Factory.create(url, dbname, replace)

        # Create queues, limit size of output queue
        inputs, outputs = Queue(), Queue(30000)

        # Scan input directory and add files to inputs queue
        total = Execute.scan(indir, config, inputs)
        
        # Start worker processes
        processes = []
        num_workers = min(total, os.cpu_count())
        worker_ids = Execute.least_used_cpus()[:num_workers]
        logging.info(f"Starting {num_workers} processes on cpus: {worker_ids}")
        for _ in worker_ids:
            process = Process(target=Execute.process, args=(inputs, outputs))
            process.start()
            processes.append(process)

        # Read results from worker processes and save to database
        Execute.save(processes, outputs, db)

        # Complete and close database
        db.complete()
        db.close()

        # Wait for processes to terminate
        for process in processes:
            process.join()
