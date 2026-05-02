from __future__ import annotations

import hashlib
import json
import os
import re
from urllib.request import urlopen
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Protocol, Sequence

from app.services.hazard_scoring import ensure_utc_datetime, hazard_score


def _backend_root() -> Path:
    """Directory that contains ``app/`` and ``data/`` (repo ``backend/``, image ``WORKDIR``)."""
    return Path(__file__).resolve().parents[2]


def _default_hazard_export_path() -> Path:
    return _backend_root() / "data" / "external_hazards.json"


def _default_review_export_path() -> Path:
    return _backend_root() / "data" / "external_reviews.json"


# Keyword matching uses word-ish boundaries so substrings like "icy" inside "bicycles" do not trip hazards.
HAZARD_PATTERN_TYPES: tuple[tuple[str, str], ...] = (
    (r"\bsnow\b|\bsnowy\b", "snow"),
    (r"\bmuddy\b|\bmud\b", "muddy_sections"),
    (r"\bwashouts?\b", "washout"),
    (r"\bbear\b", "wildlife"),
    (r"\btree\b|\btrees\b", "downed_tree"),
    (r"\bicy\b|\bicing\b|\bice\b", "ice"),
)


class SourceAdapter(Protocol):
    name: str

    def fetch(self) -> List[Dict]:
        ...


class HazardStore(Protocol):
    def search_trails(self, query: str, limit: int = 10, **kwargs: Any) -> List[Dict]:
        ...

    def get_hazards_for_dedupe(self, trail_ids: Sequence[int], since: datetime) -> List[Dict]:
        ...

    def persist_hazards(self, hazards: Sequence[Dict]) -> int:
        ...

    def has_fetch_log(
        self, source_name: str, fetch_scope: str, period_start, period_end, content_hash: str
    ) -> bool:
        ...

    def record_fetch_log(
        self, source_name: str, fetch_scope: str, period_start, period_end, content_hash: str
    ) -> None:
        ...

    def persist_reviews(self, reviews: Sequence[Dict]) -> int:
        ...


class StaticHazardSourceAdapter:
    """Deterministic adapter reserved for tests; not used in real-data runtime."""

    name = "seeded_scraped_feed"

    def __init__(self, seeded_payloads: Sequence[Dict] | None = None) -> None:
        self._seeded_payloads = list(seeded_payloads or [])

    def fetch(self) -> List[Dict]:
        if self._seeded_payloads:
            return list(self._seeded_payloads)
        return []


class ExportedHazardSourceAdapter:
    """Load latest scraped hazard events from a local export file."""

    name = "external_hazard_export"

    def __init__(self, path: str | None = None) -> None:
        explicit = path or os.getenv("HAZARD_EXPORT_PATH")
        self.path = Path(explicit) if explicit else _default_hazard_export_path()

    def fetch(self) -> List[Dict]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return []
        rows: List[Dict] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            reported_at = row.get("reported_at")
            if isinstance(reported_at, str):
                try:
                    row["reported_at"] = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
                except ValueError:
                    row["reported_at"] = datetime.now(tz=timezone.utc)
            rows.append(row)
        return rows


class ExportedTripReportSourceAdapter:
    """Load externally scraped trip reports from a local export file."""

    name = "external_trip_report_export"

    def __init__(self, path: str | None = None) -> None:
        explicit = path or os.getenv("REVIEW_EXPORT_PATH")
        self.path = Path(explicit) if explicit else _default_review_export_path()

    def fetch(self) -> List[Dict]:
        if not self.path.exists():
            return []
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return []
        rows: List[Dict] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            seen_at = row.get("scraped_at") or row.get("published_at")
            if isinstance(seen_at, str):
                try:
                    row["reported_at"] = datetime.fromisoformat(seen_at.replace("Z", "+00:00"))
                except ValueError:
                    row["reported_at"] = datetime.now(tz=timezone.utc)
            row["text"] = row.get("text") or row.get("summary") or row.get("body") or ""
            rows.append(row)
        return rows


class RemoteJsonSourceAdapter:
    """Fetch normalized source records from a remote JSON endpoint."""

    def __init__(self, name: str, url: str) -> None:
        self.name = name
        self.url = url

    def fetch(self) -> List[Dict]:
        with urlopen(self.url, timeout=12) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            return []
        rows: List[Dict] = []
        for row in payload:
            if not isinstance(row, dict):
                continue
            reported_at = row.get("reported_at") or row.get("published_at")
            if isinstance(reported_at, str):
                try:
                    row["reported_at"] = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
                except ValueError:
                    row["reported_at"] = datetime.now(tz=timezone.utc)
            row["text"] = row.get("text") or row.get("summary") or row.get("body") or ""
            rows.append(row)
        return rows


