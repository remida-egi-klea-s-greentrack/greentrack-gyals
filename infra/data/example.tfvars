# Example values; copy to <env>.tfvars.

region      = "eu-central-1"
name_prefix = "g2-greentrack"
environment = "datamax"

# Lake Formation (see infra/modules/data/lakeformation.tf)
enforce_gold           = false
analyst_principal_arns = ["arn:aws:iam::<ACCOUNT_ID>:role/aws-reserved/sso.amazonaws.com/<REGION>/<SSO_ROLE_NAME>"]
