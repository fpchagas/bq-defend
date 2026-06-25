from google.cloud import bigquery
from google.cloud import bigquery_datatransfer
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class BigQueryExtractor(BaseExtractor):
    """
    Extractor for BigQuery assets (Datasets, Tables, Views, Schemas)
    and BigQuery Data Transfer configurations (including scheduled queries).
    """
    def __init__(self, project_id: str, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.bq_client = None
        self.transfer_client = None

    def extract(self) -> Dict[str, Any]:
        self.bq_client = bigquery.Client(project=self.project_id, credentials=self.credentials)
        self.transfer_client = bigquery_datatransfer.DataTransferServiceClient(credentials=self.credentials)
        datasets_metadata = []
        try:
            datasets = list(self.bq_client.list_datasets())
            for dataset_ref in datasets:
                dataset_id = dataset_ref.dataset_id
                try:
                    dataset = self.bq_client.get_dataset(dataset_id)
                    datasets_metadata.append(self._extract_dataset(dataset))
                except Exception as e:
                    self.logger.error(f"Error fetching dataset {dataset_id} in {self.project_id}: {e}")
                    datasets_metadata.append({
                        "dataset_id": dataset_id,
                        "error": str(e),
                        "status": "PERMISSION_DENIED_OR_FAILED"
                    })
        except Exception as e:
            self.logger.error(f"Error listing datasets in project {self.project_id}: {e}")
            datasets_metadata = [{"error": str(e)}]

        transfer_configs = []
        try:
            parent = f"projects/{self.project_id}"
            configs = self.transfer_client.list_transfer_configs(parent=parent)
            for config in configs:
                transfer_configs.append({
                    "name": config.name,
                    "display_name": config.display_name,
                    "data_source_id": config.data_source_id,
                    "destination_dataset_id": getattr(config, "destination_dataset_id", None),
                    "state": str(config.state),
                    "schedule": config.schedule,
                    "next_run_time": config.next_run_time.isoformat() if config.next_run_time else None,
                    "update_time": config.update_time.isoformat() if config.update_time else None,
                    "params": dict(config.params) if config.params else {}
                })
        except Exception as e:
            self.logger.error(f"Error listing BigQuery Data Transfer configs: {e}")
            transfer_configs = [{"error": str(e)}]

        return {
            "datasets": datasets_metadata,
            "data_transfers": transfer_configs
        }

    def _extract_dataset(self, dataset: bigquery.Dataset) -> Dict[str, Any]:
        tables_metadata = []
        try:
            tables = list(self.bq_client.list_tables(dataset.reference))
            for table_ref in tables:
                table_id = table_ref.table_id
                try:
                    table = self.bq_client.get_table(table_ref)
                    tables_metadata.append(self._extract_table(table))
                except Exception as e:
                    self.logger.error(f"Error fetching table {table_id} in {dataset.dataset_id}: {e}")
                    tables_metadata.append({
                        "table_id": table_id,
                        "error": str(e),
                        "status": "PERMISSION_DENIED_OR_FAILED"
                    })
        except Exception as e:
            self.logger.error(f"Error listing tables in dataset {dataset.dataset_id}: {e}")
            tables_metadata = [{"error": str(e)}]

        return {
            "dataset_id": dataset.dataset_id,
            "friendly_name": dataset.friendly_name,
            "description": dataset.description,
            "location": dataset.location,
            "labels": dataset.labels,
            "created": dataset.created.isoformat() if dataset.created else None,
            "last_modified": dataset.modified.isoformat() if dataset.modified else None,
            "default_table_expiration_ms": dataset.default_table_expiration_ms,
            "tables": tables_metadata
        }

    def _extract_table(self, table: bigquery.Table) -> Dict[str, Any]:
        schema = []
        for field in table.schema:
            schema.append({
                "name": field.name,
                "type": field.field_type,
                "mode": field.mode,
                "description": field.description,
                "policy_tags": list(field.policy_tags.names) if (field.policy_tags and field.policy_tags.names) else []
            })

        partitioning = None
        if table.time_partitioning:
            partitioning = {
                "type": str(table.time_partitioning.type_),
                "field": table.time_partitioning.field,
                "expiration_ms": table.time_partitioning.expiration_ms
            }
        elif table.range_partitioning:
            partitioning = {
                "type": "RANGE",
                "field": table.range_partitioning.field,
                "range": {
                    "start": table.range_partitioning.range_.start,
                    "end": table.range_partitioning.range_.end,
                    "interval": table.range_partitioning.range_.interval
                }
            }

        metadata = {
            "table_id": table.table_id,
            "table_type": table.table_type,
            "description": table.description,
            "num_rows": table.num_rows,
            "num_bytes": table.num_bytes,
            "created": table.created.isoformat() if table.created else None,
            "last_modified": table.modified.isoformat() if table.modified else None,
            "schema": schema,
            "partitioning": partitioning,
            "clustering_fields": list(table.clustering_fields) if table.clustering_fields else []
        }

        if table.table_type == "VIEW":
            metadata["view_query"] = table.view_query

        return metadata
