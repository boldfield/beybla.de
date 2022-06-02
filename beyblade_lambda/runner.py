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
    import beyblade_lambda.ca as cali
    import beyblade_lambda.wa as wash
except ModuleNotFoundError:
    # To support running for local testing
    import ca as cali
    import wa as wash


def main(debug=False, force_refresh=False):
    # TODO: convert to asyncio
    cali.run(debug=debug, force_refresh=force_refresh)
    wash.run(debug=debug, force_refresh=force_refresh)


def lambda_event(*args, **kwargs):
    main()


if __name__ == "__main__":
    main(debug=True, force_refresh=False)
