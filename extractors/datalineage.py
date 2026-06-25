from google.cloud.datacatalog import lineage_v1
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class DataLineageExtractor(BaseExtractor):
    """
    Extractor for Google Cloud Data Lineage, capturing lineage processes,
    runs, lineage events, and data flow links.
    """
    def __init__(self, project_id: str, regions: List[str] = None, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.regions = regions or ["us", "eu", "global", "us-central1"]
        self.client = lineage_v1.LineageClient(credentials=self.credentials)

    def extract(self) -> Dict[str, Any]:
        processes_metadata = []
        for region in self.regions:
            parent = f"projects/{self.project_id}/locations/{region}"
            try:
                self.logger.info(f"Listing lineage processes in {parent}")
                processes = self.client.list_processes(parent=parent)
                for process in processes:
                    runs_metadata = []
                    try:
                        runs = self.client.list_runs(parent=process.name)
                        for run in runs:
                            events_metadata = []
                            try:
                                events = self.client.list_lineage_events(parent=run.name)
                                for event in events:
                                    links = []
                                    if event.links:
                                        for link in event.links:
                                            links.append({
                                                "source": link.source.fully_qualified_name if hasattr(link.source, "fully_qualified_name") else str(link.source),
                                                "target": link.target.fully_qualified_name if hasattr(link.target, "fully_qualified_name") else str(link.target)
                                            })
                                    events_metadata.append({
                                        "name": event.name,
                                        "start_time": event.start_time.isoformat() if event.start_time else None,
                                        "end_time": event.end_time.isoformat() if event.end_time else None,
                                        "links": links
                                    })
                            except Exception as e:
                                self.logger.warning(f"Failed to list lineage events for run {run.name}: {e}")
                                events_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

                            runs_metadata.append({
                                "name": run.name,
                                "display_name": run.display_name,
                                "state": str(run.state),
                                "start_time": run.start_time.isoformat() if run.start_time else None,
                                "end_time": run.end_time.isoformat() if run.end_time else None,
                                "lineage_events": events_metadata
                            })
                    except Exception as e:
                        self.logger.warning(f"Failed to list runs for process {process.name}: {e}")
                        runs_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

                    processes_metadata.append({
                        "name": process.name.split("/")[-1] if "/" in process.name else process.name,
                        "full_name": process.name,
                        "display_name": process.display_name,
                        "origin": {
                            "source_type": str(process.origin.source_type) if process.origin else None,
                            "name": getattr(process.origin, "name", None)
                        } if process.origin else None,
                        "region": region,
                        "runs": runs_metadata
                    })
            except Exception as e:
                # Log debug since lineage might not be enabled/used in all regions
                self.logger.debug(f"Could not list lineage processes in region {region}: {e}")

        return {"lineage_processes": processes_metadata}
