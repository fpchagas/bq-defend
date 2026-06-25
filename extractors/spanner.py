from google.cloud import spanner
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class SpannerExtractor(BaseExtractor):
    """
    Extractor for Google Cloud Spanner instances, databases, and schemas (DDLs).
    """
    def __init__(self, project_id: str, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.spanner_client = spanner.Client(project=self.project_id, credentials=self.credentials)

    def extract(self) -> Dict[str, Any]:
        instances_metadata = []
        try:
            instances = list(self.spanner_client.list_instances())
            for instance in instances:
                instances_metadata.append(self._extract_instance(instance))
        except Exception as e:
            self.logger.error(f"Error listing Spanner instances in project {self.project_id}: {e}")
            return {"instances": [], "error": str(e)}

        return {"instances": instances_metadata}

    def _extract_instance(self, instance) -> Dict[str, Any]:
        databases = []
        try:
            dbs = list(instance.list_databases())
            for db in dbs:
                ddl = []
                try:
                    # Get DDL statements representing the schemas of the tables
                    ddl = list(db.get_ddl())
                except Exception as e:
                    self.logger.error(f"Error getting DDL for Spanner database {db.name}: {e}")
                    ddl = [f"/* Error fetching DDL: {e} */"]

                databases.append({
                    "name": db.name.split("/")[-1] if "/" in db.name else db.name,
                    "full_name": db.name,
                    "ddl": ddl
                })
        except Exception as e:
            self.logger.error(f"Error listing databases for Spanner instance {instance.name}: {e}")
            databases = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

        return {
            "name": instance.name.split("/")[-1] if "/" in instance.name else instance.name,
            "full_name": instance.name,
            "display_name": instance.display_name,
            "configuration": instance.configuration,
            "node_count": instance.node_count,
            "processing_units": instance.processing_units,
            "databases": databases
        }
