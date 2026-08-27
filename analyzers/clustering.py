"""Keyword clustering using scikit-learn."""

import logging
from typing import Any, Dict, List

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

logger = logging.getLogger(__name__)


class KeywordClustering:
    """Groups related keywords into product niches using TF-IDF + KMeans."""

    def __init__(self, config):
        self.config = config
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words="english",
            ngram_range=(1, 2),
        )

    def fit(self, raw_data: dict) -> Dict[str, Any]:
        """Cluster keywords from all data sources."""
        all_terms = self._extract_all_terms(raw_data)
        if len(all_terms) < 3:
            logger.warning("Not enough terms for clustering")
            return {"clusters": [], "n_clusters": 0}

        tfidf_matrix = self.vectorizer.fit_transform(all_terms)
        n_clusters = self._find_optimal_clusters(tfidf_matrix, max_k=min(15, len(all_terms) // 2))

        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels = kmeans.fit_predict(tfidf_matrix)

        clusters = self._build_clusters(all_terms, labels, kmeans.cluster_centers_)
        return {
            "clusters": clusters,
            "n_clusters": n_clusters,
            "terms": all_terms,
            "labels": labels.tolist(),
        }

    def _extract_all_terms(self, raw_data: dict) -> List[str]:
        """Extract all unique terms from collected data."""
        terms = set()

        for record in raw_data.get("trends", []):
            if isinstance(record, dict):
                if "term" in record:
                    terms.add(record["term"])
                if record.get("related_query"):
                    terms.add(record["related_query"])

        for record in raw_data.get("amazon", []):
            if isinstance(record, dict) and "title" in record:
                words = record["title"].lower().split()
                terms.update(words[:5])

        for record in raw_data.get("social", []):
            if isinstance(record, dict):
                if "term" in record:
                    terms.add(record["term"])
                if record.get("hashtag"):
                    terms.add(record["hashtag"])

        return list(terms)

    def _find_optimal_clusters(self, matrix, max_k: int = 15) -> int:
        """Find optimal number of clusters using silhouette score."""
        if matrix.shape[0] < 4:
            return 2

        best_k = 2
        best_score = -1

        for k in range(2, min(max_k + 1, matrix.shape[0])):
            try:
                kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = kmeans.fit_predict(matrix)
                score = silhouette_score(matrix, labels)
                if score > best_score:
                    best_score = score
                    best_k = k
            except Exception as e:
                logger.debug(f"Clustering failed for k={k}: {e}")
                continue

        return best_k

    def _build_clusters(self, terms: List[str], labels: np.ndarray, centers: np.ndarray) -> List[Dict[str, Any]]:
        """Build cluster summaries."""
        clusters: Dict[int, Dict[str, Any]] = {}
        feature_names = self.vectorizer.get_feature_names_out()

        for term, label in zip(terms, labels):
            label = int(label)
            if label not in clusters:
                clusters[label] = {"id": label, "terms": [], "centroid_keywords": []}
            clusters[label]["terms"].append(term)

        for label_id, cluster in clusters.items():
            center = centers[label_id]
            top_indices = center.argsort()[-10:][::-1]
            cluster["centroid_keywords"] = [feature_names[i] for i in top_indices]
            cluster["size"] = len(cluster["terms"])
            cluster["niche"] = " ".join(cluster["centroid_keywords"][:3])

        return sorted(clusters.values(), key=lambda c: c["size"], reverse=True)
