#!/usr/bin/env python3
import base64
import boto3 as boto
import hashlib
import json
import math
import openpyxl
import PyPDF2 as pypdf
import requests
import time

from botocore.exceptions import ClientError
from datetime import datetime, tzinfo
from pprint import pprint
from io import BytesIO

try:
    from beyblade_lambda.config import StorageConfig
    from beyblade_lambda.constants import (
        AMERICA_PACIFIC, BEYBLADE_S3_BUCKET, BEYBLADE_URL
    )
    from beyblade_lambda.wa_constants import (
        EPI_DATA_URL, EPI_DEATHS_WORKSHEET_NAME,
        EPI_COLUMNS_NAME_MAP, EPI_COUNTY_OF_INTEREST,
        EPI_DEATHS_FNAME_TMPL,
        BREAKTHROUGH_REPORT_FNAME_TMPL, BREAKTHROUGH_DATA_URL,
        BREAKTHROUGH_REPORT_DATE_PATTERN, BREAKTHROUGH_DATE_PATTERN,
        BREAKTHROUGH_CASE_COUNT_PATTERN,
        BREAKTHROUGH_HOSPITALIZED_PCT_PATTERN,
        BREAKTHROUGH_DEATH_COUNT_PATTERN, BREAKTHROUGH_DEATH_PCT_PATTERN,
    )
    from beyblade_lambda.exceptions import DependencyError
except ModuleNotFoundError:
    # To support running for local testing
    from config import StorageConfig
    from constants import (
        AMERICA_PACIFIC, BEYBLADE_S3_BUCKET, BEYBLADE_URL
    )
    from wa_constants import (
        EPI_DATA_URL, EPI_DEATHS_WORKSHEET_NAME,
        EPI_COLUMNS_NAME_MAP, EPI_COUNTY_OF_INTEREST,
        EPI_DEATHS_FNAME_TMPL,
        BREAKTHROUGH_REPORT_FNAME_TMPL, BREAKTHROUGH_DATA_URL,
        BREAKTHROUGH_REPORT_DATE_PATTERN, BREAKTHROUGH_DATE_PATTERN,
        BREAKTHROUGH_CASE_COUNT_PATTERN,
        BREAKTHROUGH_HOSPITALIZED_PCT_PATTERN,
        BREAKTHROUGH_DEATH_COUNT_PATTERN, BREAKTHROUGH_DEATH_PCT_PATTERN,
    )
    from exceptions import DependencyError


CONFIG = StorageConfig("wa")


def process_breakthrough_date(dstring):
    dt = datetime.strptime(dstring, '%B %d, %Y')
    dt_tz = AMERICA_PACIFIC.localize(dt)
    return int(time.mktime(dt_tz.timetuple()))


