from google.cloud import pubsub_v1
from extractors.base import BaseExtractor
from typing import Dict, Any, List

class PubSubExtractor(BaseExtractor):
    """
    Extractor for Pub/Sub Topics, Subscriptions, and schemas linked to topics.
    """
    def __init__(self, project_id: str, credentials=None):
        super().__init__(project_id=project_id, credentials=credentials)
        self.publisher_client = pubsub_v1.PublisherClient(credentials=self.credentials)
        self.subscriber_client = pubsub_v1.SubscriberClient(credentials=self.credentials)

    def extract(self) -> Dict[str, Any]:
        topics_metadata = []
        subscriptions_metadata = []
        project_path = f"projects/{self.project_id}"

        # 1. Extract Topics
        try:
            topics = self.publisher_client.list_topics(project=project_path)
            for topic in topics:
                schema_settings = None
                if topic.schema_settings:
                    schema_settings = {
                        "schema": topic.schema_settings.schema,
                        "encoding": str(topic.schema_settings.encoding)
                    }
                topics_metadata.append({
                    "name": topic.name.split("/")[-1] if "/" in topic.name else topic.name,
                    "full_name": topic.name,
                    "kms_key_name": topic.kms_key_name,
                    "schema_settings": schema_settings,
                    "labels": dict(topic.labels) if topic.labels else {}
                })
        except Exception as e:
            self.logger.error(f"Error listing Pub/Sub topics: {e}")
            topics_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

        # 2. Extract Subscriptions
        try:
            subscriptions = self.subscriber_client.list_subscriptions(project=project_path)
            for sub in subscriptions:
                push_config = None
                if sub.push_config and sub.push_config.push_endpoint:
                    push_config = {
                        "push_endpoint": sub.push_config.push_endpoint,
                        "attributes": dict(sub.push_config.attributes) if sub.push_config.attributes else {}
                    }

                dead_letter_policy = None
                if sub.dead_letter_policy and sub.dead_letter_policy.dead_letter_topic:
                    dead_letter_policy = {
                        "dead_letter_topic": sub.dead_letter_policy.dead_letter_topic,
                        "max_delivery_attempts": sub.dead_letter_policy.max_delivery_attempts
                    }

                subscriptions_metadata.append({
                    "name": sub.name.split("/")[-1] if "/" in sub.name else sub.name,
                    "full_name": sub.name,
                    "topic": sub.topic,
                    "ack_deadline_seconds": sub.ack_deadline_seconds,
                    "retain_acked_messages": sub.retain_acked_messages,
                    "message_retention_duration": sub.message_retention_duration.seconds if sub.message_retention_duration else None,
                    "push_config": push_config,
                    "dead_letter_policy": dead_letter_policy,
                    "labels": dict(sub.labels) if sub.labels else {}
                })
        except Exception as e:
            self.logger.error(f"Error listing Pub/Sub subscriptions: {e}")
            subscriptions_metadata = [{"error": str(e), "status": "PERMISSION_DENIED_OR_FAILED"}]

        return {
            "topics": topics_metadata,
            "subscriptions": subscriptions_metadata
        }
