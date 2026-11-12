# GitHub Actions -> AWS me OIDC (APP-07 / APP-08), pa access keys në GitHub.
#
# Dy role:
#   - <prefix>-github-plan    : PR-të, vetëm lexim (terraform plan -lock=false)
#   - <prefix>-github-deploy  : main + environments production/e2e, apply + deploy frontend
#
# OIDC provider-i ekziston tashmë në llogarinë e përbashkët (përdoret edhe nga grupet e tjera),
# prandaj lexohet me data source dhe NUK krijohet/menaxhohet këtu.

data "aws_caller_identity" "current" {}

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = var.aws_region
  subs       = var.github_sub_prefixes

  fn_arns = [for p in var.managed_prefixes : "arn:aws:lambda:${local.region}:${local.account_id}:function:${p}-*"]
  table_arns = flatten([for p in var.managed_prefixes : [
    "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${p}-*",
    "arn:aws:dynamodb:${local.region}:${local.account_id}:table/${p}-*/*",
  ]])
  role_arns    = [for p in var.managed_prefixes : "arn:aws:iam::${local.account_id}:role/${p}-*"]
  policy_arns  = [for p in var.managed_prefixes : "arn:aws:iam::${local.account_id}:policy/${p}-*"]
  bucket_arns  = [for p in var.managed_prefixes : "arn:aws:s3:::${p}-frontend-*"]
  object_arns  = [for p in var.managed_prefixes : "arn:aws:s3:::${p}-frontend-*/*"]
  assistant    = "arn:aws:lambda:${local.region}:${local.account_id}:function:${var.assistant_function_name}"
  apigw_arns   = ["arn:aws:apigateway:${local.region}::/apis", "arn:aws:apigateway:${local.region}::/apis/*", "arn:aws:apigateway:${local.region}::/tags/*"]
  state_bucket = "arn:aws:s3:::${var.state_bucket}"
}

# ---------------------------------------------------------------------------
# Trust policies
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "trust_plan" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values   = flatten([for s in local.subs : ["${s}:pull_request", "${s}:ref:refs/heads/*"]])
    }
  }
}

data "aws_iam_policy_document" "trust_deploy" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [data.aws_iam_openid_connect_provider.github.arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    # Vetëm jobs me environment production/e2e (environment vendos sub-in) ose main.
    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = flatten([for s in local.subs : [
        "${s}:environment:production",
        "${s}:environment:e2e",
        "${s}:ref:refs/heads/main",
      ]])
    }
  }
}

