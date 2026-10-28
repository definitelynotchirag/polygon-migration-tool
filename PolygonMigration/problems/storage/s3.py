"""
S3-compatible storage backend (AWS S3, MinIO, Cloudflare R2, ...).

Configured entirely from environment variables (see settings.STORAGE):
    S3_BUCKET_NAME, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY,
    S3_REGION (default us-east-1), S3_ENDPOINT_URL (empty for AWS).
"""
import logging
import boto3
from botocore.config import Config

from .base import TestCaseStorage

logger = logging.getLogger(__name__)


class S3Storage(TestCaseStorage):
    display_name = "S3-compatible storage"

    def __init__(self, bucket, access_key, secret_key, region="us-east-1", endpoint_url=None):
        if not bucket or not access_key or not secret_key:
            raise ValueError("S3_BUCKET_NAME, S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY must be set")
        self.bucket = bucket
        self.endpoint_url = endpoint_url or None
        self.client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region or "us-east-1",
            endpoint_url=self.endpoint_url,
            # path-style addressing is required by MinIO and harmless for AWS
            config=Config(s3={"addressing_style": "path"}),
        )
        if self.endpoint_url:
            self.display_name = f"S3-compatible storage ({self.endpoint_url})"
        logger.info("S3Storage ready: bucket=%s endpoint=%s", bucket, self.endpoint_url or "aws")

    def upload_bytes(self, key, data):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def list_keys(self, prefix):
        keys = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            keys.extend(obj["Key"] for obj in page.get("Contents", []))
        return keys

    def delete_prefix(self, prefix):
        keys = self.list_keys(prefix)
        for i in range(0, len(keys), 1000):
            batch = [{"Key": k} for k in keys[i:i + 1000]]
            self.client.delete_objects(Bucket=self.bucket, Delete={"Objects": batch, "Quiet": True})
        return len(keys)
