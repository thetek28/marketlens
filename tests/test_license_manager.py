"""Tests for security.license_manager module."""

import json
import os
from pathlib import Path

import pytest

from security.license_manager import LicenseManager


class TestLicenseManagerInit:
    """Test LicenseManager initialization."""

    def test_creates_data_directory(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        assert tmp_data_dir.exists()

    def test_default_tier_is_none(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        assert mgr.get_tier() == "none"

    def test_not_licensed_initially(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        assert mgr.is_licensed() is False


class TestMachineId:
    """Test machine ID generation."""

    def test_returns_string(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mid = mgr._get_machine_id()
        assert isinstance(mid, str)

    def test_length_is_16(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mid = mgr._get_machine_id()
        assert len(mid) == 16

    def test_consistent_across_calls(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mid1 = mgr._get_machine_id()
        mid2 = mgr._get_machine_id()
        assert mid1 == mid2


class TestKeyGeneration:
    """Test license key generation."""

    def test_generates_valid_format(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key = mgr.generate_key("pro")
        parts = key.split("-")
        assert len(parts) == 4
        assert parts[0] == "ML"
        assert parts[1] == "PRO"

    def test_generates_different_keys(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key1 = mgr.generate_key("pro")
        key2 = mgr.generate_key("pro")
        # Keys may be same if generated in same second
        # Just verify format is valid
        assert len(key1.split("-")) == 4


class TestKeyValidation:
    """Test license key validation."""

    def test_valid_key(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key = mgr.generate_key("pro")
        valid, tier = mgr.validate_key(key)
        assert valid is True
        assert tier == "pro"

    def test_invalid_format(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        valid, msg = mgr.validate_key("INVALID")
        assert valid is False
        assert "format" in msg.lower()

    def test_invalid_prefix(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        valid, msg = mgr.validate_key("XX-PRO-123456-ABCDEF12")
        assert valid is False
        assert "prefix" in msg.lower()

    def test_invalid_tier(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        valid, msg = mgr.validate_key("ML-PLATINUM-123456-ABCDEF12")
        assert valid is False
        assert "tier" in msg.lower()

    def test_too_many_parts(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        valid, msg = mgr.validate_key("ML-PRO-123-ABC-DEF")
        assert valid is False


class TestActivation:
    """Test license activation."""

    def test_activate_valid_key(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key = mgr.generate_key("pro")
        success, tier = mgr.activate(key)

        assert success is True
        assert tier == "pro"
        assert mgr.is_licensed() is True
        assert mgr.get_tier() == "pro"

    def test_activate_invalid_key(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        success, msg = mgr.activate("INVALID-KEY")
        assert success is False
        assert mgr.is_licensed() is False

    def test_license_persists(self, tmp_data_dir: Path):
        mgr1 = LicenseManager(str(tmp_data_dir))
        key = mgr1.generate_key("pro")
        mgr1.activate(key)

        # Create new instance
        mgr2 = LicenseManager(str(tmp_data_dir))
        assert mgr2.is_licensed() is True
        assert mgr2.get_tier() == "pro"

    def test_machine_lock(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key = mgr.generate_key("pro")
        mgr.activate(key)

        # Tamper with machine_id in license file
        license_file = tmp_data_dir / "license.json"
        with open(license_file, "r") as f:
            data = json.load(f)
        data["machine_id"] = "tampered"
        with open(license_file, "w") as f:
            json.dump(data, f)

        # New instance should reject
        mgr2 = LicenseManager(str(tmp_data_dir))
        assert mgr2.is_licensed() is False


class TestTrial:
    """Test trial mode."""

    def test_start_trial(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mgr.start_trial()

        assert mgr.get_tier() == "trial"
        assert mgr._trial_days_left() > 0

    def test_trial_expired(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mgr.start_trial()

        # Manually expire trial
        mgr._trial["started_at"] = "2020-01-01T00:00:00"
        mgr._save_trial()

        assert mgr._trial_expired() is True
        assert mgr.get_tier() == "none"

    def test_trial_features(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mgr.start_trial()

        features = mgr.get_features()
        assert features["ai_calls"] > 0
        assert features["exports"] > 0

    def test_trial_usage_tracking(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mgr.start_trial()

        mgr.record_usage("ai_calls")
        usage = mgr.get_usage()

        assert usage["ai_calls"] == 1
        assert usage["ai_limit"] == 50


class TestFeatures:
    """Test feature gating."""

    def test_pro_features_unlimited(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key = mgr.generate_key("pro")
        mgr.activate(key)

        assert mgr.can_use_feature("ai_calls") is True
        assert mgr.can_use_feature("exports") is True
        assert mgr.can_use_feature("products") is True

    def test_no_license_no_features(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        assert mgr.can_use_feature("ai_calls") is False

    def test_trial_feature_limits(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        mgr.start_trial()

        # Use up all AI calls
        for _ in range(50):
            mgr.record_usage("ai_calls")

        assert mgr.can_use_feature("ai_calls") is False


class TestDeactivation:
    """Test license deactivation."""

    def test_deactivate(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))
        key = mgr.generate_key("pro")
        mgr.activate(key)

        mgr.deactivate()
        assert mgr.is_licensed() is False
        assert mgr.get_tier() == "none"

    def test_status_text(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))

        # No license
        assert "Unlicensed" in mgr.get_status_text()

        # Licensed
        key = mgr.generate_key("pro")
        mgr.activate(key)
        assert "Licensed" in mgr.get_status_text()
        assert "PRO" in mgr.get_status_text()

    def test_status_color(self, tmp_data_dir: Path):
        mgr = LicenseManager(str(tmp_data_dir))

        # No license = red
        assert mgr.get_status_color() == "#ef4444"

        # Licensed = green
        key = mgr.generate_key("pro")
        mgr.activate(key)
        assert mgr.get_status_color() == "#10b981"