# ---------------------------------------------------------------------------
# Plan role: lexim i metadata-ve të stack-ut + state (pa lock, pa shkrim)
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "plan" {
  statement {
    sid       = "StateRead"
    actions   = ["s3:ListBucket", "s3:GetObject"]
    resources = [local.state_bucket, "${local.state_bucket}/greentrack/*"]
  }

  statement {
    sid = "DescribeStack"
    actions = [
      "lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:GetPolicy",
      "lambda:ListVersionsByFunction", "lambda:GetFunctionCodeSigningConfig", "lambda:ListTags",
      "dynamodb:DescribeTable", "dynamodb:DescribeContinuousBackups", "dynamodb:DescribeTimeToLive",
      "dynamodb:ListTagsOfResource",
      "iam:GetRole", "iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListAttachedRolePolicies",
      "iam:ListRolePolicies", "iam:ListPolicyVersions", "iam:ListInstanceProfilesForRole",
      "cloudfront:GetDistribution", "cloudfront:GetOriginAccessControl", "cloudfront:ListTagsForResource",
      "s3:GetBucket*", "s3:GetAccelerateConfiguration", "s3:GetLifecycleConfiguration",
      "s3:GetReplicationConfiguration", "s3:GetEncryptionConfiguration", "s3:ListBucket",
      "apigateway:GET",
      "sts:GetCallerIdentity",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "plan" {
  name                 = "${var.name_prefix}-github-plan"
  description          = "GitHub Actions (PR) - terraform plan, read-only"
  assume_role_policy   = data.aws_iam_policy_document.trust_plan.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "plan" {
  name   = "terraform-plan-readonly"
  role   = aws_iam_role.plan.id
  policy = data.aws_iam_policy_document.plan.json
}

# ---------------------------------------------------------------------------
# Deploy role: menaxhon vetëm burimet me prefiksin e app stack (production/e2e)
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "deploy" {
  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket"]
    resources = [local.state_bucket]
  }

  # Vetëm state-i i app stack (production + e2e), jo state-i i këtij stack-u OIDC.
  statement {
    sid     = "StateReadWrite"
    actions = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = [
      "${local.state_bucket}/greentrack/terraform.tfstate",
      "${local.state_bucket}/greentrack/terraform.tfstate.tflock",
      "${local.state_bucket}/greentrack/e2e.tfstate",
      "${local.state_bucket}/greentrack/e2e.tfstate.tflock",
    ]
  }

  statement {
    sid       = "Lambda"
    actions   = ["lambda:*"]
    resources = local.fn_arns
  }

  statement {
    sid = "AssistantChatPermissionOnly"
    actions = [
      "lambda:GetFunction", "lambda:GetFunctionConfiguration", "lambda:GetPolicy",
      "lambda:ListVersionsByFunction", "lambda:GetFunctionCodeSigningConfig", "lambda:ListTags",
      "lambda:AddPermission", "lambda:RemovePermission",
    ]
    resources = [local.assistant]
  }

  statement {
    sid       = "DynamoDB"
    actions   = ["dynamodb:*"]
    resources = local.table_arns
  }

  statement {
    sid       = "ApiGateway"
    actions   = ["apigateway:GET", "apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE", "apigateway:TagResource", "apigateway:UntagResource"]
    resources = local.apigw_arns
  }

  statement {
    sid = "IamForStackRolesAndPolicies"
    actions = [
      "iam:GetRole", "iam:CreateRole", "iam:DeleteRole", "iam:UpdateRole", "iam:UpdateAssumeRolePolicy",
      "iam:TagRole", "iam:UntagRole", "iam:ListAttachedRolePolicies", "iam:ListRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:GetPolicy", "iam:GetPolicyVersion", "iam:ListPolicyVersions", "iam:CreatePolicy",
      "iam:DeletePolicy", "iam:CreatePolicyVersion", "iam:DeletePolicyVersion", "iam:TagPolicy", "iam:UntagPolicy",
      "iam:ListPolicyTags", "iam:ListRoleTags",
    ]
    resources = concat(local.role_arns, local.policy_arns)
  }

  # Lambda role mund të lidhet me menaxhuar AWSLambdaBasicExecutionRole
  statement {
    sid       = "AttachLambdaBasicExecution"
    actions   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
    resources = local.role_arns
    condition {
      test     = "ArnEquals"
      variable = "iam:PolicyARN"
      values = concat(
        ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
        local.policy_arns,
      )
    }
  }

  statement {
    sid       = "PassLambdaRole"
    actions   = ["iam:PassRole"]
    resources = local.role_arns
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com"]
    }
  }

  statement {
    sid       = "FrontendBuckets"
    actions   = ["s3:*"]
    resources = concat(local.bucket_arns, local.object_arns)
  }

  # CloudFront nuk lejon kufizim sipas emrit në create; menaxhohet vetëm distribucioni i frontend-it.
  statement {
    sid = "CloudFront"
    actions = [
      "cloudfront:GetDistribution", "cloudfront:GetDistributionConfig", "cloudfront:CreateDistribution",
      "cloudfront:UpdateDistribution", "cloudfront:DeleteDistribution", "cloudfront:TagResource",
      "cloudfront:UntagResource", "cloudfront:ListTagsForResource", "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation", "cloudfront:GetOriginAccessControl", "cloudfront:CreateOriginAccessControl",
      "cloudfront:UpdateOriginAccessControl", "cloudfront:DeleteOriginAccessControl",
      "cloudfront:ListOriginAccessControls",
    ]
    resources = ["*"]
  }

  statement {
    sid       = "Identity"
    actions   = ["sts:GetCallerIdentity"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.name_prefix}-github-deploy"
  description          = "GitHub Actions (main/production/e2e) - terraform apply + frontend deploy"
  assume_role_policy   = data.aws_iam_policy_document.trust_deploy.json
  max_session_duration = 3600
}

resource "aws_iam_role_policy" "deploy" {
  name   = "terraform-apply-app-stack"
  role   = aws_iam_role.deploy.id
  policy = data.aws_iam_policy_document.deploy.json
}
