"""Amazon SP-API integration for ASIN-level gating detection.

Requires Amazon Seller account credentials stored in KeyStore.
The getListingsRestrictions endpoint returns gating info by ASIN.

Credentials needed:
  - refresh_token
  - lwa_app_id
  - lwa_client_secret
  - aws_access_key
  - aws_secret_key
  - role_arn
  - seller_id (merchant ID)

Usage:
    sp = SPAPIGatingChecker()
    result = sp.check_asin("B08N5WRWNW")
    print(result)  # {"gated": True, "reasons": [...], "level": "brand"}
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"
SP_API_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
MARKETPLACE_IDS = {
    "US": "ATVPDKIKX0DER",
    "UK": "A1F83G8C2ARO7P",
    "DE": "A1PA6795UKMFR9",
    "FR": "A13V1IB3VIYZZH",
    "JP": "A1VC38T7YXB528",
    "CA": "A2EUQ1WTGCTBG2",
    "IT": "APJ6JRA9NG5V4",
    "ES": "A1RKKUPIHCS9HS",
    "IN": "A21TJRUUN4KGV",
    "AU": "A39IBJ37TRP1C6",
}


class SPAPIGatingChecker:
    """Checks ASIN-level gating via Amazon SP-API.

    Falls back gracefully if credentials are not configured.
    """

    def __init__(self, credentials: Optional[Dict] = None, seller_id: str = "",
                 marketplace: str = "US"):
        self.credentials = credentials or {}
        self.seller_id = seller_id
        self.marketplace_id = MARKETPLACE_IDS.get(marketplace, "ATVPDKIKX0DER")
        self._access_token = ""
        self._token_expiry = 0

    @classmethod
    def from_key_store(cls) -> "SPAPIGatingChecker":
        """Create checker from stored credentials."""
        try:
            from security.key_store import KeyStore
            ks = KeyStore()
            creds = json.loads(ks.get("sp_api_credentials") or "{}")
            seller_id = ks.get("sp_api_seller_id") or ""
            marketplace = ks.get("sp_api_marketplace") or "US"
            return cls(credentials=creds, seller_id=seller_id, marketplace=marketplace)
        except Exception as e:
            logger.debug(f"Could not load SP-API credentials: {e}")
            return cls()

    @classmethod
    def from_env(cls) -> "SPAPIGatingChecker":
        """Create checker from environment variables."""
        creds = {
            "refresh_token": os.environ.get("SP_API_REFRESH_TOKEN", ""),
            "lwa_app_id": os.environ.get("SP_API_LWA_APP_ID", ""),
            "lwa_client_secret": os.environ.get("SP_API_LWA_CLIENT_SECRET", ""),
            "aws_access_key": os.environ.get("SP_API_AWS_ACCESS_KEY", ""),
            "aws_secret_key": os.environ.get("SP_API_AWS_SECRET_KEY", ""),
            "role_arn": os.environ.get("SP_API_ROLE_ARN", ""),
        }
        seller_id = os.environ.get("SP_API_SELLER_ID", "")
        marketplace = os.environ.get("SP_API_MARKETPLACE", "US")
        return cls(credentials=creds, seller_id=seller_id, marketplace=marketplace)

    def is_configured(self) -> bool:
        """Check if SP-API credentials are configured."""
        return bool(
            self.credentials.get("refresh_token")
            and self.credentials.get("lwa_app_id")
            and self.credentials.get("lwa_client_secret")
            and self.seller_id
        )

    def _get_access_token(self) -> str:
        """Get or refresh LWA access token."""
        if self._access_token and time.time() < self._token_expiry - 60:
            return self._access_token

        creds = self.credentials
        if not creds.get("lwa_app_id") or not creds.get("lwa_client_secret"):
            raise ValueError("SP-API LWA credentials not configured")

        data = {
            "grant_type": "refresh_token",
            "refresh_token": creds["refresh_token"],
            "client_id": creds["lwa_app_id"],
            "client_secret": creds["lwa_client_secret"],
        }

        resp = requests.post(SP_API_TOKEN_URL, data=data, timeout=10)
        resp.raise_for_status()
        token_data = resp.json()

        self._access_token = token_data["access_token"]
        self._token_expiry = time.time() + token_data.get("expires_in", 3600)
        return self._access_token

    def _get_headers(self) -> Dict[str, str]:
        """Get authenticated headers."""
        token = self._get_access_token()
        return {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
        }

    def check_asin(self, asin: str, condition: str = "new_new") -> Dict[str, Any]:
        """Check if an ASIN is gated via SP-API.

        Args:
            asin: Amazon Standard Identification Number
            condition: Condition type (e.g., "new_new", "used_acceptable")

        Returns:
            Dict with keys: gated, reasons, approval_url, level, raw
        """
        if not self.is_configured():
            return {
                "gated": False,
                "reasons": [],
                "approval_url": "",
                "level": "unknown",
                "raw": None,
                "error": "SP-API credentials not configured",
            }

        try:
            url = f"{SP_API_BASE}/listings/2021-08-01/restrictions"
            params = {
                "asin": asin,
                "sellerId": self.seller_id,
                "marketplaceIds": self.marketplace_id,
                "conditionType": condition,
            }
            headers = self._get_headers()

            resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                time.sleep(retry_after)
                resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code != 200:
                return {
                    "gated": False,
                    "reasons": [],
                    "approval_url": "",
                    "level": "unknown",
                    "raw": None,
                    "error": f"HTTP {resp.status_code}: {resp.text[:200]}",
                }

            data = resp.json()
            restrictions = data.get("restrictions", [])

            if not restrictions:
                return {
                    "gated": False,
                    "reasons": [],
                    "approval_url": "",
                    "level": "none",
                    "raw": data,
                }

            reasons = []
            approval_url = ""
            for restriction in restrictions:
                for reason in restriction.get("reasons", []):
                    reasons.append({
                        "code": reason.get("reasonCode", ""),
                        "message": reason.get("message", ""),
                    })
                    links = reason.get("links", [])
                    for link in links:
                        if link.get("rel") == "self":
                            approval_url = link.get("href", "")

            reason_codes = [r["code"] for r in reasons]
            gated = bool(reasons)
            level = "asin"
            if "APPROVAL_REQUIRED" in reason_codes:
                level = "approval_required"
            elif "NOT_ELIGIBLE" in reason_codes:
                level = "not_eligible"

            return {
                "gated": gated,
                "reasons": reasons,
                "approval_url": approval_url,
                "level": level,
                "raw": data,
            }

        except requests.RequestException as e:
            logger.debug(f"SP-API check failed for {asin}: {e}")
            return {
                "gated": False,
                "reasons": [],
                "approval_url": "",
                "level": "unknown",
                "raw": None,
                "error": str(e),
            }

    def check_brand(self, brand: str, product_type: str = "") -> Dict[str, Any]:
        """Check brand-level gating via SP-API.

        Args:
            brand: Brand name
            product_type: Optional product type for GTIN exemption check

        Returns:
            Dict with keys: gated, reasons, level, raw
        """
        if not self.is_configured():
            return {
                "gated": False,
                "reasons": [],
                "level": "unknown",
                "raw": None,
                "error": "SP-API credentials not configured",
            }

        try:
            url = f"{SP_API_BASE}/listings/2021-08-01/restrictions"
            params = {
                "brand": brand,
                "sellerId": self.seller_id,
                "marketplaceIds": self.marketplace_id,
            }
            if product_type:
                params["productType"] = product_type

            headers = self._get_headers()
            resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "5"))
                time.sleep(retry_after)
                resp = requests.get(url, headers=headers, params=params, timeout=15)

            if resp.status_code != 200:
                return {
                    "gated": False,
                    "reasons": [],
                    "level": "unknown",
                    "raw": None,
                    "error": f"HTTP {resp.status_code}",
                }

            data = resp.json()
            restrictions = data.get("restrictions", [])

            if not restrictions:
                return {
                    "gated": False,
                    "reasons": [],
                    "level": "none",
                    "raw": data,
                }

            reasons = []
            for restriction in restrictions:
                for reason in restriction.get("reasons", []):
                    reasons.append({
                        "code": reason.get("reasonCode", ""),
                        "message": reason.get("message", ""),
                    })

            return {
                "gated": bool(reasons),
                "reasons": reasons,
                "level": "brand",
                "raw": data,
            }

        except requests.RequestException as e:
            logger.debug(f"SP-API brand check failed for {brand}: {e}")
            return {
                "gated": False,
                "reasons": [],
                "level": "unknown",
                "raw": None,
                "error": str(e),
            }

    def check_asins_batch(self, asins: List[str],
                          delay: float = 1.0) -> Dict[str, Dict[str, Any]]:
        """Check multiple ASINs with rate limiting.

        Args:
            asins: List of ASINs to check
            delay: Seconds between requests (SP-API rate limit ~1 req/s)

        Returns:
            Dict mapping ASIN to check result
        """
        results = {}
        for i, asin in enumerate(asins):
            results[asin] = self.check_asin(asin)
            if i < len(asins) - 1:
                time.sleep(delay)
        return results
