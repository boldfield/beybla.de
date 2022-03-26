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
    from ca_constants import BREAKTHROUGH_DATA_URL, BREAKTHROUGH_COLUMNS, EPI_AREA_OF_INTEREST, EPI_COLUMNS, EPI_DATA_URL
    from config import StorageConfig
    from constants import (
        AMERICA_PACIFIC, BEYBLADE_S3_BUCKET, BEYBLADE_URL
    )
    from lib import upload_processed_data, upload_metadata, invalidate_cloudfront_paths

CONFIG = StorageConfig("ca")


def refresh_breakthrough_data(debug=False, force_refresh=False):
    resp = requests.get(BREAKTHROUGH_DATA_URL)
    breakthrough_reader = csv.reader(resp.content.decode('utf-8').split('\r\n'))
    column_map, records = {}, []
    for row in breakthrough_reader:
        if not row:
            continue
        if not column_map:
            for i, item in enumerate(row):
                if item in BREAKTHROUGH_COLUMNS:
                    column_map[item] = i
        else:
            dt = datetime.strptime(row[column_map["date"]], "%Y-%m-%d")
            dt_tz = AMERICA_PACIFIC.localize(dt)
            ts = int(time.mktime(dt_tz.timetuple()))
            records.append({
                "date": ts,
                "deaths": int(row[column_map["vaccinated_deaths"]]) + int(row[column_map["boosted_deaths"]]),
                "rolling_average": 0
            })
            if len(records) > 7:
                records[-1]["rolling_average"] = statistics.mean([x["deaths"] for x in records[-7:]])

    return records[-1]["date"], records


def refresh_epi_data(debug=False):
    resp = requests.get(EPI_DATA_URL)
    epi_reader = csv.reader(resp.content.decode('utf-8').split('\r\n'))
    column_map, records = {}, [{"date": None, "deaths": 0, "rolling_average": 0}]
    for row in epi_reader:
        if not row:
            continue
        if not column_map:
            for i, item in enumerate(row):
                if item in EPI_COLUMNS:
                    column_map[item] = i
        elif not row[column_map["area"]] == EPI_AREA_OF_INTEREST:
            continue
        elif not row[column_map["date"]] or row[column_map["date"]] == "None":
            # Note: Some entries show ""None"" in the date field.  These are records which do not have
            # dates associated with them; however they have been included as they are necessary to arrive
            # at the correct totals. The automated compilation of cumulative totals treats ""None"" as the
            # earliest date, which is why the actual earliest data in the table may have large numbers in
            # the cumulative total columns. Users who want to graph cumulative trends should consider
            # subtracting values for "None" dates to avoid displaying this artifact in their trend lines.

            reported_deaths = int(float(row[column_map["reported_deaths"]] if row[column_map["reported_deaths"]] else '0'))
            records[0]["deaths"] += reported_deaths
        else:
            dt = datetime.strptime(row[column_map["date"]], "%Y-%m-%d")
            dt_tz = AMERICA_PACIFIC.localize(dt)
            ts = int(time.mktime(dt_tz.timetuple()))
            reported_deaths = int(float(row[column_map["reported_deaths"]] if row[column_map["reported_deaths"]] else '0'))
            records.append({
                "date": ts,
                "deaths": reported_deaths,
                "rolling_average": 0
            })

    # If no deaths were recorded with date == None, delete the row from the records
    if records[0]["deaths"] == 0:
        del records[0]
    else:
        records[0]["date"] = records[1]["date"] - 24 * 3600

    for i in range(7, len(records)):
        records[i]["rolling_average"] = statistics.mean([x["deaths"] for x in records[i-7:i]])

    return records[-1]["date"], records


def _process_epi_data(records, debug=False):
    cumulative = 0
    for i in range(len(records)):
        if i == 0:
            records[i]["cumulative_deaths"] = records[i]["deaths"]
        else:
            cumulative = records[i-1].get("cumulative_deaths", 0)
            records[i]["cumulative_deaths"] = cumulative + records[i]["deaths"]

    records_str = json.dumps(records).encode("utf-8")
    records_key = CONFIG.get_processed_epi_data_key(hashlib.md5(records_str).hexdigest())
    if not debug:
        upload_processed_data(records_str, records_key)
    return f"{BEYBLADE_URL.rstrip('/')}/{records_key}"


def _process_breakthrough_data(records, debug=False):
    cumulative = 0
    for i in range(len(records)):
        if i == 0:
            records[i]["cumulative_deaths"] = records[i]["deaths"]
        else:
            cumulative = records[i-1].get("cumulative_deaths", 0)
            records[i]["cumulative_deaths"] = cumulative + records[i]["deaths"]

    records_str = json.dumps(records).encode("utf-8")
    records_key = CONFIG.get_processed_breakthrough_data_key(hashlib.md5(records_str).hexdigest())
    if not debug:
        upload_processed_data(records_str, records_key)
    return f"{BEYBLADE_URL.rstrip('/')}/{records_key}"


def _get_metadata():
    client = boto.client("s3")
    try:
        resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=CONFIG.get_processed_metadata_key())
        metadata = json.loads(resp["Body"].read())
        metadata["state_label"] = "California"
        metadata["human_label"] = "Californians"
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
        "human_label": "Californians",
        "state_label": "California"
    }


def run(debug=False, force_refresh=False):
    metadata, updated = _get_metadata(), False

    records_update_time, records = refresh_epi_data(debug=debug)
    if records_update_time > metadata["epi"]["update_time"] or (force_refresh and not debug):
        metadata["epi"]["url"] = _process_epi_data(records, debug=debug)
        metadata["epi"]["update_time"] = records_update_time
        updated = True

    breakthrough_update_time, breakthrough_records = refresh_breakthrough_data(debug=debug, force_refresh=force_refresh)
    if breakthrough_update_time > metadata["breakthrough"]["update_time"] or (force_refresh and not debug):
        metadata["breakthrough"]["url"] = _process_breakthrough_data(breakthrough_records, debug=debug)
        metadata["breakthrough"]["update_time"] = breakthrough_update_time
        updated = True

    if debug:
        pprint(records)
        pprint(breakthrough_records)
    elif updated:
        upload_metadata(metadata, CONFIG)
        invalidate_cloudfront_paths(["/" + CONFIG.get_processed_metadata_key()])
