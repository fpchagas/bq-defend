from google.cloud import dataplex_v1
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class DataplexExtractor(BaseExtractor):
    """
    Extractor for Dataplex Lakes, Zones, Assets, Data Scan configurations,
    and detailed Data Quality / Data Profile scan results.
    """
    def __init__(self, project_id: str, regions: List[str] = None, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.regions = regions or ["us", "eu", "global", "us-central1"]
        self.dataplex_client = None
        self.datascan_client = None

    def extract(self) -> Dict[str, Any]:
        self.dataplex_client = dataplex_v1.DataplexServiceClient(credentials=self.credentials)
        self.datascan_client = dataplex_v1.DataScanServiceClient(credentials=self.credentials)
        lakes_metadata = []
        datascans_metadata = []

        # 1. Extract Lakes, Zones, and Assets per region
        for region in self.regions:
            parent = f"projects/{self.project_id}/locations/{region}"
            try:
                self.logger.info(f"Listing Dataplex Lakes in {parent}")
                lakes = self.dataplex_client.list_lakes(parent=parent)
                for lake in lakes:
                    zones_metadata = []
                    try:
                        zones = self.dataplex_client.list_zones(parent=lake.name)
                        for zone in zones:
                            assets_metadata = []
                            try:
                                assets = self.dataplex_client.list_assets(parent=zone.name)
                                for asset in assets:
                                    assets_metadata.append({
                                        "name": asset.name.split("/")[-1] if "/" in asset.name else asset.name,
                                        "full_name": asset.name,
                                        "display_name": asset.display_name,
                                        "state": str(asset.state),
                                        "asset_resource_spec": {
                                            "type": str(asset.resource_spec.type_),
                                            "name": asset.resource_spec.name
                                        } if asset.resource_spec else None,
                                        "create_time": asset.create_time.isoformat() if asset.create_time else None,
                                        "labels": dict(asset.labels) if asset.labels else {}
                                    })
                            except Exception as e:
                                self.logger.warning(f"Failed to list assets for zone {zone.name}: {e}")
                                assets_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

                            zones_metadata.append({
                                "name": zone.name.split("/")[-1] if "/" in zone.name else zone.name,
                                "full_name": zone.name,
                                "display_name": zone.display_name,
                                "type": str(zone.type_),
                                "state": str(zone.state),
                                "create_time": zone.create_time.isoformat() if zone.create_time else None,
                                "assets": assets_metadata
                            })
                    except Exception as e:
                        self.logger.warning(f"Failed to list zones for lake {lake.name}: {e}")
                        zones_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

                    lakes_metadata.append({
                        "name": lake.name.split("/")[-1] if "/" in lake.name else lake.name,
                        "full_name": lake.name,
                        "display_name": lake.display_name,
                        "state": str(lake.state),
                        "region": region,
                        "create_time": lake.create_time.isoformat() if lake.create_time else None,
                        "labels": dict(lake.labels) if lake.labels else {},
                        "zones": zones_metadata
                    })
            except Exception as e:
                # Log debug because Dataplex might not be enabled or used in this region
                self.logger.debug(f"Could not list Dataplex Lakes in region {region}: {e}")

        # 2. Extract Data Scans and Job Results per region
        for region in self.regions:
            parent = f"projects/{self.project_id}/locations/{region}"
            try:
                self.logger.info(f"Listing Dataplex Data Scans in {parent}")
                scans = self.datascan_client.list_data_scans(parent=parent)
                for scan in scans:
                    jobs_metadata = []
                    try:
                        jobs = self.datascan_client.list_data_scan_jobs(parent=scan.name)
                        # We inspect up to the 3 most recent jobs to avoid excessive requests
                        for idx, job in enumerate(jobs):
                            if idx >= 3:
                                break

                            # Get full job view containing quality or profiling results
                            request = dataplex_v1.GetDataScanJobRequest(
                                name=job.name,
                                view=dataplex_v1.GetDataScanJobRequest.DataScanJobView.FULL
                            )
                            job_detail = self.datascan_client.get_data_scan_job(request=request)

                            quality_result = None
                            profile_result = None

                            if job_detail.data_quality_result:
                                qr = job_detail.data_quality_result
                                rules = []
                                for rule in qr.rules:
                                    rules.append({
                                        "rule_name": rule.rule.column if rule.rule else None,
                                        "rule_type": str(rule.rule.dimension) if rule.rule else None,
                                        "passed": rule.passed,
                                        "evaluated_count": rule.evaluated_count,
                                        "passed_count": rule.passed_count,
                                        "failed_count": rule.failed_count
                                    })
                                quality_result = {
                                    "passed": qr.passed,
                                    "rules": rules,
                                    "dimensions": {d.dimension: d.passed for d in qr.dimensions} if qr.dimensions else {}
                                }

                            if job_detail.data_profile_result:
                                pr = job_detail.data_profile_result
                                fields = []
                                if pr.profile and pr.profile.fields:
                                    for field in pr.profile.fields:
                                        stats = {}
                                        if field.profile:
                                            f_prof = field.profile
                                            stats = {
                                                "null_ratio": getattr(f_prof, "null_ratio", 0.0),
                                                "distinct_ratio": getattr(f_prof, "distinct_ratio", 0.0),
                                                "min": str(f_prof.min) if f_prof.min else None,
                                                "max": str(f_prof.max) if f_prof.max else None
                                            }
                                        fields.append({
                                            "name": field.name,
                                            "type": field.type_,
                                            "mode": field.mode,
                                            "statistics": stats
                                        })
                                profile_result = {
                                    "fields": fields,
                                    "row_count": pr.row_count
                                }

                            jobs_metadata.append({
                                "name": job_detail.name.split("/")[-1] if "/" in job_detail.name else job_detail.name,
                                "full_name": job_detail.name,
                                "state": str(job_detail.state),
                                "start_time": job_detail.start_time.isoformat() if job_detail.start_time else None,
                                "end_time": job_detail.end_time.isoformat() if job_detail.end_time else None,
                                "data_quality_result": quality_result,
                                "data_profile_result": profile_result
                            })
                    except Exception as e:
                        self.logger.warning(f"Failed to list or get jobs for Data Scan {scan.name}: {e}")
                        jobs_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

                    datascans_metadata.append({
                        "name": scan.name.split("/")[-1] if "/" in scan.name else scan.name,
                        "full_name": scan.name,
                        "description": scan.description,
                        "type": str(scan.type_),
                        "data_spec": {
                            "resource": scan.data.resource if scan.data else None
                        } if scan.data else None,
                        "region": region,
                        "jobs": jobs_metadata
                    })
            except Exception as e:
                # Log debug since Dataplex scans might not be enabled/used in all regions
                self.logger.debug(f"Could not list Dataplex Data Scans in region {region}: {e}")

        return {
            "lakes": lakes_metadata,
            "data_scans": datascans_metadata
        }
