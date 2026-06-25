# GCP Enterprise Metadata Catalog Crawler

A production-grade, asynchronous, and modular Python application designed to crawl and extract metadata from virtually the entire Google Cloud Platform (GCP) data ecosystem. It crosses-references these resources with governance metadata (Data Catalog, Dataplex, Datalineage).

## Features

- **Factory & Dependency Injection Architecture**: Each GCP service has its own dedicated, isolated extractor class.
- **High Performance**: Parallelized execution of extraction classes using a thread pool.
- **Robust Error Tolerancy**: Scoped `try/except` execution. Lack of permissions or errors in one service (e.g. Spanner) will not block or crash metadata collection from other services (e.g. BigQuery).
- **Comprehensive GCP Coverage**:
  - **Resource Manager**: Resolves folders, organizations, or individual projects.
  - **BigQuery & Data Transfer**: Datasets, tables, views (with query statements), schema definitions, partition/clustering setup, and data transfer schedules.
  - **Cloud SQL**: Machine tiers, IP configs, database flags, and internal databases (via SQL Admin API).
  - **Spanner**: Instances, databases, and schemas (DDL statements).
  - **Bigtable**: Instances, clusters, tables, and Column Families (with GC rules).
  - **Storage**: Buckets, governance labels, lifecycle rules, and object statistics (safely limited to 1,000 objects per bucket for safety).
  - **Pub/Sub**: Topics, subscription configurations, and linked Pub/Sub schemas.
  - **Data Catalog**: Taxonomies, policy tags, tag templates, and custom business tags applied on assets.
  - **Data Lineage**: Lineage processes, runs, events, and flow link relationships.
  - **Dataplex**: Lakes, Zones, Assets, Data Scan configurations, and detailed results from Data Profiling/Data Quality runs.

---

## Installation & Setup

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Authentication**:
   The crawler relies on Application Default Credentials (ADC). Set up credentials using either:
   - Run `gcloud auth application-default login` on your local workstation.
   - Set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to your service account JSON file:
     ```bash
     export GOOGLE_APPLICATION_CREDENTIALS="/path/to/keyfile.json"
     ```

---

## Executing the Crawler

### Standard Scan (Single Project)
Scan the default project configured in your environment or specify a project directly:
```bash
python main.py --project-id my-gcp-project-123
```

### Scan Under an Organization
Discover and scan all projects under a GCP Organization:
```bash
python main.py --org-id 1234567890
```

### Scan Under a Folder
Discover and scan all projects under a GCP Folder:
```bash
python main.py --folder-id 9876543210
```

### Options & Parameter Reference
- `--project-id`: (Optional) Targets a single GCP project.
- `--org-id`: (Optional) Scopes discovery to projects inside an organization.
- `--folder-id`: (Optional) Scopes discovery to projects inside a folder.
- `--regions`: (Optional) Comma-separated list of GCP regions to crawl for regional resources. Defaults to `us,eu,global,us-central1`.
- `--output`: (Optional) Output filepath. Defaults to `gcp_enterprise_metadata_catalog.json`.
- `--threads`: (Optional) Number of worker threads. Defaults to `8`.

---

## IAM Permissions Required

To run all extractors successfully, the authenticated principal (User or Service Account) should have the following roles (or equivalent custom read permissions):
- **Resource Manager**: `roles/resourcemanager.viewer` (or `browser`)
- **BigQuery**: `roles/bigquery.metadataViewer` and `roles/bigquery.admin` (for Data Transfer listing)
- **Cloud SQL**: `roles/cloudsql.viewer`
- **Spanner**: `roles/spanner.viewer` or `roles/spanner.databaseReader`
- **Bigtable**: `roles/bigtable.viewer`
- **Storage**: `roles/storage.objectViewer`
- **Pub/Sub**: `roles/pubsub.viewer`
- **Data Catalog**: `roles/datacatalog.viewer`
- **Data Lineage**: `roles/lineage.viewer`
- **Dataplex**: `roles/dataplex.viewer`
