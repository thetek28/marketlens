"""Tests for utils.commercial and utils.helpers modules."""

import json
import logging
import os
import threading
import time
from pathlib import Path

import pytest

from utils.commercial import (
    AutoSave,
    DataValidator,
    MarketLensLogger,
    PerformanceMonitor,
    RateLimiter,
    init_commercial,
    retry_on_failure,
    safe_execute,
)
from utils.helpers import load_results, save_results, setup_logging


# ---------------------------------------------------------------------------
#  helpers.py
# ---------------------------------------------------------------------------

class TestSetupLogging:
    """Tests for setup_logging()."""

    def test_default(self):
        """Default call sets up a configuration (no crash)."""
        setup_logging("DEBUG")
        # basicConfig is a one-shot call so we cannot inspect handlers afterwards;
        # at minimum verify no exception was raised and a known logger works.
        logger = logging.getLogger("test_default_logger")
        logger.info("should not crash")

    def test_with_file(self, tmp_path):
        """When log_file is provided a FileHandler is added and writes to disk."""
        # Ensure root handlers are cleared so basicConfig can work
        root = logging.getLogger()
        root.handlers.clear()
        log_file = tmp_path / "test.log"
        setup_logging("INFO", str(log_file))
        logger = logging.getLogger("test_file_logger")
        logger.info("written to file")
        for h in root.handlers:
            h.flush()
        assert log_file.exists()
        content = log_file.read_text(encoding="utf-8")
        assert "written to file" in content


class TestSaveResults:
    """Tests for save_results()."""

    def test_saves_json(self, tmp_path):
        """JSON is written to the given path."""
        filepath = tmp_path / "out.json"
        data = {"key": "value", "num": 42}
        save_results(data, str(filepath))
        assert filepath.exists()
        assert json.loads(filepath.read_text(encoding="utf-8")) == data

    def test_creates_dirs(self, tmp_path):
        """Parent directories are created when they do not exist."""
        filepath = tmp_path / "sub" / "deep" / "out.json"
        save_results([1, 2, 3], str(filepath))
        assert filepath.exists()
        assert json.loads(filepath.read_text(encoding="utf-8")) == [1, 2, 3]


class TestLoadResults:
    """Tests for load_results()."""

    def test_loads_json(self, tmp_path):
        """JSON file is correctly loaded back."""
        data = {"a": 1, "b": [2, 3]}
        fp = tmp_path / "data.json"
        fp.write_text(json.dumps(data), encoding="utf-8")
        assert load_results(str(fp)) == data

    def test_file_not_found(self, tmp_path):
        """Raises FileNotFoundError when file does not exist."""
        with pytest.raises(FileNotFoundError):
            load_results(str(tmp_path / "nonexistent.json"))


# ---------------------------------------------------------------------------
#  commercial.py — MarketLensLogger
# ---------------------------------------------------------------------------

class TestMarketLensLogger:
    """Every logging method should delegate to the underlying logger."""

    @pytest.fixture(autouse=True)
    def _logger(self):
        obj = MarketLensLogger("test_logger")
        # attach a list handler so we can inspect records
        handler = logging.Handler()
        handler.setLevel(logging.DEBUG)
        records = []
        handler.emit = lambda r: records.append(r)
        obj.logger.handlers.clear()
        obj.logger.addHandler(handler)
        obj.logger.propagate = False
        obj._handler = handler
        obj._records = records
        return obj

    def test_debug(self, _logger):
        _logger.debug("dbg")
        assert _logger._records[0].levelno == logging.DEBUG
        assert _logger._records[0].msg == "dbg"

    def test_info(self, _logger):
        _logger.info("inf")
        assert _logger._records[0].levelno == logging.INFO

    def test_warning(self, _logger):
        _logger.warning("wrn")
        assert _logger._records[0].levelno == logging.WARNING

    def test_error(self, _logger):
        _logger.error("err")
        assert _logger._records[0].levelno == logging.ERROR

    def test_critical(self, _logger):
        _logger.critical("crt")
        assert _logger._records[0].levelno == logging.CRITICAL

    def test_audit(self, _logger):
        _logger.audit("LOGIN", "user=admin")
        assert _logger._records[0].levelno == logging.INFO
        assert "ACTION=LOGIN" in _logger._records[0].msg
        assert "user=admin" in _logger._records[0].msg

    def test_audit_no_details(self, _logger):
        _logger.audit("SHUTDOWN")
        assert "ACTION=SHUTDOWN" in _logger._records[0].msg

    def test_exception(self, _logger):
        _logger.exception("oops")
        assert _logger._records[0].levelno == logging.ERROR
        assert "oops" in _logger._records[0].msg


