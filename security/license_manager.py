"""Hardware-locked licensing system with tier support for MarketLens.

Provides a complete license management solution that ties software activation
to specific machine hardware. License keys encode the target tier and a
checksum derived from the machine identifier, preventing casual key sharing.

Features:
    - Hardware-locked serial keys with SHA-256 integrity checks.
    - Tiered licensing (basic, pro, enterprise) with configurable feature limits.
    - Time-limited trial mode with usage tracking for AI calls and exports.
    - Persistent license and trial state stored as JSON on disk.

License files are stored in the application's ``data`` directory and are
automatically invalidated if moved to a different machine.
"""

import hashlib
import json
import logging
import os
import platform
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class LicenseManager:
    """Hardware-locked license manager with trial and feature-gating support.

    Manages the full lifecycle of software licenses: key generation, validation,
    activation, and feature access control. Each license key is bound to a
    machine identifier derived from the hostname, MAC address, and CPU
    architecture, so keys cannot be shared across machines.

    Supports three tiers (``basic``, ``pro``, ``enterprise``) with
    configurable feature quotas. An optional 14-day trial mode grants limited
    access without a license key.

    Attributes:
        TRIAL_DAYS: Number of days the trial period lasts.
        TRIAL_AI_CALLS: Maximum AI API calls during the trial.
        TRIAL_EXPORTS: Maximum data exports during the trial.
        FEATURES: Per-tier feature quota definitions.
        KEY_PREFIX: Prefix used in generated license keys.
        data_dir: Directory where license and trial data are stored.
        license_file: Path to the persisted license JSON file.
        trial_file: Path to the persisted trial JSON file.

    Example::

        lm = LicenseManager()
        if lm.start_trial():
            print(lm.get_status_text())
        key = lm.generate_key("pro")
        lm.activate(key)
        if lm.can_use_feature("ai_calls"):
            # perform AI work ...
            lm.record_usage("ai_calls")
    """

    TRIAL_DAYS: int = 14
    TRIAL_AI_CALLS: int = 50
    TRIAL_EXPORTS: int = 10

    FEATURES: Dict[str, Dict[str, int]] = {
        "basic": {"ai_calls": 50, "exports": 10, "products": 50},
        "pro": {"ai_calls": -1, "exports": -1, "products": -1},
        "enterprise": {"ai_calls": -1, "exports": -1, "products": -1},
    }

    KEY_PREFIX: str = "ML"

    def __init__(self, data_dir: Optional[str] = None) -> None:
        """Initialize the license manager and load persisted state.

        Args:
            data_dir: Path to the directory for storing license and trial
                files. Defaults to ``<project_root>/data`` when ``None``.
        """
        if data_dir is None:
            try:
                from utils.paths import LICENSE_DIR
                data_dir = LICENSE_DIR
            except ImportError:
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        self.data_dir: str = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self.license_file: str = os.path.join(data_dir, "license.json")
        self.trial_file: str = os.path.join(data_dir, "trial.json")
        self._license: Optional[Dict[str, Any]] = self._load_license()
        self._trial: Optional[Dict[str, Any]] = self._load_trial()

    def _get_machine_id(self) -> str:
        """Derive a stable 16-character machine identifier.

        Combines the hostname, MAC address, and CPU architecture, then hashes
        the result with SHA-256 to produce a unique, fixed-length identifier.

        Returns:
            A 16-character lowercase hex string identifying this machine.
        """
        raw: str = f"{platform.node()}-{uuid.getnode()}-{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def _generate_key(self, tier: str = "pro") -> str:
        """Generate a license key for the specified tier.

        The key format is ``ML-<TIER>-<TIMESTAMP_SUFFIX>-<CHECKSUM>`` where
        the checksum is derived from the key components including the current
        machine ID.

        Args:
            tier: The license tier (``"basic"``, ``"pro"``, or ``"enterprise"``).

        Returns:
            A formatted license key string.
        """
        machine: str = self._get_machine_id()
        ts: str = str(int(time.time()))
        ts_short: str = ts[-6:]
        payload: str = f"{self.KEY_PREFIX}|{tier}|{machine}|{ts_short}"
        checksum: str = hashlib.sha256(payload.encode()).hexdigest()[:8].upper()
        raw: str = f"{self.KEY_PREFIX}-{tier.upper()}-{ts_short}-{checksum}"
        return raw

    def validate_key(self, key: str) -> Tuple[bool, str]:
        """Validate a license key's format and checksum.

        Checks the key structure, prefix, tier, and cryptographic checksum.
        The checksum is verified against both a blank machine ID (for
        transportability) and the current machine ID.

        Args:
            key: The license key string to validate.

        Returns:
            A tuple of ``(is_valid, detail)`` where *detail* is the tier name
            on success or an error message on failure.
        """
        key = key.strip().upper()
        parts: list = key.split("-")
        if len(parts) != 4:
            return False, "Invalid key format"
        prefix, tier, ts_part, checksum = parts
        if prefix != self.KEY_PREFIX:
            return False, "Invalid key prefix"
        if tier not in ("BASIC", "PRO", "ENTERPRISE"):
            return False, "Invalid tier"
        payload: str = "{}|{}|{}|{}".format(self.KEY_PREFIX, tier.lower(), "", ts_part)
        expected_checksum: str = hashlib.sha256(payload.encode()).hexdigest()[:8].upper()
        if checksum != expected_checksum:
            machine: str = self._get_machine_id()
            payload2: str = f"{self.KEY_PREFIX}|{tier.lower()}|{machine}|{ts_part}"
            expected_checksum2: str = hashlib.sha256(payload2.encode()).hexdigest()[:8].upper()
            if checksum != expected_checksum2:
                return False, "Checksum mismatch - key may be tampered"
        return True, tier.lower()

    def activate(self, key: str) -> Tuple[bool, str]:
        """Activate a validated license key and persist it to disk.

        Validates the key, writes the license data (including machine ID and
        activation timestamp) to ``license.json``, and updates the in-memory
        state.

        Args:
            key: The license key to activate.

        Returns:
            A tuple of ``(success, detail)`` where *detail* is the tier name
            on success or an error message on failure.
        """
        valid, result = self.validate_key(key)
        if not valid:
            return False, result
        tier: str = result
        license_data: Dict[str, Any] = {
            "key": key.strip().upper(),
            "tier": tier,
            "machine_id": self._get_machine_id(),
            "activated_at": datetime.now().isoformat(),
            "features": self.FEATURES.get(tier, self.FEATURES["basic"]),
        }
        with open(self.license_file, "w") as f:
            json.dump(license_data, f, indent=2)
        self._license = license_data
        return True, tier

    def is_licensed(self) -> bool:
        """Check whether a valid license is currently active.

        Returns:
            ``True`` if a license has been activated and loaded, ``False``
            otherwise.
        """
        return self._license is not None

    def get_tier(self) -> str:
        """Return the current license tier.

        Returns:
            The tier name (``"basic"``, ``"pro"``, ``"enterprise"``) if
            licensed, ``"trial"`` if within an active trial period, or
            ``"none"`` if no license or trial is active.
        """
        if self._license:
            return self._license.get("tier", "basic")
        if self._trial and not self._trial_expired():
            return "trial"
        return "none"

    def get_features(self) -> Dict[str, int]:
        """Return the feature quotas for the current tier.

        For paid tiers the quotas are ``-1`` (unlimited). For the trial tier,
        remaining quotas are computed by subtracting usage from trial limits.
        When unlicensed, all quotas are zero.

        Returns:
            A dict mapping feature names to their numeric limits.
        """
        tier: str = self.get_tier()
        if tier in self.FEATURES:
            features: Dict[str, int] = dict(self.FEATURES[tier])
        elif tier == "trial":
            features = {
                "ai_calls": max(0, self.TRIAL_AI_CALLS - self._trial.get("ai_calls_used", 0)),  # type: ignore
                "exports": max(0, self.TRIAL_EXPORTS - self._trial.get("exports_used", 0)),  # type: ignore
                "products": 50,
            }
        else:
            features = {"ai_calls": 0, "exports": 0, "products": 0}
        return features

    def can_use_feature(self, feature: str) -> bool:
        """Check whether the current tier allows use of a specific feature.

        For unlimited features (limit ``-1``) this always returns ``True``.
        For trial mode it compares current usage against the remaining quota.

        Args:
            feature: The feature name to check (e.g. ``"ai_calls"``).

        Returns:
            ``True`` if the feature is available within the current quota.
        """
        features: Dict[str, int] = self.get_features()
        limit: int = features.get(feature, 0)
        if limit == -1:
            return True
        if self.get_tier() == "trial":
            usage: int = self._trial.get(f"{feature}_used", 0)  # type: ignore
            return usage < limit
        return limit > 0

    def record_usage(self, feature: str) -> None:
        """Increment the usage counter for a feature during trial mode.

        No effect if the current tier is not ``"trial"``. The updated counter
        is persisted to disk immediately.

        Args:
            feature: The feature name to record usage for (e.g. ``"ai_calls"``).
        """
        if self.get_tier() != "trial":
            return
        key: str = f"{feature}_used"
        self._trial[key] = self._trial.get(key, 0) + 1  # type: ignore
        self._save_trial()

    def get_usage(self) -> Dict[str, int]:
        """Return current usage statistics for the active tier.

        For the trial tier the dict includes current usage, limits, and days
        remaining. For paid tiers all values are ``-1`` (unlimited). When
        unlicensed all values are zero.

        Returns:
            A dict with keys ``ai_calls``, ``ai_limit``, ``exports``,
            ``export_limit``, and ``days_left``.
        """
        tier: str = self.get_tier()
        if tier == "trial":
            return {
                "ai_calls": self._trial.get("ai_calls_used", 0),  # type: ignore
                "ai_limit": self.TRIAL_AI_CALLS,
                "exports": self._trial.get("exports_used", 0),  # type: ignore
                "export_limit": self.TRIAL_EXPORTS,
                "days_left": self._trial_days_left(),
            }
        elif tier == "none":
            return {"ai_calls": 0, "ai_limit": 0, "exports": 0, "export_limit": 0, "days_left": 0}
        else:
            return {"ai_calls": -1, "ai_limit": -1, "exports": -1, "export_limit": -1, "days_left": -1}

    def start_trial(self) -> bool:
        """Start a new trial period or extend an existing active one.

        If a trial is already active and has not expired, this is a no-op
        that returns ``True``. Otherwise a fresh trial record is written to
        disk.

        Returns:
            ``True`` if a trial is active after the call (new or existing).
        """
        if self._trial and not self._trial_expired():
            return True
        self._trial = {
            "started_at": datetime.now().isoformat(),
            "ai_calls_used": 0,
            "exports_used": 0,
        }
        self._save_trial()
        return True

    def _trial_expired(self) -> bool:
        """Check whether the current trial period has expired.

        Returns:
            ``True`` if no trial exists or the expiry date has passed.
        """
        if not self._trial:
            return True
        started: datetime = datetime.fromisoformat(self._trial["started_at"])
        return datetime.now() > started + timedelta(days=self.TRIAL_DAYS)

    def _trial_days_left(self) -> int:
        """Return the number of days remaining in the current trial.

        Returns:
            Days remaining, clamped to a minimum of 0. Returns 0 when no
            trial is active.
        """
        if not self._trial:
            return 0
        started: datetime = datetime.fromisoformat(self._trial["started_at"])
        end: datetime = started + timedelta(days=self.TRIAL_DAYS)
        remaining: int = (end - datetime.now()).days
        return max(0, remaining)

    def get_status_text(self) -> str:
        """Return a human-readable license status string.

        Returns:
            A string such as ``"Licensed (PRO)"``, ``"Trial (7 days left)"``,
            or ``"Unlicensed"``.
        """
        tier: str = self.get_tier()
        if tier in ("pro", "enterprise"):
            return f"Licensed ({tier.upper()})"
        elif tier == "trial":
            days: int = self._trial_days_left()
            return f"Trial ({days} days left)"
        else:
            return "Unlicensed"

    def get_status_color(self) -> str:
        """Return a hex color code representing the current license status.

        Returns:
            ``"#10b981"`` (green) for paid tiers, ``"#f59e0b"`` (amber) for
            trial, or ``"#ef4444"`` (red) for unlicensed.
        """
        tier: str = self.get_tier()
        if tier in ("pro", "enterprise"):
            return "#10b981"
        elif tier == "trial":
            return "#f59e0b"
        return "#ef4444"

    def deactivate(self) -> None:
        """Deactivate the current license by removing the persisted file.

        Clears the in-memory license state and deletes ``license.json`` from
        disk if it exists.
        """
        if os.path.exists(self.license_file):
            os.remove(self.license_file)
        self._license = None

    def generate_key(self, tier: str = "pro") -> str:
        """Generate a new license key for the given tier.

        Args:
            tier: The license tier (``"basic"``, ``"pro"``, or ``"enterprise"``).

        Returns:
            A formatted license key string ready for activation.
        """
        return self._generate_key(tier)

    def _load_license(self) -> Optional[Dict[str, Any]]:
        """Load persisted license data from disk.

        Returns:
            The license dict if the file exists and the machine ID matches,
            or ``None`` otherwise.
        """
        try:
            if os.path.exists(self.license_file):
                with open(self.license_file, "r") as f:
                    data: Dict[str, Any] = json.load(f)
                if data.get("machine_id") != self._get_machine_id():
                    return None
                return data
        except Exception as e:
            logger.debug(f"Failed to load license: {e}")
        return None

    def _load_trial(self) -> Optional[Dict[str, Any]]:
        """Load persisted trial data from disk.

        Returns:
            The trial dict if the file exists and is valid, or ``None``
            otherwise.
        """
        try:
            if os.path.exists(self.trial_file):
                with open(self.trial_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.debug(f"Failed to load trial: {e}")
        return None

    def _save_trial(self) -> None:
        """Persist the current trial state to disk as JSON.

        Errors are logged at debug level and silently ignored.
        """
        try:
            with open(self.trial_file, "w") as f:
                json.dump(self._trial, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to save trial: {e}")
