"""
Factory for the configured test-case storage provider.

    from problems.storage import get_storage
    storage = get_storage()          # reads settings.STORAGE_PROVIDER
    storage.upload_test_case(problem_id, 1, "input", "output")

Set STORAGE_PROVIDER=s3 (AWS / MinIO / R2) or STORAGE_PROVIDER=azure in .env.
"""
from django.conf import settings

from .base import TestCaseStorage, test_case_keys, problem_prefix  # noqa: F401


def get_storage() -> TestCaseStorage:
    provider = (getattr(settings, "STORAGE_PROVIDER", "s3") or "s3").lower()
    if provider == "s3":
        from .s3 import S3Storage
        return S3Storage(
            bucket=settings.S3_BUCKET_NAME,
            access_key=settings.S3_ACCESS_KEY_ID,
            secret_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
        )
    if provider == "azure":
        from .azure import AzureBlobStorage
        return AzureBlobStorage(
            account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            username=settings.AZURE_USERNAME,
            password=settings.AZURE_PASSWORD,
            container_name=settings.AZURE_CONTAINER_NAME,
        )
    raise ValueError(f"Unsupported STORAGE_PROVIDER '{provider}' (expected 's3' or 'azure')")
