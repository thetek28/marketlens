"""Encrypted API key storage using Fernet symmetric encryption.

Provides secure storage for API keys and secrets using the Fernet symmetric
encryption scheme from the ``cryptography`` library. Encryption keys are
derived from machine-specific hardware identifiers (hostname, MAC address,
CPU info) so that encrypted files can only be decrypted on the same machine.

Features:
    - Fernet symmetric encryption with machine-derived keys.
    - Automatic migration from legacy plaintext ``api_keys.json`` files.
    - In-memory caching to avoid repeated disk reads and decryption.
    - Base85-encoded fallback when the ``cryptography`` library is absent.

If ``cryptography`` is not installed, keys are stored using a lightweight
base85 obfuscation fallback that does not provide true encryption.
"""

import hashlib
import json
import logging
import os
import platform
import uuid
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


def _get_machine_seed() -> bytes:
    """Generate a machine-specific seed for key derivation."""
    raw: str = f"{platform.node()}-{uuid.getnode()}-{platform.machine()}-{platform.processor()}"
    return hashlib.sha256(raw.encode()).digest()


def _derive_key() -> bytes:
    """Derive a Fernet key from machine hardware."""
    seed: bytes = _get_machine_seed()
    derived: bytes = hashlib.pbkdf2_hmac("sha256", seed, b"marketlens-key-store-v1", 100000)
    return __import__("base64").urlsafe_b64encode(derived[:32])


