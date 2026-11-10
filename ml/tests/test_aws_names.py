"""Tests for the shared-account names and tags used by the SageMaker scripts.

Variables: none beyond the imported NAME_PREFIX, TAGS and resource_name.
"""

from ml.sagemaker.aws_names import NAME_PREFIX, TAGS, resource_name


def test_names_carry_group_prefix_and_fit_sagemaker_limit():
    name = resource_name("xgboost")

    assert name.startswith(f"{NAME_PREFIX}-xgboost-")
    assert len(name) <= 63  # SageMaker job and endpoint name limit


def test_tags_identify_the_group():
    tags = {tag["Key"]: tag["Value"] for tag in TAGS}

    assert tags["Group"] == "g2"
    assert tags["Project"] == "greentrack"
