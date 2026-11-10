"""Names and tags for the SageMaker resources these scripts create in the shared DataMax account.

The challenge requires every resource to carry the group prefix and tags. Terraform's default_tags
do not reach resources created with boto3, so the scripts add them from here.

Variables:
    NAME_PREFIX - group prefix shared by all g2 resources (same as Terraform's name_prefix)
    TAGS        - tags attached to training jobs, models, endpoint configs and endpoints
"""

import time

NAME_PREFIX = "g2-greentrack"
TAGS = [
    {"Key": "Project", "Value": "greentrack"},
    {"Key": "Group", "Value": "g2"},
    {"Key": "ManagedBy", "Value": "script"},
]


def resource_name(kind):
    """Unique prefixed name for one run, e.g. g2-greentrack-rcf-20261110-050102."""
    return f"{NAME_PREFIX}-{kind}-{time.strftime('%Y%m%d-%H%M%S')}"