# ---------------------------------------------------------------------------
#  commercial.py — RateLimiter
# ---------------------------------------------------------------------------

class TestRateLimiter:
    """Thread-safe rate limiter based on deque + lock."""

    def test_defaults(self):
        rl = RateLimiter()
        assert rl.max_calls == 10
        assert rl.period == 60

    def test_custom_values(self):
        rl = RateLimiter(max_calls=5, period=10)
        assert rl.max_calls == 5
        assert rl.period == 10

    def test_wait_no_sleep_needed(self, monkeypatch):
        """With zero previous calls wait() should not sleep."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))
        rl = RateLimiter(max_calls=3, period=10)
        for _ in range(3):
            rl.wait()
        assert sleeps == []  # limit not hit

    def test_wait_cleans_old_calls(self, monkeypatch):
        """Expired calls are removed from the deque."""
        real_time = [1000.0]

        def fake_time():
            return real_time[0]

        monkeypatch.setattr(time, "time", fake_time)
        rl = RateLimiter(max_calls=3, period=10)

        # Add calls far in the past
        rl.calls.append(500.0)
        rl.calls.append(600.0)
        rl.calls.append(700.0)

        rl.wait()
        # All old calls should be removed
        assert len(rl.calls) == 1  # only the newly added one
        assert rl.calls[0] >= 1000.0

    def test_wait_when_limit_hit(self, monkeypatch):
        """After hitting max_calls the next wait should sleep."""
        sleeps = []
        real_time = [1000.0]

        def fake_sleep(s):
            sleeps.append(s)
            real_time[0] += s

        def fake_time():
            return real_time[0]

        monkeypatch.setattr(time, "sleep", fake_sleep)
        monkeypatch.setattr(time, "time", fake_time)

        rl = RateLimiter(max_calls=2, period=10)
        # First two calls – should not sleep
        for _ in range(2):
            rl.wait()
        assert len(sleeps) == 0

        # Third call – now max_calls hit; oldest call was at t=1000, now at t=1000
        # wait_time = 1000 + 10 - 1000 = 10
        rl.wait()
        assert len(sleeps) == 1
        assert 9.9 <= sleeps[0] <= 10.1


# ---------------------------------------------------------------------------
#  commercial.py — AutoSave
# ---------------------------------------------------------------------------

class TestAutoSave:
    """Auto-save with crash recovery."""

    def test_init_creates_dir(self, tmp_path):
        data_dir = tmp_path / "autosave"
        assert not data_dir.exists()
        AutoSave(str(data_dir))
        assert data_dir.exists()

    def test_start_stop(self, tmp_path):
        asv = AutoSave(str(tmp_path / "autosave"), interval=0.1)
        asv.start(lambda: {})
        assert asv._running is True
        assert asv._thread is not None
        assert asv._thread.is_alive()
        asv.stop()
        assert asv._running is False

    def test_start_idempotent(self, tmp_path):
        asv = AutoSave(str(tmp_path / "autosave"))
        asv.start(lambda: {})
        t1 = asv._thread
        asv.start(lambda: {})  # second call — no-op
        assert asv._thread is t1
        asv.stop()

    def test_save_now(self, tmp_path):
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "products.json")
        asv = AutoSave(str(data_dir))

        def get_data():
            return {filepath: {"id": 1, "name": "test"}}

        asv.start(get_data)
        asv.save_now()
        asv.stop()

        assert Path(filepath).exists()
        assert json.loads(Path(filepath).read_text(encoding="utf-8")) == {"id": 1, "name": "test"}

    def test_save_now_non_string_key_skipped(self, tmp_path):
        """Keys that are not strings should be skipped."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        asv = AutoSave(str(data_dir))

        def get_data():
            return {filepath: [1, 2], 42: "should_be_skipped"}

        asv.start(get_data)
        asv.save_now()
        asv.stop()

        assert Path(filepath).exists()
        # 42 key was skipped — only filepath was written
        assert json.loads(Path(filepath).read_text(encoding="utf-8")) == [1, 2]

    def test_save_now_exception_handled(self, tmp_path):
        """If save_now encounters an error, it logs exception and does not crash."""
        data_dir = tmp_path / "autosave"
        asv = AutoSave(str(data_dir))

        def failing_get_data():
            raise ValueError("simulated failure")

        asv.start(failing_get_data)
        # Should not raise
        asv.save_now()
        asv.stop()

    def test_save_now_creates_backup(self, tmp_path):
        """Saving again should create a .bak of the previous file."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        asv = AutoSave(str(data_dir))

        def get_data_v1():
            return {filepath: {"v": 1}}

        asv.start(get_data_v1)
        asv.save_now()

        def get_data_v2():
            return {filepath: {"v": 2}}

        # swap the data function
        asv._get_data = get_data_v2
        asv.save_now()
        asv.stop()

        bak = filepath + ".bak"
        assert Path(bak).exists()
        assert json.loads(Path(bak).read_text(encoding="utf-8")) == {"v": 1}
        assert json.loads(Path(filepath).read_text(encoding="utf-8")) == {"v": 2}

    def test_recover_from_file(self, tmp_path):
        """recover() loads data from the main file."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        asv = AutoSave(str(data_dir))
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(json.dumps({"a": 1}), encoding="utf-8")
        assert asv.recover(filepath) == {"a": 1}

    def test_recover_from_bak(self, tmp_path):
        """recover() falls back to .bak when main file is missing."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        asv = AutoSave(str(data_dir))
        Path(filepath + ".bak").parent.mkdir(parents=True, exist_ok=True)
        Path(filepath + ".bak").write_text(json.dumps({"b": 2}), encoding="utf-8")
        assert asv.recover(filepath) == {"b": 2}

    def test_recover_from_tmp(self, tmp_path):
        """recover() falls back to .tmp when main and .bak are missing."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        asv = AutoSave(str(data_dir))
        Path(filepath + ".tmp").parent.mkdir(parents=True, exist_ok=True)
        Path(filepath + ".tmp").write_text(json.dumps({"c": 3}), encoding="utf-8")
        assert asv.recover(filepath) == {"c": 3}

    def test_recover_returns_none_when_no_files(self, tmp_path):
        """recover() returns None when no variants exist."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        asv = AutoSave(str(data_dir))
        assert asv.recover(filepath) is None

    def test_recover_prefers_main_over_bak(self, tmp_path):
        """Both main and .bak exist — should return main."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text(json.dumps({"main": 1}), encoding="utf-8")
        Path(filepath + ".bak").write_text(json.dumps({"bak": 2}), encoding="utf-8")
        asv = AutoSave(str(data_dir))
        assert asv.recover(filepath) == {"main": 1}

    def test_recover_corrupt_file_continues(self, tmp_path):
        """If the main file is corrupt JSON, it tries the next extension."""
        data_dir = tmp_path / "autosave"
        filepath = str(data_dir / "data.json")
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        Path(filepath).write_text("not-json", encoding="utf-8")
        Path(filepath + ".bak").write_text(json.dumps({"from_bak": True}), encoding="utf-8")
        asv = AutoSave(str(data_dir))
        assert asv.recover(filepath) == {"from_bak": True}


