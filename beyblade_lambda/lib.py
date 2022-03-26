import base64
import boto3 as boto
import hashlib
import json
import time

from io import BytesIO


try:
    from beyblade_lambda.constants import BEYBLADE_S3_BUCKET, CLOUDFRONT_DISTRIBUTION
except ModuleNotFoundError:
    # To support running for local testing
    from constants import BEYBLADE_S3_BUCKET, CLOUDFRONT_DISTRIBUTION

def upload_processed_data(data_str, data_key):
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


def upload_metadata(metadata, config):
        client = boto.client("s3")
        metadata_str = json.dumps(metadata).encode("utf-8")
        metadata_upload_md5 = base64.b64encode(hashlib.md5(metadata_str).digest()).decode("utf-8")
        client.put_object(
            ACL="private",
            Bucket=BEYBLADE_S3_BUCKET,
            Key=config.get_processed_metadata_key(),
            Body=BytesIO(metadata_str),
            ContentMD5=metadata_upload_md5,
            ContentType="application/json"
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
