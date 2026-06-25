from google.cloud import bigtable
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class BigtableExtractor(BaseExtractor):
    """
    Extractor for Google Cloud Bigtable instances, clusters, tables, and column families.
    """
    def __init__(self, project_id: str, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.bigtable_client = None

    def extract(self) -> Dict[str, Any]:
        self.bigtable_client = bigtable.Client(project=self.project_id, credentials=self.credentials, admin=True)
        instances_metadata = []
        try:
            res = self.bigtable_client.list_instances()
            # list_instances returns a tuple (instances, failed_locations)
            instances = res[0] if isinstance(res, tuple) else res
            for instance in instances:
                instances_metadata.append(self._extract_instance(instance))
        except Exception as e:
            self.logger.error(f"Error listing Bigtable instances in project {self.project_id}: {e}")
            return {"instances": [], "error": str(e)}

        return {"instances": instances_metadata}

    def _extract_instance(self, instance) -> Dict[str, Any]:
        clusters_metadata = []
        try:
            res_clusters = instance.list_clusters()
            clusters = res_clusters[0] if isinstance(res_clusters, tuple) else res_clusters
            for cluster in clusters:
                clusters_metadata.append({
                    "cluster_id": cluster.cluster_id,
                    "location": cluster.location,
                    "serve_nodes": cluster.serve_nodes,
                    "state": str(cluster.state) if hasattr(cluster, "state") else "UNKNOWN"
                })
        except Exception as e:
            self.logger.error(f"Error listing clusters for Bigtable instance {instance.instance_id}: {e}")
            clusters_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

        tables_metadata = []
        try:
            tables = instance.list_tables()
            for table in tables:
                column_families = []
                try:
                    cfs = table.column_families
                    for cf_id, cf in cfs.items():
                        column_families.append({
                            "family_id": cf_id,
                            "gc_rule": str(cf.gc_rule) if hasattr(cf, "gc_rule") else None
                        })
                except Exception as e:
                    self.logger.error(f"Error listing column families for table {table.table_id}: {e}")
                    column_families = [{"error": str(e)}]

                tables_metadata.append({
                    "table_id": table.table_id,
                    "column_families": column_families
                })
        except Exception as e:
            self.logger.error(f"Error listing tables for Bigtable instance {instance.instance_id}: {e}")
            tables_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

        return {
            "instance_id": instance.instance_id,
            "display_name": instance.display_name,
            "state": str(instance.state) if hasattr(instance, "state") else "UNKNOWN",
            "type": str(instance.instance_type) if hasattr(instance, "instance_type") else "PRODUCTION",
            "clusters": clusters_metadata,
            "tables": tables_metadata
        }