# ---------------------------------------------------------------------------
#  commercial.py — DataValidator
# ---------------------------------------------------------------------------

class TestDataValidator:
    """Validation of product data, emails, URLs, and filenames."""

    # -- validate_product ---------------------------------------------------

    @pytest.mark.parametrize("product", [None, "not_a_dict", 42])
    def test_not_dict(self, product):
        assert DataValidator.validate_product(product) is False

    def test_valid(self):
        p = {"title": "Widget Pro", "price": 29.99, "asin": "B0TEST"}
        assert DataValidator.validate_product(p) is True
        assert p["title"] == "Widget Pro"
        assert p["price"] == 29.99

    def test_no_title(self):
        assert DataValidator.validate_product({"price": 10, "asin": "X"}) is False

    def test_short_title(self):
        assert DataValidator.validate_product({"title": "AB", "price": 10, "asin": "X"}) is False

    def test_title_whitespace_only(self):
        assert DataValidator.validate_product({"title": "   ", "price": 10, "asin": "X"}) is False

    def test_negative_price(self):
        assert DataValidator.validate_product({"title": "OK", "price": -5, "asin": "X"}) is False

    def test_price_over_100k(self):
        assert DataValidator.validate_product({"title": "OK", "price": 100001, "asin": "X"}) is False

    def test_price_string_converted(self):
        p = {"title": "Gadget", "price": "49.99", "asin": "B0X"}
        assert DataValidator.validate_product(p) is True
        assert p["price"] == 49.99

    def test_invalid_price_type_list(self):
        assert DataValidator.validate_product({"title": "G", "price": [1, 2, 3], "asin": "X"}) is False

    def test_invalid_price_type_string(self):
        assert DataValidator.validate_product({"title": "G", "price": "not-a-number", "asin": "X"}) is False

    def test_name_fallback(self):
        p = {"name": "Fallback Product", "price": 15.0, "asin": "B0F"}
        assert DataValidator.validate_product(p) is True
        assert p["title"] == "Fallback Product"

    def test_amazon_price_fallback(self):
        p = {"title": "AP Fallback", "amazon_price": 25.0, "asin": "B0A"}
        assert DataValidator.validate_product(p) is True
        assert p["price"] == 25.0

    def test_rating_too_high(self):
        p = {"title": "Overrated", "price": 10, "asin": "X", "rating": 5.5}
        assert DataValidator.validate_product(p) is True
        assert p["rating"] == 0

    def test_rating_negative(self):
        p = {"title": "Neg", "price": 10, "asin": "X", "rating": -1}
        assert DataValidator.validate_product(p) is True
        assert p["rating"] == 0

    def test_rating_zero(self):
        p = {"title": "Zero", "price": 10, "asin": "X", "rating": 0}
        assert DataValidator.validate_product(p) is True
        assert p["rating"] == 0

    def test_rating_five(self):
        p = {"title": "Max", "price": 10, "asin": "X", "rating": 5}
        assert DataValidator.validate_product(p) is True
        assert p["rating"] == 5

    def test_rating_invalid_type(self):
        p = {"title": "BadRating", "price": 10, "asin": "X", "rating": "bogus"}
        assert DataValidator.validate_product(p) is True
        assert p["rating"] == 0  # defaulted to 0

    def test_negative_reviews(self):
        p = {"title": "NegReviews", "price": 10, "asin": "X", "review_count": -100}
        assert DataValidator.validate_product(p) is True
        assert p["review_count"] == 0

    def test_reviews_invalid_type(self):
        p = {"title": "BadReviews", "price": 10, "asin": "X", "review_count": "lots"}
        assert DataValidator.validate_product(p) is True
        assert p["review_count"] == 0

    def test_title_truncated(self):
        p = {"title": "A" * 600, "price": 10, "asin": "X"}
        assert DataValidator.validate_product(p) is True
        assert len(p["title"]) == 500

    # -- sanitize_filename -------------------------------------------------

    @pytest.mark.parametrize("name,expected", [
        ("file.txt", "file.txt"),
        ("a<b>c:d\"e/f\\g|h?i*j", "a_b_c_d_e_f_g_h_i_j"),
        ("", ""),
        ("   ", "   "),
    ])
    def test_sanitize(self, name, expected):
        assert DataValidator.sanitize_filename(name) == expected

    def test_sanitize_truncated(self):
        long_name = "x" * 300
        result = DataValidator.sanitize_filename(long_name)
        assert len(result) == 200

    # -- validate_email ----------------------------------------------------

    @pytest.mark.parametrize("email,expected", [
        ("user@example.com", True),
        ("a@b.co", True),
        ("no_at_symbol", False),
        ("user@domain", False),  # no dot after @
        ("user@.com", True),     # dot exists after @
        ("", False),
        (None, False),
    ])
    def test_email(self, email, expected):
        assert DataValidator.validate_email(email) is expected

    # -- validate_url ------------------------------------------------------

    @pytest.mark.parametrize("url,expected", [
        ("https://example.com", True),
        ("http://example.com", True),
        ("ftp://example.com", False),
        ("", False),
        (None, False),
        ("example.com", False),
    ])
    def test_url(self, url, expected):
        assert DataValidator.validate_url(url) is expected


