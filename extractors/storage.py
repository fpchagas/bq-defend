from google.cloud import storage
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class StorageExtractor(BaseExtractor):
    """
    Extractor for Google Cloud Storage buckets, including metadata, lifecycle rules,
    governance labels, and estimated size/object count.
    """
    def __init__(self, project_id: str, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.storage_client = storage.Client(project=self.project_id, credentials=self.credentials)

    def extract(self) -> Dict[str, Any]:
        buckets_metadata = []
        try:
            buckets = list(self.storage_client.list_buckets())
            for bucket in buckets:
                buckets_metadata.append(self._extract_bucket(bucket))
        except Exception as e:
            self.logger.error(f"Error listing Storage buckets in project {self.project_id}: {e}")
            return {"buckets": [], "error": str(e)}

        return {"buckets": buckets_metadata}

    def _extract_bucket(self, bucket: storage.Bucket) -> Dict[str, Any]:
        lifecycle_rules = []
        try:
            for rule in bucket.lifecycle_rules:
                lifecycle_rules.append(dict(rule) if isinstance(rule, dict) else {
                    "action": getattr(rule, "action", {}),
                    "condition": getattr(rule, "condition", {})
                })
        except Exception as e:
            self.logger.warning(f"Failed to read lifecycle rules for bucket {bucket.name}: {e}")

        # Quick estimate of size and count to prevent scanning millions of objects
        estimated_object_count = 0
        estimated_volume_bytes = 0
        is_truncated = False
        try:
            # We list up to 1000 blobs for a lightweight estimate
            max_estimate_blobs = 1000
            blobs = list(self.storage_client.list_blobs(bucket.name, max_results=max_estimate_blobs))
            estimated_object_count = len(blobs)
            estimated_volume_bytes = sum(blob.size for blob in blobs if blob.size is not None)
            if estimated_object_count >= max_estimate_blobs:
                is_truncated = True
        except Exception as e:
            self.logger.warning(f"Failed to estimate blob stats for bucket {bucket.name}: {e}")
            estimated_object_count = -1
            estimated_volume_bytes = -1

        return {
            "name": bucket.name,
            "location": bucket.location,
            "location_type": getattr(bucket, "location_type", None),
            "storage_class": bucket.storage_class,
            "time_created": bucket.time_created.isoformat() if bucket.time_created else None,
            "time_updated": bucket.updated.isoformat() if bucket.updated else None,
            "labels": dict(bucket.labels) if bucket.labels else {},
            "lifecycle_rules": lifecycle_rules,
            "estimated_stats": {
                "object_count": estimated_object_count,
                "volume_bytes": estimated_volume_bytes,
                "is_truncated": is_truncated
            }
        }
