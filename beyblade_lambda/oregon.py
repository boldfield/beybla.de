#!/usr/bin/env python3
import base64
import boto3 as boto
import csv
import hashlib
import json
import math
import openpyxl
import PyPDF2 as pypdf
import requests
import statistics
import time

from botocore.exceptions import ClientError
from datetime import datetime, tzinfo
from pprint import pprint
from io import BytesIO

try:
    from beyblade_lambda.ca_constants import BREAKTHROUGH_DATA_URL, BREAKTHROUGH_COLUMNS, EPI_AREA_OF_INTEREST, EPI_COLUMNS, EPI_DATA_URL
    from beyblade_lambda.config import StorageConfig
    from beyblade_lambda.constants import (
        AMERICA_PACIFIC, BEYBLADE_S3_BUCKET, BEYBLADE_URL
    )
    from beyblade_lambda.lib import upload_processed_data, upload_metadata, invalidate_cloudfront_paths
except ModuleNotFoundError:
    from or_constants import BREAKTHROUGH_DATA_URL, BREAKTHROUGH_COLUMNS, EPI_AREA_OF_INTEREST, EPI_COLUMNS, EPI_DATA_URL
    from config import StorageConfig
    from constants import (
        AMERICA_PACIFIC, BEYBLADE_S3_BUCKET, BEYBLADE_URL
    )
    from lib import upload_processed_data, upload_metadata, invalidate_cloudfront_paths

CONFIG = StorageConfig("or")


def refresh_breakthrough_data(debug=False, force_refresh=False):
    pass


def _get_metadata():
    client = boto.client("s3")
    try:
        resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=CONFIG.get_processed_metadata_key())
        metadata = json.loads(resp["Body"].read())
        metadata["state_label"] = "Oregon"
        metadata["human_label"] = "Oregonians"
        return metadata
    except ClientError as ex:
        if not ex.response['Error']['Code'] == 'NoSuchKey':
            raise

    return {
        "epi": {
            "update_time": 0,
            "url": None,
        },
        "breakthrough": {
            "update_time": 0,
            "url": None,
        },
        "human_label": "Oregonians",
        "state_label": "Oregon"
    }


def run(debug=False, force_refresh=False):
    metadata, updated = _get_metadata(), False

    breakthrough_update_time, breakthrough_records = refresh_breakthrough_data(debug=debug, force_refresh=force_refresh)
