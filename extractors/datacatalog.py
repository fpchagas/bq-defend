from google.cloud import datacatalog_v1
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class DataCatalogExtractor(BaseExtractor):
    """
    Extractor for Google Cloud Data Catalog, capturing taxonomies, policy tags,
    tag templates, and applied business tags on data assets.
    """
    def __init__(self, project_id: str, regions: List[str] = None, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.regions = regions or ["us", "eu", "global", "us-central1"]
        self.catalog_client = None
        self.policy_client = None

    def extract(self) -> Dict[str, Any]:
        self.catalog_client = datacatalog_v1.DataCatalogClient(credentials=self.credentials)
        self.policy_client = datacatalog_v1.PolicyTagManagerClient(credentials=self.credentials)
        taxonomies_metadata = []
        tag_templates = []
        applied_tags = []

        # 1. Extract Taxonomies and Policy Tags per Region
        for region in self.regions:
            parent = f"projects/{self.project_id}/locations/{region}"
            try:
                taxonomies = self.policy_client.list_taxonomies(parent=parent)
                for taxonomy in taxonomies:
                    policy_tags = []
                    try:
                        pts = self.policy_client.list_policy_tags(parent=taxonomy.name)
                        for pt in pts:
                            policy_tags.append({
                                "name": pt.name,
                                "display_name": pt.display_name,
                                "description": pt.description,
                                "parent_policy_tag": pt.parent_policy_tag
                            })
                    except Exception as e:
                        self.logger.warning(f"Failed to list policy tags for taxonomy {taxonomy.name}: {e}")
                        policy_tags = [{"error": str(e)}]

                    taxonomies_metadata.append({
                        "name": taxonomy.name,
                        "display_name": taxonomy.display_name,
                        "description": taxonomy.description,
                        "region": region,
                        "policy_tags": policy_tags
                    })
            except Exception as e:
                # Quietly log since not all regions support or have taxonomies
                self.logger.debug(f"Could not list taxonomies in region {region}: {e}")

        # 2. Search catalog to find all Templates and Applied Tags in the project
        try:
            scope = datacatalog_v1.SearchCatalogRequest.Scope()
            scope.include_project_ids.append(self.project_id)

            # Search tag templates
            try:
                request_templates = datacatalog_v1.SearchCatalogRequest(
                    scope=scope,
                    query="type=template"
                )
                for result in self.catalog_client.search_catalog(request=request_templates):
                    tag_templates.append({
                        "relative_resource_name": result.relative_resource_name,
                        "linked_resource": result.linked_resource,
                        "display_name": result.display_name,
                        "description": result.description
                    })
            except Exception as e:
                self.logger.error(f"Error listing tag templates via search: {e}")

            # Search entries in project to find applied tags
            try:
                request_entries = datacatalog_v1.SearchCatalogRequest(
                    scope=scope,
                    query=f"project={self.project_id}"
                )
                for result in self.catalog_client.search_catalog(request=request_entries):
                    entry_tags = []
                    try:
                        tags = self.catalog_client.list_tags(parent=result.relative_resource_name)
                        for tag in tags:
                            fields = {}
                            for field_id, field in tag.fields.items():
                                val = None
                                # Check potential field types
                                if field.bool_value is not None:
                                    val = field.bool_value
                                elif field.double_value is not None:
                                    val = field.double_value
                                elif field.string_value is not None:
                                    val = field.string_value
                                elif field.timestamp_value is not None:
                                    val = field.timestamp_value.isoformat()
                                elif field.enum_value and field.enum_value.display_name:
                                    val = field.enum_value.display_name
                                fields[field_id] = val

                            entry_tags.append({
                                "template": tag.template,
                                "template_display_name": tag.template_display_name,
                                "fields": fields
                            })
                    except Exception as e:
                        # Log debug as some entries might not support tag listing or fail
                        self.logger.debug(f"Failed to list tags for entry {result.relative_resource_name}: {e}")

                    if entry_tags:
                        applied_tags.append({
                            "relative_resource_name": result.relative_resource_name,
                            "linked_resource": result.linked_resource,
                            "display_name": result.display_name,
                            "entry_type": str(result.search_result_type),
                            "tags": entry_tags
                        })
            except Exception as e:
                self.logger.error(f"Error searching entries via search: {e}")

        except Exception as e:
            self.logger.error(f"Error performing search catalog for project {self.project_id}: {e}")

        return {
            "taxonomies": taxonomies_metadata,
            "tag_templates": tag_templates,
            "applied_tags": applied_tags
        }