# ---------------------------------------------------------------------------
#  commercial.py — PerformanceMonitor
# ---------------------------------------------------------------------------

class TestPerformanceMonitor:
    """Performance tracking."""

    def test_known_metric(self):
        pm = PerformanceMonitor()
        pm.record("api_calls", 3)
        assert pm.metrics["api_calls"] == 3

    def test_unknown_metric_ignored(self):
        pm = PerformanceMonitor()
        pm.record("nonexistent", 99)
        assert "nonexistent" not in pm.metrics
        # known metrics unchanged
        assert pm.metrics["api_calls"] == 0

    def test_get_stats(self):
        pm = PerformanceMonitor()
        pm.record("products_collected", 10)
        pm.record("products_analyzed", 5)
        pm.record("api_calls", 100)
        pm.record("errors", 2)
        stats = pm.get_stats()
        assert stats["products_collected"] == 10
        assert stats["products_analyzed"] == 5
        assert stats["api_calls"] == 100
        assert stats["errors"] == 2
        assert "uptime" in stats

    def test_get_stats_thread_safe(self):
        pm = PerformanceMonitor()
        results = []

        def worker():
            for _ in range(100):
                pm.record("api_calls")
            results.append(pm.get_stats())

        threads = [threading.Thread(target=worker) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert pm.metrics["api_calls"] == 500


# ---------------------------------------------------------------------------
#  commercial.py — retry_on_failure
# ---------------------------------------------------------------------------

class TestRetryOnFailure:
    """Decorator for retrying on exception."""

    def test_success_first_try(self):
        """When the function succeeds immediately, no retries occur."""
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0)
        def ok():
            nonlocal call_count
            call_count += 1
            return "done"

        assert ok() == "done"
        assert call_count == 1

    def test_fail_then_succeed(self):
        """After an exception, the second attempt succeeds."""
        attempts = []

        @retry_on_failure(max_retries=3, delay=0)
        def flaky():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("not ready")
            return "recovered"

        assert flaky() == "recovered"
        assert len(attempts) == 2

    def test_max_retries_exceeded(self):
        """Raises the last exception after exhausting retries."""
        call_count = 0

        @retry_on_failure(max_retries=2, delay=0)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            always_fails()
        assert call_count == 2

    def test_backoff_applied(self, monkeypatch):
        """Each retry doubles the delay."""
        sleeps = []
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        call_count = 0

        @retry_on_failure(max_retries=3, delay=1, backoff=2)
        def fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("nope")

        with pytest.raises(ValueError):
            fails()
        # delays: 1, 2 (third retry does not sleep before raising)
        assert sleeps == [1, 2]


