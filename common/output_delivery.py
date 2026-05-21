#!/usr/bin/env python3
"""Store generated outputs in Google Cloud Storage and notify progress sites."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_PREFIX = "Output"
DEFAULT_IMAGE_PREFIX = "Image"
DATA_URL_PATTERN = re.compile(r"^data:(?P<content_type>[-\w.+/]+);base64,(?P<data>.*)$", re.DOTALL)
SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
SENSITIVE_METADATA_KEYS = {
    "authorization",
    "password",
    "response_url",
    "secret",
    "slack_response_url",
    "token",
}


class DeliveryError(RuntimeError):
    """Raised when output delivery cannot be completed."""


@dataclass(frozen=True)
class OutputDeliveryConfig:
    bucket: str
    output_prefix: str = DEFAULT_OUTPUT_PREFIX
    image_prefix: str = DEFAULT_IMAGE_PREFIX
    public_base_url: str | None = None
    progress_webhook_url: str | None = None
    progress_shared_secret: str | None = None
    progress_authorization: str | None = None
    progress_timeout_seconds: float = 5.0
    slack_response_timeout_seconds: float = 5.0

    @classmethod
    def from_env(cls) -> "OutputDeliveryConfig":
        bucket = os.getenv("GCS_OUTPUT_BUCKET")
        if not bucket:
            raise DeliveryError("GCS_OUTPUT_BUCKET is required")

        return cls(
            bucket=bucket,
            output_prefix=clean_prefix(os.getenv("GCS_OUTPUT_PREFIX", DEFAULT_OUTPUT_PREFIX)),
            image_prefix=clean_prefix(os.getenv("GCS_IMAGE_PREFIX", DEFAULT_IMAGE_PREFIX)),
            public_base_url=os.getenv("GCS_PUBLIC_BASE_URL"),
            progress_webhook_url=os.getenv("PROGRESS_WEBHOOK_URL"),
            progress_shared_secret=os.getenv("PROGRESS_SHARED_SECRET"),
            progress_authorization=os.getenv("PROGRESS_AUTHORIZATION"),
            progress_timeout_seconds=float(os.getenv("PROGRESS_TIMEOUT_SECONDS", "5.0")),
            slack_response_timeout_seconds=float(os.getenv("SLACK_RESPONSE_TIMEOUT_SECONDS", "5.0")),
        )


@dataclass(frozen=True)
class UploadedOutput:
    bucket: str
    object_name: str
    link: str
    content_type: str
    size_bytes: int


def clean_prefix(prefix: str) -> str:
    cleaned = prefix.strip("/")
    if not cleaned:
        raise DeliveryError("GCS output prefixes cannot be empty")
    return cleaned


def safe_filename(filename: str | None, content_type: str | None = None) -> str:
    candidate = Path(filename or "").name.strip()
    if not candidate:
        candidate = f"image-{uuid.uuid4().hex}"

    stem, extension = os.path.splitext(candidate)
    stem = SAFE_FILENAME_PATTERN.sub("-", stem).strip(".-")
    if not stem:
        stem = f"image-{uuid.uuid4().hex}"

    if not extension:
        extension = mimetypes.guess_extension(content_type or "") or ".bin"
    elif not re.fullmatch(r"\.[A-Za-z0-9]+", extension):
        extension = mimetypes.guess_extension(content_type or "") or ".bin"

    return f"{stem}{extension}"[:180]


def build_image_object_name(
    config: OutputDeliveryConfig,
    filename: str | None,
    content_type: str,
    *,
    now: datetime | None = None,
    task_id: str | None = None,
) -> str:
    current_time = now or datetime.now(timezone.utc)
    timestamp = current_time.strftime("%Y%m%dT%H%M%SZ")
    safe_task = SAFE_FILENAME_PATTERN.sub("-", task_id or "").strip(".-")
    task_part = f"{safe_task}-" if safe_task else ""
    return "/".join(
        [
            config.output_prefix,
            config.image_prefix,
            f"{timestamp}-{task_part}{safe_filename(filename, content_type)}",
        ]
    )


def decode_image_payload(image_payload: str, content_type: str | None = None) -> tuple[bytes, str]:
    match = DATA_URL_PATTERN.match(image_payload)
    if match:
        content_type = match.group("content_type")
        image_payload = match.group("data")

    try:
        image_bytes = base64.b64decode(image_payload, validate=True)
    except binascii.Error as exc:
        raise DeliveryError("image payload must be valid base64 or a base64 data URL") from exc

    if not image_bytes:
        raise DeliveryError("image payload is empty")

    return image_bytes, content_type or "application/octet-stream"


def object_link(config: OutputDeliveryConfig, object_name: str) -> str:
    encoded_object_name = urllib.parse.quote(object_name)
    if config.public_base_url:
        return f"{config.public_base_url.rstrip('/')}/{encoded_object_name}"
    return f"https://storage.googleapis.com/{config.bucket}/{encoded_object_name}"


def upload_image_bytes(
    image_bytes: bytes,
    *,
    filename: str | None,
    content_type: str,
    config: OutputDeliveryConfig | None = None,
    task_id: str | None = None,
    metadata: dict[str, str] | None = None,
) -> UploadedOutput:
    config = config or OutputDeliveryConfig.from_env()
    try:
        from google.cloud import storage
    except ImportError as exc:
        raise DeliveryError("google-cloud-storage is required to upload outputs") from exc

    client = storage.Client()
    bucket = client.bucket(config.bucket)

    for folder in (
        f"{config.output_prefix}/",
        f"{config.output_prefix}/{config.image_prefix}/",
    ):
        blob = bucket.blob(folder)
        if not blob.exists():
            blob.upload_from_string(b"", content_type="application/x-directory")

    object_name = build_image_object_name(
        config,
        filename,
        content_type,
        task_id=task_id,
    )
    blob = bucket.blob(object_name)
    if metadata:
        blob.metadata = metadata
    blob.upload_from_string(image_bytes, content_type=content_type)

    return UploadedOutput(
        bucket=config.bucket,
        object_name=object_name,
        link=object_link(config, object_name),
        content_type=content_type,
        size_bytes=len(image_bytes),
    )


def public_metadata(metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    if not metadata:
        return {}
    return {
        key: value
        for key, value in metadata.items()
        if key.lower() not in SENSITIVE_METADATA_KEYS
    }


def progress_payload(
    uploaded_output: UploadedOutput,
    *,
    title: str,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event": "task.completed",
        "status": "completed",
        "task_id": task_id,
        "title": title,
        "completed_at": int(time.time()),
        "links": [
            {
                "type": "image",
                "url": uploaded_output.link,
                "bucket": uploaded_output.bucket,
                "object_name": uploaded_output.object_name,
                "content_type": uploaded_output.content_type,
                "size_bytes": uploaded_output.size_bytes,
            }
        ],
        "metadata": metadata or {},
    }


def post_webhook_json(
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
    timeout_seconds: float = 5.0,
) -> tuple[int, str]:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {
        "Content-Type": "application/json",
        "User-Agent": "slack-output-delivery/1.0",
    }
    if headers:
        request_headers.update(headers)

    request = urllib.request.Request(
        url,
        data=body,
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        return 0, f"request_failed: {exc}"


def post_progress_completed(
    uploaded_output: UploadedOutput,
    *,
    title: str,
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    config: OutputDeliveryConfig | None = None,
) -> tuple[int, str] | None:
    config = config or OutputDeliveryConfig.from_env()
    if not config.progress_webhook_url:
        return None

    headers = {}
    if config.progress_shared_secret:
        headers["X-Progress-Secret"] = config.progress_shared_secret
    if config.progress_authorization:
        headers["Authorization"] = config.progress_authorization

    return post_webhook_json(
        config.progress_webhook_url,
        progress_payload(
            uploaded_output,
            title=title,
            task_id=task_id,
            metadata=metadata,
        ),
        headers=headers,
        timeout_seconds=config.progress_timeout_seconds,
    )


def is_slack_response_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.netloc == "hooks.slack.com"
        and parsed.path.startswith("/commands/")
    )


def slack_completion_payload(
    uploaded_output: UploadedOutput,
    *,
    title: str,
    text: str | None = None,
    response_type: str = "ephemeral",
) -> dict[str, Any]:
    safe_response_type = response_type if response_type in {"ephemeral", "in_channel"} else "ephemeral"
    message = text or f"{title} completed: {uploaded_output.link}"
    return {
        "response_type": safe_response_type,
        "replace_original": False,
        "text": message,
    }


def post_slack_response(
    slack_response_url: str | None,
    uploaded_output: UploadedOutput,
    *,
    title: str,
    text: str | None = None,
    response_type: str = "ephemeral",
    config: OutputDeliveryConfig | None = None,
) -> tuple[int, str] | None:
    if not slack_response_url:
        return None
    if not is_slack_response_url(slack_response_url):
        return 0, "invalid_slack_response_url"

    config = config or OutputDeliveryConfig.from_env()
    return post_webhook_json(
        slack_response_url,
        slack_completion_payload(
            uploaded_output,
            title=title,
            text=text,
            response_type=response_type,
        ),
        timeout_seconds=config.slack_response_timeout_seconds,
    )


def deliver_image_output(
    image_payload: str,
    *,
    filename: str | None = None,
    content_type: str | None = None,
    title: str = "Image output",
    task_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    slack_response_url: str | None = None,
    slack_text: str | None = None,
    slack_response_type: str = "ephemeral",
    config: OutputDeliveryConfig | None = None,
) -> dict[str, Any]:
    config = config or OutputDeliveryConfig.from_env()
    image_bytes, detected_content_type = decode_image_payload(image_payload, content_type)
    safe_metadata = public_metadata(metadata)
    upload_metadata = {key: str(value) for key, value in safe_metadata.items()}
    uploaded_output = upload_image_bytes(
        image_bytes,
        filename=filename,
        content_type=detected_content_type,
        config=config,
        task_id=task_id,
        metadata=upload_metadata,
    )
    progress_result = post_progress_completed(
        uploaded_output,
        title=title,
        task_id=task_id,
        metadata=safe_metadata,
        config=config,
    )
    slack_result = post_slack_response(
        slack_response_url,
        uploaded_output,
        title=title,
        text=slack_text,
        response_type=slack_response_type,
        config=config,
    )
    return {
        "ok": True,
        "output": asdict(uploaded_output),
        "progress": {
            "notified": progress_result is not None,
            "status": progress_result[0] if progress_result else None,
            "body": progress_result[1] if progress_result else None,
        },
        "slack_response": {
            "notified": slack_result is not None,
            "status": slack_result[0] if slack_result else None,
            "body": slack_result[1] if slack_result else None,
        },
    }


def parse_metadata(raw_metadata: str | None) -> dict[str, Any]:
    if not raw_metadata:
        return {}
    parsed = json.loads(raw_metadata)
    if not isinstance(parsed, dict):
        raise DeliveryError("--metadata-json must decode to an object")
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload an image output and notify progress webhook.")
    parser.add_argument("--image", required=True, help="Local image file path")
    parser.add_argument("--filename", help="Stored filename. Defaults to the image basename.")
    parser.add_argument("--content-type", help="Image content type")
    parser.add_argument("--task-title", default="Image output")
    parser.add_argument("--task-id")
    parser.add_argument("--metadata-json")
    args = parser.parse_args()

    image_path = Path(args.image)
    content_type = args.content_type or mimetypes.guess_type(image_path.name)[0]
    result = deliver_image_output(
        base64.b64encode(image_path.read_bytes()).decode("ascii"),
        filename=args.filename or image_path.name,
        content_type=content_type,
        title=args.task_title,
        task_id=args.task_id,
        metadata=parse_metadata(args.metadata_json),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
