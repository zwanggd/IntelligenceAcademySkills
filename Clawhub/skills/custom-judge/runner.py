#!/usr/bin/env python3
"""Thin HTTP adapter for the custom-judge skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_BUNDLE_DIR = "judge_input"
DEFAULT_RESULTS_DIR = "artifacts/judge_results"
DEFAULT_CONFIG_PATH = "configs/judge_provider.local.json"
DEFAULT_REQUEST_PATH = "/judge"
DEFAULT_TIMEOUT_MS = 60000
DEFAULT_RETRY_COUNT = 0
DEFAULT_RETRY_BACKOFF_MS = 1000
DEFAULT_VERIFY_TLS = True
DEFAULT_AUTH_HEADER = "Authorization"
DEFAULT_TOKEN_ENV_VAR = "JUDGE_API_TOKEN"
DEFAULT_JUDGE_VERSION = "v1"
SOURCE_SKILL = "custom-judge"
ADAPTER_VERSION = "custom-judge-http-adapter-v2"


class JudgeAdapterError(Exception):
    """Base adapter error."""

    code = "judge_adapter_error"
    stage = "adapter"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        stage: str | None = None,
        retryable: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.details = details
        self.stage = stage if stage is not None else self.stage
        self.retryable = retryable if retryable is not None else self.retryable


class BundleValidationError(JudgeAdapterError):
    code = "bundle_validation_error"
    stage = "bundle_validation"


class ConfigValidationError(JudgeAdapterError):
    code = "config_validation_error"
    stage = "config_validation"


class HttpRequestError(JudgeAdapterError):
    code = "http_request_error"
    stage = "http_request"
    retryable = True


class ResponseValidationError(JudgeAdapterError):
    code = "response_validation_error"
    stage = "response_validation"


@dataclass
class RequestContext:
    judge_version: str
    request_id: str
    idempotency_key: str
    run_id: str
    question_id: str
    bundle_hash: str
    source_skill: str
    adapter_version: str
    request_generated_at: str
    request_started_at: str | None = None
    request_completed_at: str | None = None


@dataclass
class ProviderSettings:
    base_url: str
    path: str
    timeout_ms: int
    auth_header_name: str | None
    auth_token: str | None
    retry_count: int
    retry_backoff_ms: int
    verify_tls: bool

    @property
    def request_url(self) -> str:
        return urllib.parse.urljoin(_normalize_base_url(self.base_url), self.path.lstrip("/"))


def _normalize_base_url(base_url: str) -> str:
    return base_url if base_url.endswith("/") else f"{base_url}/"


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _compute_bundle_hash(
    manifest: dict[str, Any],
    answer: dict[str, Any],
    question_markdown: str,
    rubric_markdown: str,
    reference_markdown: str | None,
) -> str:
    digest = hashlib.sha256()
    digest.update(_canonical_json(manifest).encode("utf-8"))
    digest.update(b"\n")
    digest.update(_canonical_json(answer).encode("utf-8"))
    digest.update(b"\n")
    digest.update(question_markdown.encode("utf-8"))
    digest.update(b"\n")
    digest.update(rubric_markdown.encode("utf-8"))
    digest.update(b"\n")
    digest.update((reference_markdown or "").encode("utf-8"))
    return digest.hexdigest()


def _build_trace(request_context: RequestContext | None, *, timestamp: str | None = None) -> dict[str, Any]:
    trace = {
        "adapter_version": ADAPTER_VERSION,
        "source_skill": SOURCE_SKILL,
    }
    if request_context is None:
        trace["timestamp"] = timestamp or _iso_now()
        return trace
    trace.update(
        {
            "request_id": request_context.request_id,
            "idempotency_key": request_context.idempotency_key,
            "bundle_hash": request_context.bundle_hash,
            "request_generated_at": request_context.request_generated_at,
            "request_started_at": request_context.request_started_at,
            "request_completed_at": request_context.request_completed_at,
            "timestamp": timestamp or _iso_now(),
        }
    )
    return trace


def _read_text(path: Path, description: str) -> str:
    if not path.exists():
        raise BundleValidationError(f"Missing required {description}: {path}")
    return path.read_text(encoding="utf-8")


def _load_json(path: Path, description: str) -> dict[str, Any]:
    if not path.exists():
        raise BundleValidationError(f"Missing required {description}: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BundleValidationError(f"Malformed JSON in {description}: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BundleValidationError(f"{description} must be a JSON object: {path}")
    return data


def _require_object(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise BundleValidationError(f"{name} must be a JSON object")
    return value


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise BundleValidationError(f"{name} must be a non-empty string")
    return value


def _require_number(value: Any, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise BundleValidationError(f"{name} must be a number")
    if value < 0:
        raise BundleValidationError(f"{name} must be >= 0")
    return float(value)


def _as_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise BundleValidationError(f"{name} must be a boolean")
    return value


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    raise ConfigValidationError(f"Invalid boolean value: {value!r}")


def _parse_int(value: Any, name: str, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigValidationError(f"{name} must be an integer") from exc
    if parsed < 0:
        raise ConfigValidationError(f"{name} must be >= 0")
    return parsed


def _validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    validated = {
        "manifest_version": _require_string(manifest.get("manifest_version"), "manifest.manifest_version"),
        "judge_version": _require_string(manifest.get("judge_version"), "manifest.judge_version"),
        "exam_id": _require_string(manifest.get("exam_id"), "manifest.exam_id"),
        "run_id": _require_string(manifest.get("run_id"), "manifest.run_id"),
        "question_id": _require_string(manifest.get("question_id"), "manifest.question_id"),
        "dimension": _require_string(manifest.get("dimension"), "manifest.dimension"),
        "source_answer_artifact": _require_string(
            manifest.get("source_answer_artifact"),
            "manifest.source_answer_artifact",
        ),
        "expected_output_paths": _require_object(
            manifest.get("expected_output_paths"),
            "manifest.expected_output_paths",
        ),
        "weights": _require_object(manifest.get("weights"), "manifest.weights"),
    }

    expected_output_paths = validated["expected_output_paths"]
    _require_string(
        expected_output_paths.get("judge_result_json"),
        "manifest.expected_output_paths.judge_result_json",
    )
    _require_string(
        expected_output_paths.get("judge_result_md"),
        "manifest.expected_output_paths.judge_result_md",
    )

    weights = validated["weights"]
    _require_number(weights.get("hard"), "manifest.weights.hard")
    _require_number(weights.get("soft"), "manifest.weights.soft")
    _require_number(weights.get("total"), "manifest.weights.total")

    score_cap = manifest.get("score_cap")
    if score_cap is not None:
        score_cap = _require_object(score_cap, "manifest.score_cap")
        _as_bool(score_cap.get("enabled"), "manifest.score_cap.enabled")
        if score_cap.get("hard_below") is not None:
            _require_number(score_cap.get("hard_below"), "manifest.score_cap.hard_below")
        if score_cap.get("total_cap") is not None:
            _require_number(score_cap.get("total_cap"), "manifest.score_cap.total_cap")

    attachments_contract = manifest.get("attachments_contract")
    if attachments_contract is not None:
        attachments_contract = _require_object(
            attachments_contract,
            "manifest.attachments_contract",
        )
        if attachments_contract.get("mode") is not None:
            _require_string(attachments_contract.get("mode"), "manifest.attachments_contract.mode")
        if attachments_contract.get("sandbox") is not None:
            _require_string(
                attachments_contract.get("sandbox"),
                "manifest.attachments_contract.sandbox",
            )

    return manifest


def _validate_answer(answer: dict[str, Any]) -> dict[str, Any]:
    _require_string(answer.get("exam_id"), "answer.exam_id")
    _require_string(answer.get("run_id"), "answer.run_id")
    _require_string(answer.get("question_id"), "answer.question_id")
    _require_string(answer.get("dimension"), "answer.dimension")
    if not isinstance(answer.get("answer_text"), str):
        raise BundleValidationError("answer.answer_text must be a string")
    artifacts = answer.get("artifacts")
    if not isinstance(artifacts, list):
        raise BundleValidationError("answer.artifacts must be an array")
    trace = answer.get("trace")
    if not isinstance(trace, dict):
        raise BundleValidationError("answer.trace must be an object")
    metadata = answer.get("metadata")
    if not isinstance(metadata, dict):
        raise BundleValidationError("answer.metadata must be an object")
    return answer


def _cross_validate_bundle(manifest: dict[str, Any], answer: dict[str, Any]) -> None:
    for key in ("exam_id", "run_id", "question_id"):
        if manifest[key] != answer[key]:
            raise BundleValidationError(
                f"Manifest and answer mismatch for {key}: {manifest[key]!r} != {answer[key]!r}"
            )


def _resolve_output_path(workspace_root: Path, relative_or_absolute: str) -> Path:
    output_path = Path(relative_or_absolute)
    if not output_path.is_absolute():
        output_path = workspace_root / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path


def _versioned_result_stem(run_id: str, question_id: str, judge_version: str) -> str:
    return f"{run_id}__{question_id}__{judge_version}"


def _fallback_output_paths(workspace_root: Path, manifest: dict[str, Any] | None) -> tuple[Path, Path]:
    run_id = "unknown_run"
    question_id = "unknown_question"
    judge_version = DEFAULT_JUDGE_VERSION
    if manifest:
        run_id = str(manifest.get("run_id") or run_id)
        question_id = str(manifest.get("question_id") or question_id)
        judge_version = str(manifest.get("judge_version") or judge_version)
    output_base = workspace_root / DEFAULT_RESULTS_DIR
    output_base.mkdir(parents=True, exist_ok=True)
    stem = _versioned_result_stem(run_id, question_id, judge_version)
    return output_base / f"{stem}.json", output_base / f"{stem}.md"


def _resolve_artifact_paths(workspace_root: Path, manifest: dict[str, Any] | None) -> tuple[Path, Path]:
    if manifest is None:
        return _fallback_output_paths(workspace_root, None)
    try:
        output_paths = manifest["expected_output_paths"]
        json_path = _resolve_output_path(workspace_root, output_paths["judge_result_json"])
        md_path = _resolve_output_path(workspace_root, output_paths["judge_result_md"])
        return json_path, md_path
    except Exception:
        return _fallback_output_paths(workspace_root, manifest)


def _load_provider_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}
    try:
        loaded = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigValidationError(f"Malformed provider config JSON: {config_path}: {exc}") from exc
    if not isinstance(loaded, dict):
        raise ConfigValidationError("Provider config must be a JSON object")
    return loaded


def _build_provider_settings(config_path: Path) -> ProviderSettings:
    config = _load_provider_config(config_path)

    def env_or_config(env_name: str, *config_keys: str, default: Any = None) -> Any:
        if env_name in os.environ and os.environ[env_name] != "":
            return os.environ[env_name]
        for key in config_keys:
            if key in config and config[key] not in (None, ""):
                return config[key]
        return default

    base_url = env_or_config("JUDGE_API_BASE_URL", "base_url")
    if not base_url:
        raise ConfigValidationError(
            "Missing judge API base URL. Set JUDGE_API_BASE_URL or configs/judge_provider.local.json"
        )

    path = str(env_or_config("JUDGE_API_PATH", "path", "endpoint_path", default=DEFAULT_REQUEST_PATH))
    timeout_ms = _parse_int(
        env_or_config("JUDGE_API_TIMEOUT_MS", "timeout_ms", default=DEFAULT_TIMEOUT_MS),
        "timeout_ms",
        DEFAULT_TIMEOUT_MS,
    )
    retry_count = _parse_int(
        env_or_config("JUDGE_API_RETRY_COUNT", "retry_count", default=DEFAULT_RETRY_COUNT),
        "retry_count",
        DEFAULT_RETRY_COUNT,
    )
    retry_backoff_ms = _parse_int(
        env_or_config(
            "JUDGE_API_RETRY_BACKOFF_MS",
            "retry_backoff_ms",
            default=DEFAULT_RETRY_BACKOFF_MS,
        ),
        "retry_backoff_ms",
        DEFAULT_RETRY_BACKOFF_MS,
    )
    verify_tls = _parse_bool(
        env_or_config("JUDGE_API_VERIFY_TLS", "verify_tls", default=DEFAULT_VERIFY_TLS),
        DEFAULT_VERIFY_TLS,
    )
    auth_header_name = env_or_config(
        "JUDGE_API_AUTH_HEADER",
        "auth_header_name",
        "auth_header",
        default=DEFAULT_AUTH_HEADER,
    )
    token_env_var_name = str(
        env_or_config(
            "JUDGE_API_TOKEN_ENV_VAR",
            "auth_token_env_var",
            "token_env_var_name",
            default=DEFAULT_TOKEN_ENV_VAR,
        )
    )

    auth_token = env_or_config("JUDGE_API_TOKEN", "auth_token", "api_key")
    if not auth_token and token_env_var_name:
        auth_token = os.getenv(token_env_var_name)

    return ProviderSettings(
        base_url=str(base_url),
        path=path,
        timeout_ms=timeout_ms,
        auth_header_name=str(auth_header_name) if auth_header_name else None,
        auth_token=str(auth_token) if auth_token else None,
        retry_count=retry_count,
        retry_backoff_ms=retry_backoff_ms,
        verify_tls=verify_tls,
    )


def _build_request_payload(
    manifest: dict[str, Any],
    answer: dict[str, Any],
    question_markdown: str,
    rubric_markdown: str,
    reference_markdown: str | None,
) -> tuple[dict[str, Any], RequestContext]:
    judge_version = _require_string(manifest.get("judge_version"), "manifest.judge_version")
    request_generated_at = _iso_now()
    request_id = str(uuid.uuid4())
    bundle_hash = _compute_bundle_hash(
        manifest,
        answer,
        question_markdown,
        rubric_markdown,
        reference_markdown,
    )
    idempotency_key = hashlib.sha256(
        f"{judge_version}:{manifest['run_id']}:{manifest['question_id']}:{bundle_hash}".encode("utf-8")
    ).hexdigest()
    request_context = RequestContext(
        judge_version=judge_version,
        request_id=request_id,
        idempotency_key=idempotency_key,
        run_id=manifest["run_id"],
        question_id=manifest["question_id"],
        bundle_hash=bundle_hash,
        source_skill=SOURCE_SKILL,
        adapter_version=ADAPTER_VERSION,
        request_generated_at=request_generated_at,
    )
    payload = {
        "judge_version": judge_version,
        "request_id": request_id,
        "idempotency_key": idempotency_key,
        "source_skill": SOURCE_SKILL,
        "generated_at": request_generated_at,
        "run_id": manifest["run_id"],
        "question_id": manifest["question_id"],
        "bundle_hash": bundle_hash,
        "bundle": {
            "manifest": manifest,
            "answer": answer,
            "question_markdown": question_markdown,
            "rubric_markdown": rubric_markdown,
        },
    }
    if reference_markdown is not None:
        payload["bundle"]["reference_markdown"] = reference_markdown
    return payload, request_context


def _normalize_string_list(value: Any, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ResponseValidationError(f"{field_name} must be an array of strings")
    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise ResponseValidationError(f"{field_name}[{index}] must be a string")
        normalized.append(item)
    return normalized


def _normalize_hard_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ResponseValidationError("hard_checks must be an array")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ResponseValidationError(f"hard_checks[{index}] must be an object")
        name = item.get("name")
        passed = item.get("passed")
        score = item.get("score")
        note = item.get("note")
        if not isinstance(name, str) or not name.strip():
            raise ResponseValidationError(f"hard_checks[{index}].name must be a non-empty string")
        if not isinstance(passed, bool):
            raise ResponseValidationError(f"hard_checks[{index}].passed must be a boolean")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ResponseValidationError(f"hard_checks[{index}].score must be a number")
        if not isinstance(note, str):
            raise ResponseValidationError(f"hard_checks[{index}].note must be a string")
        normalized_item = {
            "name": name,
            "passed": passed,
            "score": float(score),
            "note": note,
        }
        max_score = item.get("max_score")
        if max_score is not None:
            if not isinstance(max_score, (int, float)) or isinstance(max_score, bool):
                raise ResponseValidationError(f"hard_checks[{index}].max_score must be a number")
            normalized_item["max_score"] = float(max_score)
        normalized.append(normalized_item)
    return normalized


def _normalize_soft_checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ResponseValidationError("soft_checks must be an array")
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ResponseValidationError(f"soft_checks[{index}] must be an object")
        name = item.get("name")
        score = item.get("score")
        max_score = item.get("max_score")
        note = item.get("note")
        if not isinstance(name, str) or not name.strip():
            raise ResponseValidationError(f"soft_checks[{index}].name must be a non-empty string")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ResponseValidationError(f"soft_checks[{index}].score must be a number")
        if not isinstance(max_score, (int, float)) or isinstance(max_score, bool):
            raise ResponseValidationError(f"soft_checks[{index}].max_score must be a number")
        if not isinstance(note, str):
            raise ResponseValidationError(f"soft_checks[{index}].note must be a string")
        normalized.append(
            {
                "name": name,
                "score": float(score),
                "max_score": float(max_score),
                "note": note,
            }
        )
    return normalized


def _validate_success_result_shape(result: dict[str, Any]) -> None:
    required_strings = [
        "exam_id",
        "run_id",
        "question_id",
        "judge_version",
        "judge_summary",
        "status",
    ]
    for key in required_strings:
        if not isinstance(result.get(key), str) or not str(result[key]).strip():
            raise ResponseValidationError(f"Result field {key} must be a non-empty string")
    for key in ("hard_score", "soft_score", "total_score"):
        if not isinstance(result.get(key), (int, float)) or isinstance(result.get(key), bool):
            raise ResponseValidationError(f"Result field {key} must be a number")
    if not isinstance(result.get("hard_checks"), list):
        raise ResponseValidationError("Result field hard_checks must be an array")
    if not isinstance(result.get("soft_checks"), list):
        raise ResponseValidationError("Result field soft_checks must be an array")
    if not isinstance(result.get("failure_tags"), list):
        raise ResponseValidationError("Result field failure_tags must be an array")
    if result.get("status") not in {"success", "error"}:
        raise ResponseValidationError("Result field status must be 'success' or 'error'")
    if not isinstance(result.get("trace"), dict):
        raise ResponseValidationError("Result field trace must be an object")
    if result.get("status") == "error":
        error_info = result.get("error")
        if not isinstance(error_info, dict):
            raise ResponseValidationError("Error result must include an error object")
        required_error_fields = {
            "code": str,
            "message": str,
            "stage": str,
            "retryable": bool,
        }
        for key, expected_type in required_error_fields.items():
            if not isinstance(error_info.get(key), expected_type):
                raise ResponseValidationError(f"Error field {key} must be {expected_type.__name__}")


def _normalize_response(
    response_data: dict[str, Any],
    manifest: dict[str, Any],
    request_context: RequestContext,
) -> dict[str, Any]:
    if not isinstance(response_data, dict):
        raise ResponseValidationError("Judge API response must be a JSON object")

    question_id = response_data.get("question_id")
    if not isinstance(question_id, str) or not question_id.strip():
        raise ResponseValidationError("Response field question_id is required")
    if question_id != manifest["question_id"]:
        raise ResponseValidationError(
            f"Response question_id mismatch: {question_id!r} != {manifest['question_id']!r}"
        )

    judge_version = response_data.get("judge_version")
    if not isinstance(judge_version, str) or not judge_version.strip():
        raise ResponseValidationError("Response field judge_version is required")
    if judge_version != request_context.judge_version:
        raise ResponseValidationError(
            f"Response judge_version mismatch: {judge_version!r} != {request_context.judge_version!r}"
        )

    run_id = response_data.get("run_id")
    if run_id is not None and run_id != request_context.run_id:
        raise ResponseValidationError(f"Response run_id mismatch: {run_id!r} != {request_context.run_id!r}")

    hard_score = response_data.get("hard_score")
    soft_score = response_data.get("soft_score")
    total_score = response_data.get("total_score")
    for key, value in {
        "hard_score": hard_score,
        "soft_score": soft_score,
        "total_score": total_score,
    }.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ResponseValidationError(f"Response field {key} must be a number")

    hard_checks = _normalize_hard_checks(response_data.get("hard_checks"))
    soft_checks = _normalize_soft_checks(response_data.get("soft_checks"))
    failure_tags = _normalize_string_list(response_data.get("failure_tags"), "failure_tags")
    judge_summary = response_data.get("judge_summary")
    if not isinstance(judge_summary, str) or not judge_summary.strip():
        raise ResponseValidationError("Response field judge_summary is required")

    normalized = {
        "status": "success",
        "exam_id": manifest["exam_id"],
        "run_id": manifest["run_id"],
        "question_id": manifest["question_id"],
        "judge_version": judge_version,
        "hard_score": float(hard_score),
        "soft_score": float(soft_score),
        "total_score": float(total_score),
        "hard_checks": hard_checks,
        "soft_checks": soft_checks,
        "failure_tags": failure_tags,
        "judge_summary": judge_summary,
        "trace": _build_trace(request_context),
        "metadata": {
            "adapter": SOURCE_SKILL,
            "source": "external_http_api",
            "received_at": _iso_now(),
        },
    }

    if "cap_applied" in response_data:
        if not isinstance(response_data["cap_applied"], bool):
            raise ResponseValidationError("Response field cap_applied must be a boolean")
        normalized["cap_applied"] = response_data["cap_applied"]
    if "report_markdown" in response_data:
        if not isinstance(response_data["report_markdown"], str):
            raise ResponseValidationError("Response field report_markdown must be a string")
        normalized["report_markdown"] = response_data["report_markdown"]

    metadata = response_data.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            raise ResponseValidationError("Response field metadata must be an object")
        normalized["metadata"]["response_metadata"] = metadata

    _validate_success_result_shape(normalized)
    return normalized


def _build_markdown_report(result: dict[str, Any]) -> str:
    provided = result.get("report_markdown")
    if isinstance(provided, str) and provided.strip():
        return provided

    failure_tags = result.get("failure_tags") or []
    failure_line = ", ".join(failure_tags) if failure_tags else "None"
    lines = [
        "# Judge Report",
        "",
        f"- Status: {result.get('status', 'unknown')}",
        f"- Question ID: {result.get('question_id', 'unknown')}",
        f"- Judge Version: {result.get('judge_version', DEFAULT_JUDGE_VERSION)}",
        f"- Hard Score: {result.get('hard_score', 0)}",
        f"- Soft Score: {result.get('soft_score', 0)}",
        f"- Total Score: {result.get('total_score', 0)}",
        f"- Failure Tags: {failure_line}",
        "",
        "## Summary",
        "",
        str(result.get("judge_summary", "No summary provided.")),
    ]

    if result.get("status") == "error":
        error_info = result.get("error") or {}
        lines.extend(
            [
                "",
                "## Error",
                "",
                f"- Code: {error_info.get('code', 'unknown_error')}",
                f"- Stage: {error_info.get('stage', 'unknown_stage')}",
                f"- Retryable: {error_info.get('retryable', False)}",
                f"- Message: {error_info.get('message', 'Unknown error')}",
            ]
        )
        details = error_info.get("details")
        if details:
            lines.extend(["", "```json", json.dumps(details, indent=2, sort_keys=True), "```"])
        return "\n".join(lines) + "\n"

    if result.get("hard_checks"):
        lines.extend(["", "## Hard Checks", ""])
        for check in result["hard_checks"]:
            lines.append(
                f"- {check['name']}: passed={check['passed']}, score={check['score']}, note={check['note']}"
            )

    if result.get("soft_checks"):
        lines.extend(["", "## Soft Checks", ""])
        for check in result["soft_checks"]:
            lines.append(
                f"- {check['name']}: score={check['score']}/{check['max_score']}, note={check['note']}"
            )

    return "\n".join(lines) + "\n"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _error_result(
    message: str,
    manifest: dict[str, Any] | None,
    *,
    error_code: str,
    stage: str,
    retryable: bool,
    request_context: RequestContext | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = manifest or {}
    result = {
        "status": "error",
        "exam_id": str(manifest.get("exam_id") or "unknown_exam"),
        "run_id": str(manifest.get("run_id") or "unknown_run"),
        "question_id": str(manifest.get("question_id") or "unknown_question"),
        "judge_version": str(manifest.get("judge_version") or DEFAULT_JUDGE_VERSION),
        "hard_score": 0.0,
        "soft_score": 0.0,
        "total_score": 0.0,
        "hard_checks": [],
        "soft_checks": [],
        "failure_tags": ["adapter_error", error_code],
        "judge_summary": message,
        "trace": _build_trace(request_context),
        "error": {
            "code": error_code,
            "stage": stage,
            "retryable": retryable,
            "message": message,
        },
        "metadata": {
            "adapter": SOURCE_SKILL,
            "source": "external_http_api",
            "received_at": _iso_now(),
        },
    }
    if details:
        result["error"]["details"] = details
    _validate_success_result_shape(result)
    return result


def _write_error_artifacts(
    workspace_root: Path,
    manifest: dict[str, Any] | None,
    message: str,
    *,
    error_code: str,
    stage: str,
    retryable: bool,
    request_context: RequestContext | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Path]:
    result = _error_result(
        message,
        manifest,
        error_code=error_code,
        stage=stage,
        retryable=retryable,
        request_context=request_context,
        details=details,
    )
    json_path, md_path = _resolve_artifact_paths(workspace_root, manifest)
    _write_json(json_path, result)
    _write_text(md_path, _build_markdown_report(result))
    return {"json": json_path, "markdown": md_path}


def _http_post_json(
    settings: ProviderSettings,
    payload: dict[str, Any],
    request_context: RequestContext,
) -> dict[str, Any]:
    request_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": request_context.idempotency_key,
        "X-Request-Id": request_context.request_id,
    }
    if settings.auth_header_name and settings.auth_token:
        headers[settings.auth_header_name] = settings.auth_token

    context = None
    if not settings.verify_tls:
        context = ssl._create_unverified_context()

    last_error: Exception | None = None
    for attempt in range(settings.retry_count + 1):
        request_context.request_started_at = _iso_now()
        request = urllib.request.Request(
            settings.request_url,
            data=request_data,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=settings.timeout_ms / 1000.0,
                context=context,
            ) as response:
                raw_body = response.read().decode("utf-8")
            request_context.request_completed_at = _iso_now()
            try:
                parsed = json.loads(raw_body)
            except json.JSONDecodeError as exc:
                raise ResponseValidationError(f"Malformed JSON response from judge API: {exc}") from exc
            if not isinstance(parsed, dict):
                raise ResponseValidationError("Judge API response must be a JSON object")
            return parsed
        except urllib.error.HTTPError as exc:
            request_context.request_completed_at = _iso_now()
            response_body = ""
            try:
                response_body = exc.read().decode("utf-8")
            except Exception:
                response_body = ""
            if 500 <= exc.code < 600 and attempt < settings.retry_count:
                time.sleep(settings.retry_backoff_ms / 1000.0)
                last_error = exc
                continue
            raise HttpRequestError(
                f"Judge API returned HTTP {exc.code}: {response_body or exc.reason}",
                details={"http_status": exc.code, "response_body": response_body or None},
                stage="http_response",
                retryable=500 <= exc.code < 600,
            ) from exc
        except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
            request_context.request_completed_at = _iso_now()
            last_error = exc
            if attempt < settings.retry_count:
                time.sleep(settings.retry_backoff_ms / 1000.0)
                continue
            raise HttpRequestError(
                f"Judge API request failed: {exc}",
                details={"reason": str(exc)},
                stage="http_request",
                retryable=True,
            ) from exc

    raise HttpRequestError(
        f"Judge API request failed: {last_error}",
        details={"reason": str(last_error) if last_error else None},
        stage="http_request",
        retryable=True,
    )


def _build_legacy_manifest(
    exam_package_path: Path,
    run_id: str,
    question_id: str,
    answer: dict[str, Any],
) -> dict[str, Any]:
    exam_config_path = exam_package_path / "configs/exam_v1.json"
    exam_config = _load_json(exam_config_path, "legacy exam config")
    questions = exam_config.get("questions")
    if not isinstance(questions, dict) or question_id not in questions:
        raise BundleValidationError(
            f"Legacy exam config missing questions entry for {question_id}: {exam_config_path}"
        )
    question_config = questions[question_id]
    if not isinstance(question_config, dict):
        raise BundleValidationError(f"Legacy question config for {question_id} must be an object")
    weights = question_config.get("weights")
    if not isinstance(weights, dict):
        raise BundleValidationError(f"Legacy question config missing weights for {question_id}")

    score_caps = exam_config.get("score_caps", {})
    score_cap_entry = score_caps.get(question_id)
    if score_cap_entry is None:
        score_cap = {"enabled": False}
    else:
        if not isinstance(score_cap_entry, dict):
            raise BundleValidationError(f"Legacy score cap for {question_id} must be an object")
        score_cap = {
            "enabled": True,
            "hard_below": score_cap_entry.get("hard_below"),
            "total_cap": score_cap_entry.get("total_cap"),
        }

    return {
        "manifest_version": "v1",
        "judge_version": DEFAULT_JUDGE_VERSION,
        "exam_id": _require_string(answer.get("exam_id"), "answer.exam_id"),
        "run_id": run_id,
        "question_id": question_id,
        "dimension": _require_string(
            answer.get("dimension") or question_config.get("dimension"),
            "legacy.dimension",
        ),
        "source_answer_artifact": f"artifacts/exam_answers/{run_id}__{question_id}.json",
        "bundle_root": "legacy_exam_package",
        "weights": weights,
        "score_cap": score_cap,
        "expected_output_paths": {
            "judge_result_json": (
                f"{DEFAULT_RESULTS_DIR}/{_versioned_result_stem(run_id, question_id, DEFAULT_JUDGE_VERSION)}.json"
            ),
            "judge_result_md": (
                f"{DEFAULT_RESULTS_DIR}/{_versioned_result_stem(run_id, question_id, DEFAULT_JUDGE_VERSION)}.md"
            ),
        },
        "metadata": {
            "legacy_input_mode": True,
            "exam_package_path": str(exam_package_path),
        },
    }


def _load_primary_bundle(bundle_root: Path) -> tuple[dict[str, Any], dict[str, Any], str, str, str | None]:
    manifest = _validate_manifest(_load_json(bundle_root / "manifest.json", "bundle manifest"))
    answer = _validate_answer(_load_json(bundle_root / "answer.json", "bundle answer"))
    question_markdown = _read_text(bundle_root / "question.md", "question markdown")
    rubric_markdown = _read_text(bundle_root / "rubric.md", "rubric markdown")
    reference_path = bundle_root / "reference.md"
    reference_markdown = reference_path.read_text(encoding="utf-8") if reference_path.exists() else None
    _cross_validate_bundle(manifest, answer)
    return manifest, answer, question_markdown, rubric_markdown, reference_markdown


def _load_legacy_bundle(
    exam_package_path: Path,
    run_id: str,
    question_id: str,
) -> tuple[dict[str, Any], dict[str, Any], str, str, str | None]:
    answer = _validate_answer(
        _load_json(
            exam_package_path / "artifacts/exam_answers" / f"{run_id}__{question_id}.json",
            "legacy answer artifact",
        )
    )
    question_root = exam_package_path / "questions" / question_id
    question_markdown = _read_text(question_root / "question.md", "legacy question markdown")
    rubric_markdown = _read_text(question_root / "rubric.md", "legacy rubric markdown")
    reference_path = question_root / "reference.md"
    reference_markdown = reference_path.read_text(encoding="utf-8") if reference_path.exists() else None
    manifest = _validate_manifest(_build_legacy_manifest(exam_package_path, run_id, question_id, answer))
    _cross_validate_bundle(manifest, answer)
    return manifest, answer, question_markdown, rubric_markdown, reference_markdown


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read a custom-judge bundle, call the external judge API, and write local artifacts."
    )
    parser.add_argument(
        "--workspace-root",
        default=".",
        help="Judge workspace root. Relative output paths are resolved from here.",
    )
    parser.add_argument(
        "--bundle-root",
        default=DEFAULT_BUNDLE_DIR,
        help="Bundle root containing manifest.json, answer.json, question.md, rubric.md, and optional reference.md.",
    )
    parser.add_argument(
        "--config-path",
        default=DEFAULT_CONFIG_PATH,
        help="Judge-local provider config path. Relative to workspace root unless absolute.",
    )
    parser.add_argument(
        "--exam-package-path",
        help="Legacy-compatible fallback path to a custom-exam package when judge_input/ is unavailable.",
    )
    parser.add_argument("--run-id", help="Required with --exam-package-path.")
    parser.add_argument("--question-id", help="Required with --exam-package-path.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    bundle_root = Path(args.bundle_root)
    if not bundle_root.is_absolute():
        bundle_root = workspace_root / bundle_root
    config_path = Path(args.config_path)
    if not config_path.is_absolute():
        config_path = workspace_root / config_path

    manifest: dict[str, Any] | None = None
    request_context: RequestContext | None = None
    try:
        if bundle_root.exists():
            manifest, answer, question_markdown, rubric_markdown, reference_markdown = _load_primary_bundle(
                bundle_root
            )
        elif args.exam_package_path:
            if not args.run_id or not args.question_id:
                raise BundleValidationError("--run-id and --question-id are required with --exam-package-path")
            manifest, answer, question_markdown, rubric_markdown, reference_markdown = _load_legacy_bundle(
                Path(args.exam_package_path).resolve(),
                args.run_id,
                args.question_id,
            )
        else:
            raise BundleValidationError(
                f"Bundle root not found: {bundle_root}. Provide judge_input/ or use --exam-package-path."
            )

        settings = _build_provider_settings(config_path)
        payload, request_context = _build_request_payload(
            manifest,
            answer,
            question_markdown,
            rubric_markdown,
            reference_markdown,
        )
        response_data = _http_post_json(settings, payload, request_context)
        result = _normalize_response(response_data, manifest, request_context)
        json_path, md_path = _resolve_artifact_paths(workspace_root, manifest)
        _write_json(json_path, result)
        _write_text(md_path, _build_markdown_report(result))
        print(
            json.dumps(
                {
                    "status": "success",
                    "result_json": str(json_path),
                    "result_markdown": str(md_path),
                }
            )
        )
        return 0
    except JudgeAdapterError as exc:
        written = _write_error_artifacts(
            workspace_root,
            manifest,
            str(exc),
            error_code=exc.code,
            stage=exc.stage,
            retryable=exc.retryable,
            request_context=request_context,
            details=exc.details,
        )
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_code": exc.code,
                    "stage": exc.stage,
                    "retryable": exc.retryable,
                    "message": str(exc),
                    "result_json": str(written["json"]),
                    "result_markdown": str(written["markdown"]),
                }
            ),
            file=sys.stderr,
        )
        return 1
    except Exception as exc:  # pragma: no cover - defensive final guard
        written = _write_error_artifacts(
            workspace_root,
            manifest,
            f"Unexpected adapter failure: {exc}",
            error_code="unexpected_error",
            stage="unexpected_error",
            retryable=False,
            request_context=request_context,
            details={"exception_type": type(exc).__name__},
        )
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_code": "unexpected_error",
                    "stage": "unexpected_error",
                    "retryable": False,
                    "message": str(exc),
                    "result_json": str(written["json"]),
                    "result_markdown": str(written["markdown"]),
                }
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
