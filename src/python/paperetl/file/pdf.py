"""
PDF processing module
"""

from io import StringIO

import requests

from .tei import TEI

import time
import shutil
import os
import logging
logging.getLogger(__name__)

class PDF:
    """
    Methods to transform medical/scientific PDFs into article objects.
    """

    @staticmethod
    def parse(stream, filename, config):
        """
        Parses a medical/scientific PDF datastream and returns a processed article.

        Args:
            stream: handle to input data stream
            source: text string describing stream source, can be None

        Returns:
            Article
        """

        # Attempt to convert PDF to TEI XML
        xml = PDF.convert(stream)
        logging.debug(xml.getvalue())
        if config and config["xml_dir"]:
            # Save XML file
            filename = ".".join(filename.split(".")[:-1])
            with open(os.path.join(config["xml_dir"], f'{filename}.xml'), 'w') as fd:
                xml.seek(0)
                shutil.copyfileobj(xml, fd)
                xml.seek(0)
        # Parse and return object
        return TEI.parse(xml, filename) if xml else None

    @staticmethod
    def convert(stream):
        """
        Converts a medical/scientific article PDF into TEI XML via a GROBID Web Service API call.

        Args:
            stream: handle to input data stream

        Returns:
            TEI XML stream
        """
        logging.debug("Making GROBID API call")
        # Call GROBID API
        response = requests.post(
            # replacing with the server
            "http://10.0.161.181:8070/api/processFulltextDocument", files={"input": stream, "consolidateFunders": "1", "consolidateHeader": "1", "consolidateCitations": "1", "includeRawAffiliations": "1"}
        )
        time.sleep(7) # wait until next grobid api call

        # Validate request was successful
        if not response.ok:
            logging.info(f"Failed to process file - {response.text}")
            return None

        # Wrap as StringIO
        return StringIO(response.text)