def refresh_epi_data(debug=False):
    resp = requests.get(EPI_DATA_URL)
    xlsx_data = BytesIO(resp.content)
    xlsx = openpyxl.load_workbook(xlsx_data, True)
    deaths_worksheet = xlsx[EPI_DEATHS_WORKSHEET_NAME]

    # There is something broken about this spreadsheet and is read in w/o dimensional information.
    # To fix the issue we need to reset dimensions and then recalculate them.
    # See: related: https://foss.heptapod.net/openpyxl/openpyxl/-/issues/1611
    deaths_worksheet.reset_dimensions()
    deaths_worksheet.calculate_dimension(force=True)
    column_map = {}
    records = []
    for row in deaths_worksheet.rows:
        if not column_map:
            for i, cell in enumerate(row):
                if cell.value in EPI_COLUMNS_NAME_MAP:
                    column_map[EPI_COLUMNS_NAME_MAP[cell.value]] = i
        elif row[column_map["county"]].value == EPI_COUNTY_OF_INTEREST:
            dt_tz = AMERICA_PACIFIC.localize(row[column_map["date"]].value)
            ts = int(time.mktime(dt_tz.timetuple()))
            records.append({
                "date": ts,
                "deaths": row[column_map["deaths"]].value,
                "rolling_average": row[column_map["rolling_average"]].value
            })

    records_str = json.dumps(records).encode("utf-8")
    records_md5 = hashlib.md5(records_str).hexdigest()
    records_fname = EPI_DEATHS_FNAME_TMPL.format(md5=records_md5)
    records_data_key = f"{CONFIG.get_epi_data_prefix().strip('/')}/{records_fname}"

    client = boto.client("s3")
    try:
        # check to see if this key exists
        client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=records_data_key)
    except ClientError as ex:
        if not ex.response['Error']['Code'] == 'NoSuchKey':
            raise
        if not debug:
            record_upload_md5 = base64.b64encode(hashlib.md5(records_str).digest()).decode("utf-8")
            client.put_object(
                ACL="private",
                Bucket=BEYBLADE_S3_BUCKET,
                Key=records_data_key,
                Body=BytesIO(records_str),
                ContentMD5=record_upload_md5,
                ContentType="application/json"
            )

            records_md5_key = f"{records_data_key}.md5"
            records_md5_md5 = base64.b64encode(hashlib.md5(records_md5.encode("utf-8")).digest()).decode("utf-8")
            client.put_object(
                ACL="private",
                Bucket=BEYBLADE_S3_BUCKET,
                Key=records_md5_key,
                Body=BytesIO(records_md5.encode("utf-8")),
                ContentMD5=records_md5_md5,
                ContentType="text/plain"
            )

    return records[-1]["date"], records


def refresh_breakthrough_data(debug=False, force_refresh=False):
    # Get existing data
    processed_data = _get_processed_breakthrough_data(debug=debug, force_refresh=force_refresh)
    processed_data = sorted(processed_data, key=lambda x: x["report_date"])
    processed_md5s = [r["report_md5"] for r in processed_data]
    # Get latest data
    latest_report, latest_data = _get_latest_breakthrough_data()
    if latest_data["report_md5"] not in processed_md5s:
        if not debug:
            _uplode_latest_breakthrough_report(latest_report, latest_data)
        processed_data.append(latest_data)
        processed_md5s.append(latest_data["report_md5"])

    return processed_data[-1]["report_date"], processed_data


def _process_breakthrough_report(breakthrough_pdf):
    records_md5 = hashlib.md5(breakthrough_pdf).hexdigest()
    pdfp = pypdf.PdfFileReader(BytesIO(breakthrough_pdf)) 
    text = ""
    for p in range(pdfp.numPages):
        text += pdfp.getPage(p).extractText()

    stripped_text = text.replace('\n', "")
    # Just let parsing errors bubble up for now to trigger emails from lambda
    start_date_raw, end_date_raw = BREAKTHROUGH_DATE_PATTERN.match(stripped_text).groups()
    try:
        report_date_raw = BREAKTHROUGH_REPORT_DATE_PATTERN.match(stripped_text).groups()[0]
    except:
        raise

    report_date, start_date, end_date = (
        process_breakthrough_date(report_date_raw),
        process_breakthrough_date(start_date_raw),
        process_breakthrough_date(end_date_raw)
    )
    case_count = int(BREAKTHROUGH_CASE_COUNT_PATTERN.match(stripped_text).groups()[0].replace(",", ""))
    hospitalized_pct = int(BREAKTHROUGH_HOSPITALIZED_PCT_PATTERN.match(stripped_text).groups()[0])
    hospitalized_count = int(math.floor(float(case_count) * hospitalized_pct/100.0))
    death_count_match = BREAKTHROUGH_DEATH_COUNT_PATTERN.match(stripped_text)
    if not death_count_match:
        death_pct = float(BREAKTHROUGH_DEATH_PCT_PATTERN.match(stripped_text).groups()[0])
        death_count = int(math.floor(float(case_count) * death_pct/100.0))
    else:
        death_count = int(death_count_match.groups()[0])

    return {
        "report_date": report_date,
        "start_date": start_date,
        "end_date": end_date,
        "case_count": case_count,
        "death_count": death_count,
        "report_md5": records_md5,
    }


