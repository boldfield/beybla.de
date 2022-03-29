#!/usr/bin/env python
import base64
import hashlib
import os
import time
import mimetypes
import boto3 as boto
from io import BytesIO


BEYBLADE_S3_BUCKET = "beybla.de"
CLOUDFRONT_DISTRIBUTION = "E28YRVB5CTBVQT"


def list_dir(tdir):
    files = []
    for file in os.listdir(tdir):
        if file.startswith(".") or file.endswith(".py"):
            continue
        elif file == "fonts":
            continue
        elif os.path.isdir(os.path.join(tdir, file)):
            files.extend([f"{file}/{p}" for p in list_dir(os.path.join(tdir, file))])
        else:
            files.append(file)
    return files


def upload_files(files):
    client = boto.client("s3")
    for file in files:
        with open(file, "rb") as fs:
            data = fs.read()
        upload_md5 = base64.b64encode(hashlib.md5(data).digest()).decode("utf-8")
        client.put_object(
            ACL="private",
            Bucket=BEYBLADE_S3_BUCKET,
            Key=file,
            Body=data,
            ContentType=mimetypes.guess_type(file)[0]
        )


def invalidate_cloudfront_paths(paths):
    client = boto.client('cloudfront')
    client.create_invalidation(
        DistributionId=CLOUDFRONT_DISTRIBUTION,
        InvalidationBatch={
            "Paths": {
                "Quantity": len(paths),
                "Items": paths
            },
            "CallerReference": str(time.time()),
        }
    )


def main():
    cwd = os.getcwd()
    # This could get limited to only those files that have changed
    print("Finding files to upload...")
    files_to_upload = list_dir(cwd)
    print("Uploading files...")
    upload_files(files_to_upload)
    print("Invalidating files in Cloudfront...")
    invalidate_cloudfront_paths([f"/{p}" for p in files_to_upload])
    print("Done!")


if __name__ == "__main__":
    main()
