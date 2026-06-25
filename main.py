import argparse
import os
import concurrent.futures

# Set GRPC_DNS_RESOLVER to native to avoid c-ares DNS resolver thread crashes
os.environ["GRPC_DNS_RESOLVER"] = "native"
import json
import logging
import sys
import google.auth
from typing import List, Dict, Any

from extractors import (
    ResourceManagerExtractor,
    BigQueryExtractor,
    CloudSQLExtractor,
    SpannerExtractor,
    BigtableExtractor,
    StorageExtractor,
    PubSubExtractor,
    DataCatalogExtractor,
    DataLineageExtractor,
    DataplexExtractor,
)

# Configure structured and readable logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("GCPAuditCrawler")

class ExtractorFactory:
    """
    Factory pattern for creating all GCP extractor instances for a specific project.
    """
    @staticmethod
    def get_extractors(project_id: str, credentials, regions: List[str]) -> Dict[str, Any]:
        return {
            "bigquery": BigQueryExtractor(project_id, credentials=credentials),
            "cloud_sql": CloudSQLExtractor(project_id, credentials=credentials),
            "spanner": SpannerExtractor(project_id, credentials=credentials),
            "bigtable": BigtableExtractor(project_id, credentials=credentials),
            "storage": StorageExtractor(project_id, credentials=credentials),
            "pubsub": PubSubExtractor(project_id, credentials=credentials),
            "datacatalog": DataCatalogExtractor(project_id, regions=regions, credentials=credentials),
            "datalineage": DataLineageExtractor(project_id, regions=regions, credentials=credentials),
            "dataplex": DataplexExtractor(project_id, regions=regions, credentials=credentials)
        }

def run_project_extraction(project_id: str, credentials, regions: List[str], max_workers: int) -> Dict[str, Any]:
    """
    Runs extraction for all services in parallel for a single project.
    """
    logger.info(f"============ Starting extraction for project: {project_id} ============")
    extractors = ExtractorFactory.get_extractors(project_id, credentials, regions)
    project_metadata = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_service = {
            executor.submit(extractor.run): service_name
            for service_name, extractor in extractors.items()
        }

        for future in concurrent.futures.as_completed(future_to_service):
            service_name = future_to_service[future]
            try:
                result = future.result()
                project_metadata[service_name] = result
                logger.info(f"Successfully finished extraction for: {service_name} in project {project_id}")
            except Exception as e:
                logger.error(f"Fatal error running extractor for {service_name} in project {project_id}: {e}")
                project_metadata[service_name] = {
                    "error": str(e),
                    "status": "FATAL_CRAWLER_ERROR"
                }

    logger.info(f"============ Completed extraction for project: {project_id} ============")
    return {
        "project_id": project_id,
        "services": project_metadata
    }

def main():
    parser = argparse.ArgumentParser(
        description="GCP Enterprise Data Ecosystem Crawler & Governance Metadata Cataloguer"
    )
    parser.add_argument(
        "--project-id",
        type=str,
        default=None,
        help="A specific GCP Project ID to scan. Overrides org-id or folder-id search."
    )
    parser.add_argument(
        "--org-id",
        type=str,
        default=None,
        help="GCP Organization ID to discover and scan all projects underneath."
    )
    parser.add_argument(
        "--folder-id",
        type=str,
        default=None,
        help="GCP Folder ID to discover and scan all projects underneath."
    )
    parser.add_argument(
        "--regions",
        type=str,
        default="us,eu,global,us-central1",
        help="Comma-separated list of GCP regions to scan for regional resources (Data Catalog, Dataplex, Datalineage)."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="gcp_enterprise_metadata_catalog.json",
        help="Path where output JSON catalog will be saved."
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=8,
        help="Number of threads for parallelizing service crawlers per project."
    )

    args = parser.parse_args()
    regions_list = [r.strip() for r in args.regions.split(",") if r.strip()]

    # 1. Authenticate with Google Cloud
    logger.info("Authenticating via Application Default Credentials (ADC)...")
    try:
        credentials, default_project = google.auth.default()
        logger.info("Authentication successful.")
    except Exception as e:
        logger.error(f"Google Cloud Authentication failed: {e}")
        logger.error("Please set the GOOGLE_APPLICATION_CREDENTIALS environment variable or run 'gcloud auth application-default login'")
        sys.exit(1)

    # 2. Discover Projects
    logger.info("Discovering project resource scopes...")
    try:
        rm_extractor = ResourceManagerExtractor(
            project_id=args.project_id or default_project,
            org_id=args.org_id,
            folder_id=args.folder_id,
            credentials=credentials
        )
        rm_results = rm_extractor.run()
        projects = rm_results.get("projects", [])
    except Exception as e:
        logger.error(f"Failed to list or resolve project scopes: {e}")
        sys.exit(1)

    if not projects:
        logger.error("No projects resolved. Check credentials, project configurations, or organizational IDs.")
        sys.exit(1)

    logger.info(f"Targeting {len(projects)} projects: {[p['project_id'] for p in projects]}")

    # 3. Iterate and Extract Metadata
    catalog = {
        "metadata_version": "1.0",
        "scanned_projects": [],
        "scan_summary": {
            "total_projects": len(projects),
            "regions_scanned": regions_list
        }
    }

    for p in projects:
        project_id = p["project_id"]
        # Skip if the project ID is empty or invalid
        if not project_id:
            continue
            
        project_data = run_project_extraction(
            project_id=project_id,
            credentials=credentials,
            regions=regions_list,
            max_workers=args.threads
        )
        # Include Resource Manager base project info
        project_data["project_info"] = p
        catalog["scanned_projects"].append(project_data)

    # 4. Save and Export Output
    output_file = args.output
    logger.info(f"Exporting final catalog to: {output_file}")
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2, ensure_ascii=False)
        logger.info("Export completed successfully. Crawler finished.")
    except Exception as e:
        logger.error(f"Failed to write output catalog file {output_file}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
