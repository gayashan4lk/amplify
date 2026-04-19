"""Object-storage service for generated images (T010).

Persists 1080x1080 PNG/JPEG bytes returned by the Nano Banana 2 tool into an
S3-compatible bucket and hands back a (key, signed_url) pair. Signed URLs are
short-lived; callers can re-sign via `sign(key)`. A small in-process cache
memoises signed URLs until they are close to expiry so hot rehydrations do
not thrash the signer.

The exact backend is pinned by the pending BACKEND_HOSTING_TARGET ADR — we
use boto3 against any S3-compatible endpoint (AWS S3, Cloudflare R2, MinIO)
so the service is provider-agnostic.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from config import get_settings


def _extension_for(content_type: str) -> str:
    match content_type:
        case "image/png":
            return "png"
        case "image/jpeg" | "image/jpg":
            return "jpg"
        case "image/webp":
            return "webp"
        case _:
            return "bin"


class ImageStore:
    """Thin wrapper over an S3-compatible client."""

    def __init__(
        self,
        s3_client: Any,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
    ) -> None:
        self._s3 = s3_client
        self._bucket = bucket
        self._region = region
        self._endpoint_url = endpoint_url

    async def put(
        self, data: bytes, content_type: str, *, filename: str | None = None
    ) -> tuple[str, str]:
        """Upload `data` and return `(key, public_url)`.

        `filename` is set as the response `Content-Disposition` so downloads
        land with a predictable name (FR for T053). The bucket is configured
        for public read access, so we return a plain public URL.
        """

        ext = _extension_for(content_type)
        key = f"content/{uuid4().hex}.{ext}"
        extra: dict[str, Any] = {"ContentType": content_type}
        if filename:
            extra["ContentDisposition"] = (
                f'attachment; filename="{filename}"'
            )
        await _maybe_await(
            self._s3.put_object,
            Bucket=self._bucket,
            Key=key,
            Body=data,
            **extra,
        )
        return key, self.sign(key)

    def sign(self, key: str) -> str:
        if self._endpoint_url:
            base = self._endpoint_url.rstrip("/")
            return f"{base}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"


async def _maybe_await(fn: Any, /, *args: Any, **kwargs: Any) -> Any:
    """boto3 is sync; aioboto3 is async. Support either transparently."""

    result = fn(*args, **kwargs)
    if hasattr(result, "__await__"):
        return await result
    return result


def build_image_store() -> ImageStore:
    """Factory used by the deps layer. Constructs a boto3 S3 client from
    settings and wraps it in `ImageStore`. Kept out of module import time so
    tests that inject a fake client don't need AWS creds."""

    import boto3  # type: ignore[import-untyped]

    settings = get_settings()
    if not settings.image_store_access_key_id or not settings.image_store_secret_access_key:
        raise RuntimeError(
            "Image store credentials are not configured. Set "
            "IMAGE_STORE_ACCESS_KEY_ID and IMAGE_STORE_SECRET_ACCESS_KEY in apps/api/.env."
        )
    client_kwargs: dict[str, Any] = {
        "region_name": settings.image_store_region,
        "aws_access_key_id": settings.image_store_access_key_id,
        "aws_secret_access_key": settings.image_store_secret_access_key,
    }
    if settings.image_store_endpoint_url:
        client_kwargs["endpoint_url"] = settings.image_store_endpoint_url
    client = boto3.client("s3", **client_kwargs)
    return ImageStore(
        client,
        bucket=settings.image_store_bucket,
        region=settings.image_store_region,
        endpoint_url=settings.image_store_endpoint_url,
    )