def build_source_adapters() -> List[SourceAdapter]:
    adapters: List[SourceAdapter] = [ExportedHazardSourceAdapter(), ExportedTripReportSourceAdapter()]
    raw_urls = os.getenv("LIVE_RECENT_INFO_URLS", "")
    for index, url in enumerate([part.strip() for part in raw_urls.split(",") if part.strip()]):
        adapters.append(RemoteJsonSourceAdapter(name=f"remote_recent_info_{index + 1}", url=url))
    return adapters


def build_review_source_adapters() -> List[SourceAdapter]:
    return []


def resolve_trail_id(store: HazardStore, raw: Dict) -> int:
    if raw.get("trail_id"):
        return int(raw["trail_id"])
    trail_name = (raw.get("trail_name") or raw.get("trail") or "").strip()
    if not trail_name:
        raise KeyError("trail_id")
    candidates = store.search_trails(query=trail_name, limit=5)
    if not candidates:
        raise KeyError("trail_id")
    exact = next((trail for trail in candidates if trail["name"].strip().lower() == trail_name.lower()), candidates[0])
    return int(exact["id"])


def normalize_payload(store: HazardStore, raw: Dict) -> Dict:
    reported_at = raw.get("reported_at") or raw.get("published_at")
    if isinstance(reported_at, str):
        reported_at = datetime.fromisoformat(reported_at.replace("Z", "+00:00"))
    if not isinstance(reported_at, datetime):
        reported_at = datetime.now(tz=timezone.utc)
    else:
        reported_at = ensure_utc_datetime(reported_at)
    return {
        "trail_id": resolve_trail_id(store=store, raw=raw),
        "source": raw.get("source", "scraped"),
        "source_platform": raw.get("source_platform") or raw.get("platform"),
        "source_url": raw.get("source_url") or raw.get("url"),
        "adapter": raw.get("adapter"),
        "raw_text": raw.get("text", ""),
        "reported_at": reported_at,
        "confidence": raw.get("confidence", 0.75),
    }


def fetch_source_payloads(adapters: Sequence[SourceAdapter] | None = None) -> Dict[str, List[Dict]]:
    source_adapters = list(adapters or build_source_adapters())
    payloads: Dict[str, List[Dict]] = {}
    for adapter in source_adapters:
        try:
            adapter_payloads = adapter.fetch()
        except Exception:
            adapter_payloads = []
        payloads[adapter.name] = [{**payload, "adapter": adapter.name} for payload in adapter_payloads]
    return payloads


def fetch_review_payloads(adapters: Sequence[SourceAdapter] | None = None) -> List[Dict]:
    source_adapters = list(adapters or build_review_source_adapters())
    payloads: List[Dict] = []
    for adapter in source_adapters:
        adapter_payloads = adapter.fetch()
        for payload in adapter_payloads:
            payloads.append({**payload, "adapter": adapter.name})
    return payloads


def extract_hazards(normalized: Dict) -> List[Dict]:
    text = normalized["raw_text"].lower()
    hazards: List[Dict] = []
    seen_types: set[str] = set()
    for pattern, hazard_type in HAZARD_PATTERN_TYPES:
        if hazard_type in seen_types:
            continue
        if not re.search(pattern, text):
            continue
        seen_types.add(hazard_type)
        hazards.append(
            {
                "trail_id": normalized["trail_id"],
                "type": hazard_type,
                "severity": "medium" if hazard_type in {"snow", "washout"} else "low",
                "source": normalized["source"],
                "confidence": normalized["confidence"],
                "reported_at": normalized["reported_at"],
                "raw_text": normalized["raw_text"],
                "adapter": normalized.get("adapter"),
                "source_platform": normalized.get("source_platform"),
                "source_url": normalized.get("source_url"),
            }
        )
    return hazards


def score_hazards(hazards: List[Dict]) -> List[Dict]:
    return [{**hazard, "score": hazard_score(hazard)} for hazard in hazards]


