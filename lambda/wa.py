#!/usr/bin/env python
import base64
import boto3 as boto
import hashlib
import json
import math
import openpyxl
import PyPDF2 as pypdf
import re
import requests
import time

from botocore.exceptions import ClientError
from datetime import datetime, tzinfo
from pprint import pprint
from io import BytesIO


class DependencyError(Exception):
    pass


BEYBLADE_S3_BUCKET = "beybla.de"

## EPI DATA CONSTANTS ##
EPI_DATA_URL = "https://doh.wa.gov/sites/default/files/legacy/Documents/1600/coronavirus/data-tables//EpiCurve_Count_Cases_Hospitalizations_Deaths.xlsx"
EPI_PREFIX = "static/epi/wa/"
EPI_DEATHS_WORKSHEET_NAME = "Deaths"  # Fragile... but so is working with xlsx data...
EPI_COLUMNS = [
    "Earliest Specimen Collection Date",
    "County",
    "Deaths",
    "Deaths (7-Day Average)",
]
EPI_COLUMNS_NAME_MAP = {
    "Earliest Specimen Collection Date": "date",
    "County": "county",
    "Deaths": "deaths",
    "Deaths (7-Day Average)": "deaths_seven_day_average",
}
EPI_COUNTY_OF_INTEREST = "Statewide"
EPI_DEATHS_FNAME_TMPL = "epi_deaths_data.{md5}.json"

## BREAKTHROUGH DATA CONSTANTS ##
BREAKTHROUGH_DATA_PREFIX = "static/reports/wa/"
BREAKTHROUGH_REPORT_FNAME_TMPL = "{date}-420-339-VaccineBreakthroughReport.pdf"
BREAKTHROUGH_DATA_URL = "https://doh.wa.gov/sites/default/files/2022-02/420-339-VaccineBreakthroughReport.pdf"
BREAKTHROUGH_REPORT_DATE_PATTERN = re.compile(
    r".*Washington State Department of Health\s?\s?([\w]+ [\d]{1,2}, [\d]{4}).*"
)
BREAKTHROUGH_DATE_PATTERN = re.compile(
    r".*At a Glance \(\s?data from ([\w]+ [\d]{1,2}, [\d]{4})\s?-?\s?([\w]+ [\d]{1,2}, [\d]{4})\s?\).*"
)
BREAKTHROUGH_CASE_COUNT_PATTERN = re.compile(
    r".*\s([\d,]+)\s+SARS-CoV-2\s?vaccine\s?breakthrough\s?cases\s?have\s?been\s?identified.*"
)
BREAKTHROUGH_HOSPITALIZED_PCT_PATTERN = re.compile(
    r".*\s([\d]{1,2})% were hospitalized.*"
)
BREAKTHROUGH_DEATH_COUNT_PATTERN = re.compile(
    r".*\s([\d]+) people died of COVID-related illness.*"
)
BREAKTHROUGH_DEATH_PCT_PATTERN = re.compile(
    r".*\s([\d\.]{1,3})% died of COVID-related illness.*"
)

def process_breakthrough_date(dstring):
    return int(time.mktime(datetime.strptime(dstring, '%B %d, %Y').timetuple()))


def refresh_epi_data():
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
                if cell.value in EPI_COLUMNS:
                    column_map[EPI_COLUMNS_NAME_MAP[cell.value]] = i
        elif row[column_map["county"]].value == EPI_COUNTY_OF_INTEREST:
            dt = row[column_map["date"]].value
            ts = int(time.mktime(dt.timetuple()))
            records.append({
                "date": ts,
                "deaths": row[column_map["deaths"]].value,
                "deaths_seven_day_average": row[column_map["deaths_seven_day_average"]].value
            })

    records_str = json.dumps(records).encode("utf-8")
    records_md5 = hashlib.md5(records_str).hexdigest()
    records_fname = EPI_DEATHS_FNAME_TMPL.format(md5=records_md5)
    records_data_key = f"{EPI_PREFIX.strip('/')}/{records_fname}"

    modified_dt = None
    client = boto.client("s3")
    try:
        resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=records_data_key)
        modified_dt = resp["LastModified"]
    except ClientError as ex:
        if not ex.response['Error']['Code'] == 'NoSuchKey':
            raise
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

        resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=records_data_key)
        modified_dt = resp["LastModified"]

    records_update_time = int(time.mktime(modified_dt.timetuple()))


    return records_update_time, records


def refresh_breakthrough_data():
    # Get existing data
    processed_data = _get_processed_breakthrough_data()
    processed_data = sorted(processed_data, key=lambda x: x["report_date"])
    processed_md5s = [r["report_md5"] for r in processed_data]
    # Get latest data
    latest_report, latest_data = _get_latest_breakthrough_data()
    if latest_data["report_md5"] not in processed_md5s:
        _uplode_latest_breakthrough_report(latest_report, latest_data)
        processed_data.append(latest_data)
        processed_md5s.append(latest_data["report_md5"])

    return processed_data[-1]["report_date"], processed_data


def _process_breakthrough_data(breakthrough_pdf):
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
        print(stripped_text)
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


def _upload_processed_data(data_key, report_data):
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


def _get_processed_report(report_key):
    json_key = report_key.replace("pdf", "json")
    client = boto.client("s3")
    try:
        resp_json = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=json_key)
        return json.loads(resp_json["Body"].read())
    except ClientError as ex:
        if not ex.response['Error']['Code'] == 'NoSuchKey':
            raise

    resp = client.get_object(Bucket=BEYBLADE_S3_BUCKET, Key=report_key)
    report = resp["Body"].read()
    record = _process_breakthrough_data(report)

    _upload_processed_data(json_key, record)

    return record


def _get_processed_breakthrough_data():
    records, objs, last_key = [], [], None
    client = boto.client("s3")
    while True:
        resp = client.list_objects(
            Bucket=BEYBLADE_S3_BUCKET,
            Prefix=BREAKTHROUGH_DATA_PREFIX,
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
        records.append(_get_processed_report(obj["Key"]))
    return records


def _get_latest_breakthrough_data():
    resp = requests.get(BREAKTHROUGH_DATA_URL)
    if resp.status_code != 200:
        raise DependencyError(
            f"Attempt to retrieve latest breakthrough report returned status code: {resp.status_code}"
        )
    # Let errors associated with parsing bubble up
    return resp.content, _process_breakthrough_data(resp.content)


def _uplode_latest_breakthrough_report(latest_report, latest_data):
    client = boto.client("s3")
    dt = datetime.fromtimestamp(latest_data["report_date"])
    report_fname = BREAKTHROUGH_REPORT_FNAME_TMPL.format(
        date=dt.strftime("%Y-%m-%d")
    )
    report_key = f"{BREAKTHROUGH_DATA_PREFIX.rstrip('/')}/{report_fname}"
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
    _upload_processed_data(report_json_key, latest_data)


def run():
    records_update_time, records = refresh_epi_data()
    breakthrough_update_time, breakthrough_records = refresh_breakthrough_data()