def _upload_processed_report(report_data, data_key):
    client = boto.client("s3")
    report_json_str = json.dumps(report_data).encode("utf-8")
    record_md5 = base64.b64encode(hashlib.md5(report_json_str).digest()).decode("utf-8")
    client.put_object(
        ACL="private",
        Bucket=BEYBLADE_S3_BUCKET,
        Key=data_key,
        Body=BytesIO(report_json_str),
        ContentMD5=record_md5,
        ContentType="application/json"
    )


def _get_processed_report(report_key, debug=False, force_refresh=False):
    json_key = report_key.replace("pdf", "json")
    client = boto.client("s3")
    if not force_refresh:
        try:
            resp_json = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=json_key)
            return json.loads(resp_json["Body"].read())
        except ClientError as ex:
            if not ex.response['Error']['Code'] == 'NoSuchKey':
                raise

    resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=report_key)
    report = resp["Body"].read()
    record = _process_breakthrough_report(report)

    if not debug:
        _upload_processed_report(record, json_key)

    return record


def _get_processed_breakthrough_data(debug=False, force_refresh=False):
    records, objs, last_key = [], [], None
    client = boto.client("s3")
    while True:
        resp = client.list_objects(
            Bucket=BEYBLADE_S3_BUCKET,
            Prefix=CONFIG.get_breakthrough_data_prefix(),
            Marker=last_key or ""
        )
        objs.extend(resp["Contents"])
        if resp["IsTruncated"]:
            last_key = objs[-1]["Key"]
        else:
            break

    for obj in objs:
        if not obj["Key"].endswith("pdf"):
            continue
        records.append(_get_processed_report(obj["Key"], debug=debug, force_refresh=force_refresh))
    return records


def _get_latest_breakthrough_data():
    resp = requests.get(BREAKTHROUGH_DATA_URL)
    if resp.status_code != 200:
        raise DependencyError(
            f"Attempt to retrieve latest breakthrough report returned status code: {resp.status_code}"
        )
    # Let errors associated with parsing bubble up
    return resp.content, _process_breakthrough_report(resp.content)


def _uplode_latest_breakthrough_report(latest_report, latest_data):
    client = boto.client("s3")
    dt_tz = datetime.fromtimestamp(latest_data["report_date"], AMERICA_PACIFIC)
    report_fname = BREAKTHROUGH_REPORT_FNAME_TMPL.format(
        date=dt_tz.strftime("%Y-%m-%d")
    )
    report_key = f"{CONFIG.get_breakthrough_data_prefix().rstrip('/')}/{report_fname}"
    report_md5 = base64.b64encode(hashlib.md5(latest_report).digest()).decode("utf-8")
    client.put_object(
        ACL="private",
        Bucket=BEYBLADE_S3_BUCKET,
        Key=report_key,
        Body=latest_report,
        ContentMD5=report_md5,
        ContentType="application/pdf"
    )

    report_md5_key = f"{report_key}.md5"
    report_md5 = latest_data["report_md5"].encode("utf-8")
    report_md5_md5 = base64.b64encode(hashlib.md5(report_md5).digest()).decode("utf-8")
    client.put_object(
        ACL="private",
        Bucket=BEYBLADE_S3_BUCKET,
        Key=report_md5_key,
        Body=BytesIO(report_md5),
        ContentMD5=report_md5_md5,
        ContentType="text/plain"
    )

    report_json_key = report_key.replace("pdf", "json")
    report_json_str = json.dumps(latest_data).encode("utf-8")
    _upload_processed_data(report_json_str, report_json_key)


def _get_metadata():
    client = boto.client("s3")
    try:
        resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=CONFIG.get_processed_metadata_key())
        return json.loads(resp["Body"].read())
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
        }
    }


