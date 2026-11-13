# Energy-saving advice (Challenge 4): Bedrock Knowledge Base on Amazon S3 Vectors.
# The guidance documents in genai/knowledge_base/docs are uploaded to the artifacts bucket, embedded with
# Titan Text Embeddings V2 and stored in an S3 Vectors index; the assistant reads them with Retrieve.
# Variables used: var.name_prefix, var.artifacts_bucket_arn, var.embedding_model_id.
# Locals: document folder and S3 prefix, artifacts bucket name, embedding size, hash of the documents
# (a change starts a new ingestion job).

locals {
  kb_docs_dir       = "${path.module}/../../../genai/knowledge_base/docs"
  kb_docs           = fileset(local.kb_docs_dir, "*")
  kb_prefix         = "knowledge-base/energy-guidance/"
  artifacts_bucket  = split(":::", var.artifacts_bucket_arn)[1]
  kb_dimensions     = 1024
  kb_embedding_arn  = "arn:aws:bedrock:${local.region}::foundation-model/${var.embedding_model_id}"
  kb_documents_hash = sha256(join("", [for f in sort(tolist(local.kb_docs)) : filesha256("${local.kb_docs_dir}/${f}")]))
}

# ---------- Documents (each .md has a .metadata.json with its title and source URL) ----------

resource "aws_s3_object" "kb_document" {
  for_each = local.kb_docs

  bucket       = local.artifacts_bucket
  key          = "${local.kb_prefix}${each.value}"
  source       = "${local.kb_docs_dir}/${each.value}"
  etag         = filemd5("${local.kb_docs_dir}/${each.value}")
  content_type = endswith(each.value, ".json") ? "application/json" : "text/markdown"
}

# ---------- Vector store ----------

resource "aws_s3vectors_vector_bucket" "kb" {
  vector_bucket_name = "${var.name_prefix}-kb-vectors"
  force_destroy      = true
}

resource "aws_s3vectors_index" "kb" {
  index_name         = "${var.name_prefix}-energy-guidance"
  vector_bucket_name = aws_s3vectors_vector_bucket.kb.vector_bucket_name
  data_type          = "float32"
  dimension          = local.kb_dimensions
  distance_metric    = "cosine"

  # Bedrock stores the chunk text and its own metadata under these keys; they must be non-filterable,
  # otherwise ingestion fails on the 2 KB filterable-metadata limit.
  metadata_configuration {
    non_filterable_metadata_keys = ["AMAZON_BEDROCK_TEXT", "AMAZON_BEDROCK_METADATA"]
  }
}

# ---------- Knowledge Base role ----------

data "aws_iam_policy_document" "kb_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "kb" {
  name               = "${var.name_prefix}-knowledge-base"
  assume_role_policy = data.aws_iam_policy_document.kb_assume.json
}

data "aws_iam_policy_document" "kb" {
  statement {
    sid       = "Embeddings"
    actions   = ["bedrock:InvokeModel"]
    resources = [local.kb_embedding_arn]
  }

  statement {
    sid       = "ListDocuments"
    actions   = ["s3:ListBucket"]
    resources = [var.artifacts_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${local.kb_prefix}*"]
    }
  }

  statement {
    sid       = "ReadDocuments"
    actions   = ["s3:GetObject"]
    resources = ["${var.artifacts_bucket_arn}/${local.kb_prefix}*"]
  }

  statement {
    sid = "VectorIndex"
    actions = [
      "s3vectors:GetIndex", "s3vectors:QueryVectors", "s3vectors:PutVectors",
      "s3vectors:GetVectors", "s3vectors:DeleteVectors", "s3vectors:ListVectors",
    ]
    resources = [aws_s3vectors_index.kb.index_arn]
  }
}

resource "aws_iam_role_policy" "kb" {
  name   = "${var.name_prefix}-knowledge-base"
  role   = aws_iam_role.kb.id
  policy = data.aws_iam_policy_document.kb.json
}

# ---------- Knowledge Base and data source ----------

resource "aws_bedrockagent_knowledge_base" "energy" {
  name        = "${var.name_prefix}-energy-guidance"
  description = "Energy-saving guidance cited by the GreenTrack assistant"
  role_arn    = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"

    vector_knowledge_base_configuration {
      embedding_model_arn = local.kb_embedding_arn

      embedding_model_configuration {
        bedrock_embedding_model_configuration {
          dimensions          = local.kb_dimensions
          embedding_data_type = "FLOAT32"
        }
      }
    }
  }

  storage_configuration {
    type = "S3_VECTORS"

    s3_vectors_configuration {
      index_arn = aws_s3vectors_index.kb.index_arn
    }
  }

  depends_on = [aws_iam_role_policy.kb]
}

resource "aws_bedrockagent_data_source" "energy" {
  name              = "${var.name_prefix}-energy-guidance-docs"
  knowledge_base_id = aws_bedrockagent_knowledge_base.energy.id

  data_source_configuration {
    type = "S3"

    s3_configuration {
      bucket_arn         = var.artifacts_bucket_arn
      inclusion_prefixes = [local.kb_prefix]
    }
  }

  # Each document is short (about 200 words), so one document is one chunk and one citation.
  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "NONE"
    }
  }
}

# Terraform creates the data source but does not sync it. This starts an ingestion job after the first
# apply and whenever a document changes (needs the AWS CLI and the same credentials as terraform).
resource "terraform_data" "kb_ingestion" {
  triggers_replace = [local.kb_documents_hash, aws_bedrockagent_data_source.energy.data_source_id]

  provisioner "local-exec" {
    command = "aws bedrock-agent start-ingestion-job --region ${local.region} --knowledge-base-id ${aws_bedrockagent_knowledge_base.energy.id} --data-source-id ${aws_bedrockagent_data_source.energy.data_source_id}"
  }

  depends_on = [aws_s3_object.kb_document]
}