def hazard_fingerprint(hazard: Dict) -> str:
    ra = hazard["reported_at"]
    if isinstance(ra, datetime):
        ra = ensure_utc_datetime(ra)
        reported_day = ra.date().isoformat()
    else:
        reported_day = datetime.now(tz=timezone.utc).date().isoformat()
    normalized_text = " ".join(hazard.get("raw_text", "").strip().lower().split())
    materialized = f'{hazard["trail_id"]}|{hazard["type"]}|{reported_day}|{normalized_text}'
    return hashlib.sha256(materialized.encode("utf-8")).hexdigest()


def review_fingerprint(review: Dict) -> str:
    if review.get("external_review_id"):
        materialized = f'{review.get("source_platform", "unknown")}|{review["external_review_id"]}'
    else:
        normalized_text = " ".join((review.get("text") or "").strip().lower().split())
        day = review.get("scraped_at", datetime.now(tz=timezone.utc)).astimezone(timezone.utc).date().isoformat()
        materialized = f'{review.get("trail_id")}|{review.get("source_platform", "unknown")}|{day}|{normalized_text}'
    return hashlib.sha256(materialized.encode("utf-8")).hexdigest()


def dedupe_hazards(candidates: Sequence[Dict], existing: Sequence[Dict]) -> List[Dict]:
    existing_keys = {hazard_fingerprint(hazard) for hazard in existing}
    accepted: List[Dict] = []
    accepted_keys: set[str] = set()
    for hazard in candidates:
        key = hazard_fingerprint(hazard)
        if key in existing_keys or key in accepted_keys:
            continue
        accepted_keys.add(key)
        accepted.append({**hazard, "dedupe_key": key})
    return accepted


def persist_scored_hazards(store: HazardStore, hazards: Sequence[Dict]) -> int:
    return store.persist_hazards(hazards)


def persist_reviews(store: HazardStore, reviews: Sequence[Dict]) -> int:
    return store.persist_reviews(reviews)


def run_ingestion_pipeline(store: HazardStore, adapters: Sequence[SourceAdapter] | None = None) -> Dict:
    started_at = datetime.now(tz=timezone.utc)
    errors = 0
    raw_payloads_by_adapter = fetch_source_payloads(adapters=adapters)
    raw_payloads = [payload for payloads in raw_payloads_by_adapter.values() for payload in payloads]
    normalized: List[Dict] = []
    for payload in raw_payloads:
        try:
            normalized.append(normalize_payload(store=store, raw=payload))
        except Exception:
            errors += 1
    extracted = [hazard for payload in normalized for hazard in extract_hazards(payload)]
    scored = score_hazards(extracted)
    trail_ids = sorted({hazard["trail_id"] for hazard in scored})
    dedupe_horizon = started_at - timedelta(days=14)
    existing = store.get_hazards_for_dedupe(trail_ids=trail_ids, since=dedupe_horizon) if trail_ids else []
    deduped: List[Dict] = []
    for hazard in dedupe_hazards(scored, existing):
        period_day = hazard["reported_at"].astimezone(timezone.utc).date()
        fingerprint = hazard["dedupe_key"]
        if store.has_fetch_log(
            source_name=hazard.get("adapter", "unknown"),
            fetch_scope=f"hazard:{hazard['trail_id']}",
            period_start=period_day,
            period_end=period_day,
            content_hash=fingerprint,
        ):
            continue
        store.record_fetch_log(
            source_name=hazard.get("adapter", "unknown"),
            fetch_scope=f"hazard:{hazard['trail_id']}",
            period_start=period_day,
            period_end=period_day,
            content_hash=fingerprint,
        )
        deduped.append(hazard)
    persisted = persist_scored_hazards(store=store, hazards=deduped)

    by_adapter_metrics = {
        name: {"raw_count": len(payloads), "parsed_count": 0}
        for name, payloads in raw_payloads_by_adapter.items()
    }
    for row in normalized:
        adapter_name = row.get("adapter", "unknown")
        if adapter_name not in by_adapter_metrics:
            by_adapter_metrics[adapter_name] = {"raw_count": 0, "parsed_count": 0}
        by_adapter_metrics[adapter_name]["parsed_count"] += 1
    return {
        "raw_count": len(raw_payloads),
        "normalized_count": len(normalized),
        "parsed_count": len(normalized),
        "hazard_count": len(extracted),
        "scored_count": len(scored),
        "deduped_count": len(deduped),
        "persisted_count": persisted,
        "review_raw_count": 0,
        "review_deduped_count": 0,
        "review_persisted_count": 0,
        "error_count": errors,
        "trail_ids": trail_ids,
        "source_metrics": by_adapter_metrics,
    }