class KeyStore:
    """Encrypted storage for API keys and secrets.

    Manages Fernet-encrypted persistence of API keys on disk with automatic
    in-memory caching. On construction the store initializes its Fernet cipher
    from a machine-derived key and attempts to migrate any legacy plaintext
    ``api_keys.json`` file to the encrypted format.

    Attributes:
        data_dir: Directory where encrypted key files are stored.
        _keys_file: Path to the encrypted keys file.
        _legacy_file: Path to the legacy plaintext keys file.
        _fernet: Fernet cipher instance, or ``None`` if cryptography is absent.
        _cache: In-memory cache of decrypted key-value pairs.

    Example::

        store = KeyStore()
        store.save({"openai": "sk-...", "claude": "sk-ant-..."})
        keys = store.load()
        assert keys["openai"] == "sk-..."
    """

    def __init__(self, data_dir: Optional[str] = None) -> None:
        """Initialize the key store, Fernet cipher, and migrate legacy data.

        Args:
            data_dir: Path to the directory for storing encrypted keys.
                Defaults to ``<project_root>/data`` when ``None``.
        """
        if data_dir is None:
            try:
                from utils.paths import KEYS_DIR
                data_dir = KEYS_DIR
            except ImportError:
                data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
        self.data_dir: str = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._keys_file: str = os.path.join(data_dir, "keys.enc")
        self._legacy_file: str = os.path.join(data_dir, "api_keys.json")
        self._fernet: Optional[Fernet] = None
        self._cache: Dict[str, str] = {}
        self._init_encryption()
        self._migrate_legacy()

    def _init_encryption(self) -> None:
        """Initialize the Fernet cipher from a machine-derived key.

        Derives a Fernet key using PBKDF2-HMAC-SHA256 with a seed based on
        the current machine's hardware identifiers. Does nothing if the
        ``cryptography`` library is not installed.
        """
        if not HAS_CRYPTOGRAPHY:
            return
        key: bytes = _derive_key()
        self._fernet = Fernet(key)

    def _migrate_legacy(self) -> None:
        """Migrate a legacy plaintext ``api_keys.json`` file to encrypted storage.

        Reads the legacy JSON file if it exists, saves its contents to the
        encrypted store, and removes the original file. Errors are logged at
        debug level and silently ignored.
        """
        if not os.path.exists(self._legacy_file):
            return
        if not self._fernet:
            return
        try:
            with open(self._legacy_file, "r", encoding="utf-8") as f:
                legacy: Dict[str, str] = json.load(f)
            if legacy.get("openai") or legacy.get("claude"):
                self.save(legacy)
                os.remove(self._legacy_file)
                logger.info("Migrated legacy API keys to encrypted storage")
        except Exception as e:
            logger.debug(f"Failed to migrate legacy keys: {e}")

    def save(self, keys: Dict[str, str]) -> bool:
        """Save API keys to encrypted storage.

        Encrypts the key-value pairs with Fernet and writes them to disk.
        Empty values and the ``saved_at`` metadata key are automatically
        excluded. The in-memory cache is updated on success.

        Args:
            keys: Mapping of key names to their secret values.

        Returns:
            ``True`` if the keys were saved successfully, ``False`` otherwise.
        """
        payload: Dict[str, str] = {k: v for k, v in keys.items() if v and k != "saved_at"}
        if not self._fernet:
            return self._save_fallback(payload)
        try:
            plaintext: bytes = json.dumps(payload).encode("utf-8")
            encrypted: bytes = self._fernet.encrypt(plaintext)
            with open(self._keys_file, "wb") as f:
                f.write(encrypted)
            self._cache = dict(payload)
            return True
        except Exception as e:
            logger.error(f"Failed to save encrypted keys: {e}")
            return False

    def load(self) -> Dict[str, str]:
        """Load API keys from encrypted storage.

        Returns cached keys when available. Otherwise reads and decrypts the
        encrypted file, populates the cache, and returns a copy.

        Returns:
            Mapping of key names to their secret values. Returns an empty
            dict if no keys are stored or decryption fails.
        """
        if self._cache:
            return dict(self._cache)
        if not self._fernet:
            return self._load_fallback()
        try:
            if not os.path.exists(self._keys_file):
                return {}
            with open(self._keys_file, "rb") as f:
                encrypted: bytes = f.read()
            plaintext: bytes = self._fernet.decrypt(encrypted)
            self._cache = json.loads(plaintext.decode("utf-8"))
            return dict(self._cache)
        except Exception as e:
            logger.debug(f"Failed to load encrypted keys: {e}")
            return {}

    def get(self, key: str) -> str:
        """Get a single API key by name.

        Args:
            key: The name of the key to retrieve.

        Returns:
            The secret value for the given key, or an empty string if not found.
        """
        return self.load().get(key, "")

    def delete(self, key: str) -> bool:
        """Remove a specific API key from the store.

        Args:
            key: The name of the key to remove.

        Returns:
            ``True`` if the key was found and removed, ``False`` otherwise.
        """
        keys: Dict[str, str] = self.load()
        if key in keys:
            del keys[key]
            return self.save(keys)
        return False

    def clear(self) -> bool:
        """Remove all stored keys and delete the encrypted file.

        Returns:
            ``True`` if the file was removed or did not exist, ``False`` if
            deletion failed.
        """
        self._cache = {}
        if os.path.exists(self._keys_file):
            try:
                os.remove(self._keys_file)
                return True
            except Exception as e:
                logger.debug(f"Failed to clear key store: {e}")
                return False
        return True

    def has_keys(self) -> bool:
        """Check whether any API keys are currently stored.

        Returns:
            ``True`` if at least one key exists, ``False`` otherwise.
        """
        return bool(self.load())

    def _save_fallback(self, payload: Dict[str, str]) -> bool:
        """Save keys using base85-encoded obfuscation (no true encryption).

        Used as a fallback when the ``cryptography`` library is not installed.
        This does **not** provide real security and should only be used for
        convenience in development.

        Args:
            payload: Mapping of key names to their secret values.

        Returns:
            ``True`` if saved successfully, ``False`` otherwise.
        """
        try:
            import base64
            encoded: str = base64.b85encode(json.dumps(payload).encode()).decode()
            with open(self._keys_file, "w", encoding="utf-8") as f:
                f.write(encoded)
            self._cache = dict(payload)
            return True
        except Exception as e:
            logger.error(f"Failed to save keys (fallback): {e}")
            return False

    def _load_fallback(self) -> Dict[str, str]:
        """Load keys from the base85-encoded obfuscated fallback file.

        Returns:
            Mapping of key names to their secret values, or an empty dict on
            failure.
        """
        try:
            if not os.path.exists(self._keys_file):
                return {}
            import base64
            with open(self._keys_file, "r", encoding="utf-8") as f:
                encoded: str = f.read()
            plaintext: str = base64.b85decode(encoded.encode()).decode()
            self._cache = json.loads(plaintext)
            return dict(self._cache)
        except Exception as e:
            logger.debug(f"Failed to load keys (fallback): {e}")
            return {}