# ---------------------------------------------------------------------------
#  commercial.py — safe_execute
# ---------------------------------------------------------------------------

class TestSafeExecute:
    """Decorator that catches exceptions and returns a default."""

    def test_success(self):
        @safe_execute(default=None)
        def ok():
            return 42

        assert ok() == 42

    def test_exception_returns_default(self):
        @safe_execute(default="fallback")
        def fails():
            raise ValueError("bad")

        assert fails() == "fallback"

    def test_exception_returns_none(self):
        @safe_execute()
        def fails():
            raise ValueError("bad")

        assert fails() is None

    def test_log_error_false(self):
        """When log_error=False, no log warning is emitted."""
        @safe_execute(default=0, log_error=False)
        def fails():
            raise ValueError("silent")

        assert fails() == 0


# ---------------------------------------------------------------------------
#  commercial.py — init_commercial
# ---------------------------------------------------------------------------

class TestInitCommercial:
    """init_commercial returns the global instances."""

    def test_returns_dict_with_all_keys(self, tmp_path):
        result = init_commercial(str(tmp_path / "commercial"))
        assert isinstance(result, dict)
        assert "logger" in result
        assert "rate_limiter" in result
        assert "auto_saver" in result
        assert "validator" in result
        assert "perf_monitor" in result

    def test_auto_saver_is_started_with_dir(self, tmp_path):
        data_dir = str(tmp_path / "commercial")
        result = init_commercial(data_dir)
        assert result["auto_saver"].data_dir == data_dir
        assert result["auto_saver"].interval == 30
        result["auto_saver"].stop()

    def test_global_instances(self, tmp_path):
        result = init_commercial(str(tmp_path / "commercial"))
        from utils.commercial import auto_saver as as_global, logger, perf_monitor, rate_limiter

        assert result["logger"] is logger
        assert result["rate_limiter"] is rate_limiter
        assert result["auto_saver"] is as_global
        assert result["perf_monitor"] is perf_monitor
