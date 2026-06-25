import abc
import logging
from typing import Dict, Any

class BaseExtractor(abc.ABC):
    """
    Base class for all GCP metadata extractors.
    Implements a standardized interface and logging setup.
    """
    def __init__(self, project_id: str, credentials=None):
        self.project_id = project_id
        self.credentials = credentials
        self.logger = logging.getLogger(self.__class__.__name__)

    @abc.abstractmethod
    def extract(self) -> Dict[str, Any]:
        """
        Runs the extraction process for the specific service.
        Must return a dictionary containing the service metadata or any error logs.
        """
        pass

    def run(self) -> Dict[str, Any]:
        """
        A wrapper around extract() with global try-except handling
        to ensure any unexpected extractor failure is gracefully captured.
        """
        try:
            self.logger.info(f"Starting extraction for project {self.project_id}")
            return self.extract()
        except Exception as e:
            self.logger.exception(f"Unhandled exception during extraction for {self.__class__.__name__}: {str(e)}")
            return {
                "error": str(e),
                "status": "FAILED"
            }
