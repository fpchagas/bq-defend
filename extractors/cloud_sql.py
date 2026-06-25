import googleapiclient.discovery
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class CloudSQLExtractor(BaseExtractor):
    """
    Extractor for Cloud SQL databases using SQL Admin API via google-api-python-client.
    """
    def __init__(self, project_id: str, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        # cache_discovery=False prevents local filesystem warnings/errors during discovery
        self.sql_service = googleapiclient.discovery.build(
            'sqladmin', 'v1beta4', credentials=self.credentials, cache_discovery=False
        )

    def extract(self) -> Dict[str, Any]:
        instances_metadata = []
        try:
            request = self.sql_service.instances().list(project=self.project_id)
            while request is not None:
                response = request.execute()
                instances = response.get('items', [])
                for instance in instances:
                    instances_metadata.append(self._extract_instance(instance))
                request = self.sql_service.instances().list_next(previous_request=request, previous_response=response)
        except Exception as e:
            self.logger.error(f"Error listing Cloud SQL instances in project {self.project_id}: {e}")
            return {"instances": [], "error": str(e)}

        return {"instances": instances_metadata}

    def _extract_instance(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        instance_name = instance.get('name')
        databases = []
        try:
            db_request = self.sql_service.databases().list(project=self.project_id, instance=instance_name)
            db_response = db_request.execute()
            for db in db_response.get('items', []):
                databases.append({
                    "name": db.get('name'),
                    "charset": db.get('charset'),
                    "collation": db.get('collation')
                })
        except Exception as e:
            self.logger.error(f"Error listing databases for Cloud SQL instance {instance_name}: {e}")
            databases = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

        return {
            "name": instance_name,
            "database_version": instance.get('databaseVersion'),
            "tier": instance.get('settings', {}).get('tier'),
            "region": instance.get('region'),
            "state": instance.get('state'),
            "backend_type": instance.get('backendType'),
            "ip_addresses": instance.get('ipAddresses', []),
            "settings": {
                "activation_policy": instance.get('settings', {}).get('activationPolicy'),
                "data_disk_size_gb": instance.get('settings', {}).get('dataDiskSizeGb'),
                "data_disk_type": instance.get('settings', {}).get('dataDiskType'),
                "database_flags": instance.get('settings', {}).get('databaseFlags', [])
            },
            "databases": databases
        }
