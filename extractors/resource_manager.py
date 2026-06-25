from google.cloud import resourcemanager_v3
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class ResourceManagerExtractor(BaseExtractor):
    """
    Extractor for Resource Manager to discover projects under folder, organization, or search projects.
    """
    def __init__(self, project_id: str = None, org_id: str = None, folder_id: str = None, credentials=None):
        # Resource manager doesn't strictly need a project_id to initialize.
        super().__init__(project_id=project_id or "", credentials=credentials)
        self.org_id = org_id
        self.folder_id = folder_id
        self.client = resourcemanager_v3.ProjectsClient(credentials=self.credentials)

    def extract(self) -> Dict[str, Any]:
        projects = []
        try:
            if self.org_id:
                parent = f"organizations/{self.org_id}"
                self.logger.info(f"Listing projects under Organization: {parent}")
                request = resourcemanager_v3.ListProjectsRequest(parent=parent)
                for project in self.client.list_projects(request=request):
                    projects.append(self._format_project(project))
            elif self.folder_id:
                parent = f"folders/{self.folder_id}"
                self.logger.info(f"Listing projects under Folder: {parent}")
                request = resourcemanager_v3.ListProjectsRequest(parent=parent)
                for project in self.client.list_projects(request=request):
                    projects.append(self._format_project(project))
            elif self.project_id:
                self.logger.info(f"Using single project: {self.project_id}")
                try:
                    project = self.client.get_project(name=f"projects/{self.project_id}")
                    projects.append(self._format_project(project))
                except Exception as e:
                    self.logger.warning(f"Failed to fetch metadata for project {self.project_id}: {e}. Adding with ID only.")
                    projects.append({
                        "project_id": self.project_id,
                        "name": self.project_id,
                        "project_number": None,
                        "state": "UNKNOWN",
                        "create_time": None,
                        "labels": {},
                        "status": "ACCESSIBLE_BUT_NO_RM_PERMISSIONS"
                    })
            else:
                self.logger.info("Searching all projects accessible by current credentials...")
                request = resourcemanager_v3.SearchProjectsRequest()
                for project in self.client.search_projects(request=request):
                    projects.append(self._format_project(project))
        except Exception as e:
            self.logger.error(f"Error in ResourceManagerExtractor: {e}")
            if self.project_id:
                # If we couldn't list projects, fallback to single project dict if it is set.
                projects = [{
                    "project_id": self.project_id,
                    "name": self.project_id,
                    "project_number": None,
                    "state": "UNKNOWN",
                    "create_time": None,
                    "labels": {},
                    "status": "FALLBACK_PROJECT"
                }]
            else:
                raise e

        return {"projects": projects}

    def _format_project(self, project) -> Dict[str, Any]:
        return {
            "project_id": project.project_id,
            "name": project.display_name,
            "project_number": project.name.split("/")[-1] if project.name else None,
            "state": str(project.state),
            "create_time": project.create_time.isoformat() if project.create_time else None,
            "labels": dict(project.labels) if project.labels else {}
        }
