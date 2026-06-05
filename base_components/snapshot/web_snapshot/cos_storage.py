from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass

import boto3
from botocore.config import Config


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"缺少环境变量: {name}")
    return value


def build_cos_client():
    endpoint = _require_env("COS_ENDPOINT")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=_require_env("COS_ACCESS_KEY"),
        aws_secret_access_key=_require_env("COS_SECRET_KEY"),
        region_name=os.getenv("COS_REGION", "us-east-1"),
        config=Config(signature_version="s3v4"),
    )


@dataclass(slots=True)
class CosStorage:
    bucket: str
    client: object

    @classmethod
    def from_env(cls) -> CosStorage:
        return cls(bucket=_require_env("COS_BUCKET"), client=build_cos_client())

    @staticmethod
    def object_key(data: bytes, ext: str) -> str:
        digest = hashlib.sha256(data).hexdigest()
        return f"snapshots/{digest}{ext}"

    def upload_bytes(self, key: str, body: bytes, content_type: str) -> None:
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
        )

    def public_url(self, key: str) -> str:
        base_url = os.getenv("COS_BASE_URL")
        if base_url:
            return f"{base_url.rstrip('/')}/{key}"
        endpoint = _require_env("COS_ENDPOINT").rstrip("/")
        return f"{endpoint}/{self.bucket}/{key}"

    def upload_snapshot(
        self, screenshot_bytes: bytes, mhtml_bytes: bytes
    ) -> tuple[str, str]:
        screenshot_key = self.object_key(screenshot_bytes, ".png")
        mhtml_key = self.object_key(mhtml_bytes, ".mhtml")
        self.upload_bytes(screenshot_key, screenshot_bytes, "image/png")
        self.upload_bytes(mhtml_key, mhtml_bytes, "application/x-mimearchive")
        return screenshot_key, mhtml_key
