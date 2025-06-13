from typing import List, Any


class ClusterDetector:
    """Utilities for detecting clusters in time-series data"""

    @staticmethod
    def detect_time_clusters(
            items: List[Any],
            time_extractor,
            window_minutes: int = 60,
            min_cluster_size: int = 2
    ) -> List[List[Any]]:
        """
        Detect clusters of items based on time proximity.

        Args:
            items: List of items to analyze
            time_extractor: Function to extract datetime from item
            window_minutes: Maximum minutes between items in a cluster
            min_cluster_size: Minimum items to consider a cluster

        Returns:
            List of clusters (each cluster is a list of items)
        """
        if len(items) < min_cluster_size:
            return []

        # Sort items by time
        sorted_items = sorted(items, key=time_extractor)
        clusters = []
        current_cluster = [sorted_items[0]]

        for i in range(1, len(sorted_items)):
            time_diff = (time_extractor(sorted_items[i]) -
                         time_extractor(current_cluster[-1])).total_seconds() / 60

            if time_diff <= window_minutes:
                current_cluster.append(sorted_items[i])
            else:
                if len(current_cluster) >= min_cluster_size:
                    clusters.append(current_cluster)
                current_cluster = [sorted_items[i]]

        # Don't forget the last cluster
        if len(current_cluster) >= min_cluster_size:
            clusters.append(current_cluster)

        return clusters
