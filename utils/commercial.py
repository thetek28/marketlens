"""MarketLens Commercial Grade - Logging, Error Handling, Auto-Save, Rate Limiting."""

import json
import logging
import os
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime
from functools import wraps
from pathlib import Path

if getattr(sys, 'frozen', False):
    _COMM_BASE = os.path.dirname(os.path.dirname(sys.executable))
else:
    _COMM_BASE = str(Path(__file__).parent.parent)

LOG_DIR = os.path.join(_COMM_BASE, "logs")
os.makedirs(LOG_DIR, exist_ok=True)


class MarketLensLogger:
    """Centralized logging with file rotation and audit trail."""

    def __init__(self, name="marketlens"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)

        if not self.logger.handlers:
            fh = logging.FileHandler(
                os.path.join(LOG_DIR, "marketlens.log"),
                encoding="utf-8", delay=True
            )
            fh.setLevel(logging.DEBUG)
            fmt = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            fh.setFormatter(fmt)
            self.logger.addHandler(fh)

            ch = logging.StreamHandler()
            ch.setLevel(logging.WARNING)
            ch.setFormatter(fmt)
            self.logger.addHandler(ch)

            audit_fh = logging.FileHandler(
                os.path.join(LOG_DIR, "audit.log"),
                encoding="utf-8", delay=True
            )
            audit_fh.setLevel(logging.INFO)
            audit_fmt = logging.Formatter(
                "%(asctime)s [AUDIT] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            audit_fh.setFormatter(audit_fmt)
            self._audit_handler = audit_fh
            self.logger.addHandler(audit_fh)

    def debug(self, msg):
        self.logger.debug(msg)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def critical(self, msg):
        self.logger.critical(msg)

    def audit(self, action, details=""):
        self.logger.info(f"ACTION={action} {details}")

    def exception(self, msg, exc=None):
        self.logger.error(f"{msg}: {traceback.format_exc()}")


logger = MarketLensLogger()


class RateLimiter:
    """Thread-safe rate limiter for API calls."""

    def __init__(self, max_calls=10, period=60):
        self.max_calls = max_calls
        self.period = period
        self.calls = deque()
        self.lock = threading.Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            while self.calls and self.calls[0] <= now - self.period:
                self.calls.popleft()
            if len(self.calls) >= self.max_calls:
                wait_time = self.calls[0] + self.period - now
                if wait_time > 0:
                    time.sleep(wait_time)
                self.calls.popleft()
            self.calls.append(time.time())


class AutoSave:
    """Auto-save data periodically with crash recovery."""

    def __init__(self, data_dir, interval=30):
        self.data_dir = data_dir
        self.interval = interval
        self._running = False
        self._thread = None
        self._pending = {}
        self._lock = threading.Lock()
        os.makedirs(data_dir, exist_ok=True)

    def start(self, get_data_func):
        if self._running:
            return
        self._running = True
        self._get_data = get_data_func
        self._thread = threading.Thread(target=self._auto_save_loop, daemon=True)
        self._thread.start()
        logger.info(f"Auto-save started (interval={self.interval}s)")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Auto-save stopped")

    def save_now(self):
        try:
            data = self._get_data()
            for filepath, value in data.items():
                if not isinstance(filepath, str):
                    continue
                tmp = filepath + ".tmp"
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(value, f, indent=2, ensure_ascii=False, default=str)
                if os.path.exists(filepath):
                    os.replace(filepath, filepath + ".bak")
                os.replace(tmp, filepath)
            logger.debug("Auto-save completed")
        except Exception:
            logger.exception("Auto-save failed")

    def _auto_save_loop(self):
        while self._running:
            time.sleep(self.interval)
            if self._running:
                self.save_now()

    def recover(self, filepath):
        for ext in ["", ".bak", ".tmp"]:
            try:
                path = filepath + ext
                if os.path.exists(path):
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    logger.info(f"Recovered data from {path}")
                    return data
            except Exception:
                continue
        return None


class DataValidator:
    """Validates and sanitizes product data."""

    REQUIRED_FIELDS = ["title", "price", "asin"]
    ASIN_RE = __import__("re").compile(r"^B0[A-Z0-9]{8}$")

    @staticmethod
    def validate_product(product):
        if not isinstance(product, dict):
            return False

        asin = str(product.get("asin", "")).strip().upper()
        if not DataValidator.ASIN_RE.match(asin):
            return False
        product["asin"] = asin

        title = product.get("title", product.get("name", ""))
        if not title or len(str(title).strip()) < 3:
            return False

        price = product.get("price", product.get("amazon_price", 0))
        try:
            price = float(price)
        except (TypeError, ValueError):
            return False
        if price < 0 or price > 100000:
            return False

        rating = product.get("rating", 0)
        try:
            rating = float(rating)
        except (TypeError, ValueError):
            rating = 0
        if rating < 0 or rating > 5:
            rating = 0

        reviews = product.get("review_count", 0)
        try:
            reviews = int(reviews)
        except (TypeError, ValueError):
            reviews = 0
        if reviews < 0:
            reviews = 0

        product["title"] = str(title).strip()[:500]
        product["price"] = round(price, 2)
        product["rating"] = round(rating, 1)
        product["review_count"] = reviews

        return True

    @staticmethod
    def sanitize_filename(name):
        invalid = '<>:"/\\|?*'
        for ch in invalid:
            name = name.replace(ch, "_")
        return name[:200]

    @staticmethod
    def validate_email(email):
        if not email:
            return False
        return "@" in email and "." in email.split("@")[-1]

    @staticmethod
    def validate_url(url):
        if not url:
            return False
        return url.startswith("http://") or url.startswith("https://")


class PerformanceMonitor:
    """Monitors app performance and memory usage."""

    def __init__(self):
        self.metrics = {
            "products_collected": 0,
            "products_analyzed": 0,
            "api_calls": 0,
            "errors": 0,
            "start_time": datetime.now(),
        }
        self._lock = threading.Lock()

    def record(self, metric, value=1):
        with self._lock:
            if metric in self.metrics:
                self.metrics[metric] = self.metrics.get(metric, 0) + value

    def get_stats(self):
        with self._lock:
            uptime = datetime.now() - self.metrics["start_time"]
            return {
                "uptime": str(uptime).split(".")[0],
                "products_collected": self.metrics.get("products_collected", 0),
                "products_analyzed": self.metrics.get("products_analyzed", 0),
                "api_calls": self.metrics.get("api_calls", 0),
                "errors": self.metrics.get("errors", 0),
            }


def retry_on_failure(max_retries=3, delay=2, backoff=2):
    """Decorator for retrying failed operations with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            current_delay = delay
            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.warning(f"All {max_retries} retries failed for {func.__name__}: {e}")
                        raise
                    logger.debug(f"Retry {retries}/{max_retries} for {func.__name__} after {current_delay}s: {e}")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator


def safe_execute(default=None, log_error=True):
    """Decorator that catches exceptions and returns a default value."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.warning(f"Error in {func.__name__}: {e}")
                return default
        return wrapper
    return decorator


perf_monitor = PerformanceMonitor()
rate_limiter = RateLimiter(max_calls=10, period=60)
auto_saver = None


def init_commercial(data_dir):
    """Initialize commercial-grade features."""
    global auto_saver
    auto_saver = AutoSave(data_dir, interval=30)
    logger.info("MarketLens Commercial Grade initialized")
    logger.audit("APP_START", f"data_dir={data_dir}")
    return {
        "logger": logger,
        "rate_limiter": rate_limiter,
        "auto_saver": auto_saver,
        "validator": DataValidator(),
        "perf_monitor": perf_monitor,
    }
