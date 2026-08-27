"""Tests for data collector modules."""

import pytest
from unittest.mock import patch, MagicMock

from data_collectors.realtime import ConnectionTester, RealtimeCollector
from data_collectors.social_media import SocialMediaCollector
from data_collectors.amazon import AmazonCollector
from data_collectors.google_trends import GoogleTrendsCollector
from data_collectors.marketplace import WalmartCollector, EbayCollector, ShopifyCollector, collect_from_marketplaces


# ---------------------------------------------------------------------------
# ConnectionTester
# ---------------------------------------------------------------------------

class TestConnectionTester:
    """Tests for ConnectionTester."""

    def test_init(self):
        tester = ConnectionTester()
        assert tester.session is not None

    @patch("data_collectors.realtime.requests.Session")
    def test_test_internet_success(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200

        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_resp
        mock_session_cls.return_value = mock_instance

        tester = ConnectionTester()
        result = tester.test_internet()

        assert result["connected"] is True
        assert result["latency_ms"] > 0
        assert len(result["tests"]) > 0

    @patch("data_collectors.realtime.requests.Session")
    def test_test_internet_failure(self, mock_session_cls):
        mock_instance = MagicMock()
        mock_instance.get.side_effect = Exception("Connection refused")
        mock_session_cls.return_value = mock_instance

        tester = ConnectionTester()
        result = tester.test_internet()

        assert result["connected"] is False
        assert all(t["status"] == "ERROR" for t in result["tests"])

    @patch("data_collectors.realtime.requests.Session")
    def test_test_all(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.text = '<div id="s-search-result">item</div>'

        mock_instance = MagicMock()
        mock_instance.get.return_value = mock_resp
        mock_session_cls.return_value = mock_instance

        with patch("data_collectors.realtime.ConnectionTester.test_google_trends") as mock_gt:
            mock_gt.return_value = {"name": "Google Trends", "status": "OK", "available": True}

            tester = ConnectionTester()
            result = tester.test_all()

            assert "internet" in result
            assert "google_trends" in result
            assert "amazon" in result
            assert "timestamp" in result
            assert result["overall_status"] in ("OK", "PARTIAL")


# ---------------------------------------------------------------------------
# RealtimeCollector
# ---------------------------------------------------------------------------

class TestRealtimeCollector:
    """Tests for RealtimeCollector."""

    def test_init(self):
        collector = RealtimeCollector()
        assert collector.config == {}
        assert collector._status == "idle"
        assert collector._progress == 0

    def test_init_with_config(self):
        config = {"timeout": 30}
        collector = RealtimeCollector(config)
        assert collector.config == config

    def test_collect_empty(self):
        collector = RealtimeCollector()
        result = collector.collect_realtime(categories=[], keywords=[])
        assert result == {"trends": [], "amazon": [], "social": []}
        assert collector._status == "No search terms provided"


# ---------------------------------------------------------------------------
# SocialMediaCollector
# ---------------------------------------------------------------------------

class TestSocialMediaCollector:
    """Tests for SocialMediaCollector."""

    def test_init(self):
        config = {"user_agent": "test"}
        collector = SocialMediaCollector(config)
        assert collector.config == config
        assert collector.session is not None

    def test_collect_empty(self):
        collector = SocialMediaCollector({})
        result = collector.collect(categories=[], keywords=[])
        assert result == []

    def test_collect_none_input(self):
        collector = SocialMediaCollector({})
        result = collector.collect(categories=None, keywords=None)
        assert result == []


# ---------------------------------------------------------------------------
# AmazonCollector
# ---------------------------------------------------------------------------

class TestAmazonCollector:
    """Tests for AmazonCollector."""

    @patch("data_collectors.amazon.SellerInfoScraper")
    def test_init(self, mock_seller_cls):
        config = {"categories": ["kitchen"]}
        collector = AmazonCollector(config)
        assert collector.config == config
        mock_seller_cls.assert_called_once()


# ---------------------------------------------------------------------------
# GoogleTrendsCollector
# ---------------------------------------------------------------------------

class TestGoogleTrendsCollector:
    """Tests for GoogleTrendsCollector."""

    def test_init(self):
        config = {"geo": "US"}
        collector = GoogleTrendsCollector(config)
        assert collector.config == config

    def test_collect_empty(self):
        collector = GoogleTrendsCollector({})
        result = collector.collect(categories=[], keywords=[])
        assert result == []

    def test_collect_none_input(self):
        collector = GoogleTrendsCollector({})
        result = collector.collect(categories=None, keywords=None)
        assert result == []


# ---------------------------------------------------------------------------
# WalmartCollector
# ---------------------------------------------------------------------------

class TestWalmartCollector:
    """Tests for WalmartCollector."""

    def test_init(self):
        collector = WalmartCollector()
        assert collector.session is not None

    def test_init_with_config(self):
        config = {"timeout": 30}
        collector = WalmartCollector(config)
        assert collector.config == config

    @patch("data_collectors.marketplace.WalmartCollector._parse_search")
    @patch("data_collectors.marketplace.requests.Session")
    def test_collect_empty_query(self, mock_session_cls, mock_parse):
        mock_parse.return_value = []
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = ""
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        collector = WalmartCollector()
        result = collector.collect(categories=[], keywords=[])
        assert result == []

    @patch("data_collectors.marketplace.requests.Session")
    def test_collect_handles_exception(self, mock_session_cls):
        mock_session = MagicMock()
        mock_session.get.side_effect = Exception("Timeout")
        mock_session_cls.return_value = mock_session

        collector = WalmartCollector()
        result = collector.collect(categories=["kitchen"], keywords=["test"])
        assert result == []


# ---------------------------------------------------------------------------
# EbayCollector
# ---------------------------------------------------------------------------

class TestEbayCollector:
    """Tests for EbayCollector."""

    def test_init_no_api_key(self):
        collector = EbayCollector()
        assert collector.ebay_app_id == ""

    @patch("data_collectors.marketplace.requests.Session")
    def test_collect_without_api_key_uses_fallback(self, mock_session_cls):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = "<html></html>"
        mock_session = MagicMock()
        mock_session.get.return_value = mock_resp
        mock_session_cls.return_value = mock_session

        collector = EbayCollector()
        result = collector.collect(categories=["kitchen"], keywords=["test"])
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# ShopifyCollector
# ---------------------------------------------------------------------------

class TestShopifyCollector:
    """Tests for ShopifyCollector."""

    def test_init_default_stores(self):
        collector = ShopifyCollector()
        assert len(collector.stores) == 2

    def test_init_custom_stores(self):
        config = {"shopify_stores": ["https://example.com/products.json"]}
        collector = ShopifyCollector(config)
        assert collector.stores == ["https://example.com/products.json"]

    @patch("data_collectors.marketplace.requests.get")
    def test_collect_handles_exception(self, mock_get):
        mock_get.side_effect = Exception("Connection failed")
        collector = ShopifyCollector()
        result = collector.collect()
        assert result == []


# ---------------------------------------------------------------------------
# collect_from_marketplaces
# ---------------------------------------------------------------------------

class TestCollectFromMarketplaces:
    """Tests for collect_from_marketplaces helper."""

    @patch("data_collectors.marketplace.ShopifyCollector.collect")
    @patch("data_collectors.marketplace.EbayCollector.collect")
    @patch("data_collectors.marketplace.WalmartCollector.collect")
    def test_collects_from_all(self, mock_wm, mock_ebay, mock_shopify):
        mock_wm.return_value = [{"name": "WM Product"}]
        mock_ebay.return_value = [{"name": "eBay Product"}]
        mock_shopify.return_value = [{"name": "Shopify Product"}]

        result = collect_from_marketplaces(categories=["kitchen"], keywords=["test"])
        assert len(result) == 3

    def test_default_categories_and_keywords(self):
        result = collect_from_marketplaces()
        assert isinstance(result, list)
