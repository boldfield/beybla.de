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

import beyblade_lambda.wa as wa


def main():
    wa.run()


def lambda_event(*args, **kwargs):
    main()


if __name__ == "__main__":
    main()