def _upload_processed_data(data_str, data_key):
    client = boto.client("s3")
    data_upload_md5 = base64.b64encode(hashlib.md5(data_str).digest()).decode("utf-8")
    client.put_object(
        ACL="private",
        Bucket=BEYBLADE_S3_BUCKET,
        Key=data_key,
        Body=BytesIO(data_str),
        ContentMD5=data_upload_md5,
        ContentType="application/json"
    )


def _process_epi_data(records, debug=False):
    cumulative = 0
    for i in range(len(records)):
        if i == 0:
            cumulative = records[i].get("cumulative_deaths", 0)
            records[i]["cumulative_deaths"] = cumulative + records[i]["deaths"]
        else:
            cumulative = records[i-1].get("cumulative_deaths", 0)
            records[i]["cumulative_deaths"] = cumulative + records[i]["deaths"]

    records_str = json.dumps(records).encode("utf-8")
    records_key = CONFIG.get_processed_epi_data_key(hashlib.md5(records_str).hexdigest())
    if not debug:
        _upload_processed_data(records_str, records_key)
    return f"{BEYBLADE_URL.rstrip('/')}/{records_key}"


def _process_breakthrough_data(records, debug=False):
    remove_indices = []
    for i in range(len(records)):
        if i == 0 or i == len(records) - 1:
            continue
        if records[i]["end_date"] == records[i+1]["end_date"]:
            remove_indices.append(i)

    for i in sorted(remove_indices, reverse=True):
        del records[i]

    for i in range(len(records)):
        if i == 0:
            start_date, end_date = (
                datetime.fromtimestamp(records[i]["start_date"], AMERICA_PACIFIC),
                datetime.fromtimestamp(records[i]["end_date"], AMERICA_PACIFIC),
            )
            num_weeks = (end_date - start_date).days / 7
            records[i]["rolling_average"] = records[i]["death_count"] / num_weeks
            records[i]["cumulative_deaths"] = records[i]["death_count"]
        else:
            start_date, end_date = (
                datetime.fromtimestamp(records[i-1]["end_date"], AMERICA_PACIFIC),
                datetime.fromtimestamp(records[i]["end_date"], AMERICA_PACIFIC),
            )
            num_days = (end_date - start_date).days
            deaths_delta = records[i]["death_count"] - records[i-1]["death_count"]
            if deaths_delta < 0:
                deaths_delta = 0
            records[i]["rolling_average"] = deaths_delta / num_days
            records[i]["cumulative_deaths"] = records[i]["death_count"]

    records_str = json.dumps(records).encode("utf-8")
    records_key = CONFIG.get_processed_breakthrough_data_key(hashlib.md5(records_str).hexdigest())
    if not debug:
        _upload_processed_data(records_str, records_key)
    return f"{BEYBLADE_URL.rstrip('/')}/{records_key}"


def run(debug=False, force_refresh=False):
    metadata, updated = _get_metadata(), False
    records_update_time, records = refresh_epi_data(debug=debug)
    if records_update_time > metadata["epi"]["update_time"]:
        metadata["epi"]["url"] = _process_epi_data(records, debug=debug)
        metadata["epi"]["update_time"] = records_update_time
        updated = True

    breakthrough_update_time, breakthrough_records = refresh_breakthrough_data(debug=debug, force_refresh=force_refresh)
    if breakthrough_update_time > metadata["breakthrough"]["update_time"]:
        metadata["breakthrough"]["url"] = _process_breakthrough_data(breakthrough_records, debug=debug)
        metadata["breakthrough"]["update_time"] = breakthrough_update_time
        updated = True
    if debug:
        pprint(records[-25:])
        pprint(breakthrough_records)

    if updated and not debug:
        client = boto.client("s3")
        metadata_str = json.dumps(metadata).encode("utf-8")
        metadata_upload_md5 = base64.b64encode(hashlib.md5(metadata_str).digest()).decode("utf-8")
        client.put_object(
            ACL="private",
            Bucket=BEYBLADE_S3_BUCKET,
            Key=CONFIG.get_processed_metadata_key(),
            Body=BytesIO(metadata_str),
            ContentMD5=metadata_upload_md5,
            ContentType="application/json"
        )
