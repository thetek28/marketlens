"""Export service module for persisting and distributing product data.

Handles exporting analyzed product data to multiple file formats including
Excel spreadsheets, PDF reports, and JSON files. Also provides utilities
for saving and loading full analysis state (including hidden gems, categories,
keywords, and cycle count) to support session persistence and resumption.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ExportService:
    """Handles exporting product data to various file formats.

    Supports Excel (.xlsx), PDF, and JSON export formats for product
    analysis results. Also provides methods for saving and loading
    complete analysis state to enable session persistence and resumption
    across application runs.

    Attributes:
        db: Optional database connection for direct persistence.
    """

    def __init__(self, db: Optional[Any] = None):
        self.db = db

    def export_excel(
        self,
        products: List[Dict[str, Any]],
        path: str,
        hidden_gems: Optional[List[Dict[str, Any]]] = None,
        portfolio_summary: Optional[Dict[str, Any]] = None,
        categories: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
    ) -> tuple:
        """Export products to an Excel (.xlsx) file with full data coverage.

        Args:
            products: List of product dictionaries to export.
            path: Output file path including filename.
            hidden_gems: Optional hidden gems list for separate sheet.
            portfolio_summary: Optional portfolio summary dict for sheet.
            categories: Optional category list for reference.
            keywords: Optional keyword list for reference.

        Returns:
            Tuple of (success: bool, error_message: str).
        """
        try:
            from utils.export_engine import ExcelExporter

            exporter = ExcelExporter()
            exporter.export_products(
                products, path,
                hidden_gems=hidden_gems,
                portfolio_summary=portfolio_summary,
                categories=categories,
                keywords=keywords,
            )
            logger.info(f"Excel exported to {path} ({len(products)} products)")
            return True, ""
        except Exception as e:
            logger.error(f"Excel export failed: {e}")
            return False, str(e)

    def export_pdf(
        self,
        products: List[Dict[str, Any]],
        path: str,
        hidden_gems: Optional[List[Dict[str, Any]]] = None,
        portfolio_summary: Optional[Dict[str, Any]] = None,
    ) -> tuple:
        """Export products to a PDF report file with full data coverage.

        Args:
            products: List of product dictionaries to export.
            path: Output file path including filename.
            hidden_gems: Optional hidden gems list for separate section.
            portfolio_summary: Optional portfolio summary (not used in PDF
                currently, but reserved for future use).

        Returns:
            Tuple of (success: bool, error_message: str).
        """
        try:
            from utils.export_engine import PDFExporter

            exporter = PDFExporter()
            exporter.export_report(
                products, path,
                hidden_gems=hidden_gems,
                portfolio_summary=portfolio_summary,
            )
            logger.info(f"PDF exported to {path} ({len(products)} products)")
            return True, ""
        except Exception as e:
            logger.error(f"PDF export failed: {e}")
            return False, f"{e}\nPython: {sys.executable}"

    def export_json(
        self,
        products: List[Dict[str, Any]],
        path: str,
        hidden_gems: Optional[List[Dict[str, Any]]] = None,
        portfolio_summary: Optional[Dict[str, Any]] = None,
        categories: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
    ) -> tuple:
        """Export products to a JSON file with full data coverage.

        Includes an export timestamp and product count alongside the
        product list, hidden gems, portfolio summary, categories, and
        keywords for complete data traceability.

        Args:
            products: List of product dictionaries to export.
            path: Output file path including filename.
            hidden_gems: Optional hidden gems list.
            portfolio_summary: Optional portfolio summary dict.
            categories: Optional categories list.
            keywords: Optional keywords list.

        Returns:
            Tuple of (success: bool, error_message: str).
        """
        try:
            payload = {
                "exported_at": datetime.now().isoformat(),
                "count": len(products),
                "products": products,
            }
            if hidden_gems:
                payload["hidden_gems"] = hidden_gems
            if portfolio_summary:
                payload["portfolio_summary"] = portfolio_summary
            if categories:
                payload["categories"] = categories
            if keywords:
                payload["keywords"] = keywords
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"JSON exported to {path} ({len(products)} products)")
            return True, ""
        except Exception as e:
            logger.error(f"JSON export failed: {e}")
            return False, str(e)

    def get_export_formats(self) -> List[Dict[str, str]]:
        """Get metadata for all available export formats.

        Returns:
            List of dictionaries, each containing 'key' (format identifier),
            'label' (human-readable description), and 'extension' (file extension).
        """
        return [
            {"key": "excel", "label": "Export to Excel (.xlsx)", "extension": ".xlsx"},
            {"key": "pdf", "label": "Export to PDF Report", "extension": ".pdf"},
            {"key": "json", "label": "Export to JSON", "extension": ".json"},
        ]

    def save_products(
        self,
        products: List[Dict[str, Any]],
        hidden_gems: List[Dict[str, Any]],
        categories: List[str],
        keywords: List[str],
        cycle: int,
        path: str,
    ) -> bool:
        """Save full analysis state to a JSON file.

        Persists the complete session state including product results,
        hidden gems, selected categories and keywords, and the current
        cycle count so that the analysis can be resumed later.

        Args:
            products: Main product list.
            hidden_gems: Hidden gems list.
            categories: Selected categories.
            keywords: Selected keywords.
            cycle: Current cycle count.
            path: Output file path including filename.

        Returns:
            True if save succeeded, False otherwise.
        """
        try:
            data = {
                "saved_at": datetime.now().isoformat(),
                "ideas": products,
                "hidden_gems": hidden_gems,
                "categories": categories,
                "keywords": keywords,
                "cycle": cycle,
            }
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)
            logger.info(f"Products saved to {path} ({len(products)} products)")
            return True
        except Exception as e:
            logger.error(f"Failed to save products: {e}")
            return False

    def load_products(self, path: str) -> Optional[Dict[str, Any]]:
        """Load previously saved product data from a JSON file.

        Args:
            path: Input file path to load from.

        Returns:
            Loaded data dictionary containing ideas, hidden_gems, categories,
            keywords, and cycle fields, or None if the file does not exist
            or cannot be read.
        """
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info("Loaded {} products from {}".format(len(data.get("ideas", [])), path))
            return data
        except Exception as e:
            logger.error(f"Failed to load products: {e}")
            return None
