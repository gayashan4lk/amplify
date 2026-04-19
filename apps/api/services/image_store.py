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

import time
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from config import get_settings

_SIGN_TTL_SECONDS = 3600  # 1h signed URLs
_CACHE_SAFETY_MARGIN = 60  # refresh signed URLs 60s before expiry


@dataclass
class _SignedEntry:
    url: str
    expires_at: float


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

    def __init__(self, s3_client: Any, *, bucket: str) -> None:
        self._s3 = s3_client
        self._bucket = bucket
        self._cache: dict[str, _SignedEntry] = {}

    async def put(
        self, data: bytes, content_type: str, *, filename: str | None = None
    ) -> tuple[str, str]:
        """Upload `data` and return `(key, signed_url)`.

        `filename` is set as the response `Content-Disposition` so downloads
        from the signed URL land with a predictable name (FR for T053).
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
        now = time.time()
        cached = self._cache.get(key)
        if cached and cached.expires_at - _CACHE_SAFETY_MARGIN > now:
            return cached.url
        url = self._s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=_SIGN_TTL_SECONDS,
        )
        self._cache[key] = _SignedEntry(url=url, expires_at=now + _SIGN_TTL_SECONDS)
        return url


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
    client = boto3.client("s3", region_name=settings.image_store_region)
    return ImageStore(client, bucket=settings.image_store_bucket)
