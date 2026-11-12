# DATA-06: deploys the data stack with Terraform and runs the Glue jobs (bronze -> silver -> gold).
# Usage: powershell -ExecutionPolicy Bypass -File infra/data/deploy.ps1 [-SkipInfra]

param(
    [switch]$SkipInfra,
    [string]$AwsProfile = "greentrack",
    [string]$Environment = "datamax"
)

$ErrorActionPreference = "Continue"
$env:AWS_PROFILE = $AwsProfile
$Repo = (Resolve-Path "$PSScriptRoot/../..").Path
$RawFile = Join-Path $Repo "data/raw/household_power_consumption.txt"

function Step($text) { Write-Host "`n===== $text =====" -ForegroundColor Cyan }
function Check($what) {
    if ($LASTEXITCODE -ne 0) {
        Write-Host "STOPPED: $what failed. Copy the output above and ask for help." -ForegroundColor Red
        exit 1
    }
}

Step "1. AWS login"
$Account = aws sts get-caller-identity --query Account --output text
Check "AWS login (run: aws sso login --profile $AwsProfile)"
Write-Host "Account: $Account"
$StateBucket = "g2-greentrack-tfstate-$Account"
aws s3api head-bucket --bucket $StateBucket 2>&1 | Out-Null
Check "finding the state bucket $StateBucket"

Push-Location $PSScriptRoot
try {
    # Settings files (git-ignored): created once from the examples.
    $TfVars = "$Environment.tfvars"
    $Backend = "$Environment.backend.hcl"
    if (-not (Test-Path $TfVars)) { Copy-Item example.tfvars $TfVars }
    if (-not (Test-Path $Backend)) {
        (Get-Content example.backend.hcl) -replace "<ACCOUNT_ID>", $Account |
            Set-Content -Encoding ascii $Backend
    }

    Step "2. Terraform init (state: s3://$StateBucket/data/terraform.tfstate)"
    terraform init -input=false -backend-config="$Backend"
    Check "terraform init"

    if (-not $SkipInfra) {
        Step "3. Terraform: create buckets, Glue databases, Glue jobs, Athena"
        terraform fmt -recursive ..
        terraform validate
        Check "terraform validate"
        Write-Host "Terraform shows the plan below and asks to confirm. Type yes to create." -ForegroundColor Yellow
        terraform apply -var-file="$TfVars"
        Check "terraform apply"
    }

    $Out = (terraform output -json) -join "`n" | ConvertFrom-Json
    Check "terraform output"
} finally {
    Pop-Location
}

$BronzeBucket = $Out.bucket_names.value.bronze
$Jobs = $Out.glue_job_names.value

Step "4. Upload the raw file to s3://$BronzeBucket/incoming/"
if (-not (Test-Path $RawFile)) {
    Write-Host "STOPPED: raw file not found: $RawFile" -ForegroundColor Red
    exit 1
}
aws s3 cp $RawFile "s3://$BronzeBucket/incoming/household_power_consumption.txt"
Check "upload"

foreach ($step in @("bronze", "silver", "gold")) {
    $job = $Jobs.$step
    Step "5. Glue job: $job"
    $runId = aws glue start-job-run --job-name $job --query JobRunId --output text
    Check "starting $job"
    $started = Get-Date
    do {
        Start-Sleep -Seconds 30
        $state = aws glue get-job-run --job-name $job --run-id $runId --query JobRun.JobRunState --output text
        $mins = [int]((Get-Date) - $started).TotalMinutes
        Write-Host "  $job : $state ($mins min)"
    } while ($state -in @("STARTING", "RUNNING", "STOPPING", "WAITING"))

    if ($state -ne "SUCCEEDED") {
        $msg = aws glue get-job-run --job-name $job --run-id $runId --query JobRun.ErrorMessage --output text
        Write-Host "STOPPED: $job ended as $state" -ForegroundColor Red
        Write-Host "Error: $msg" -ForegroundColor Red
        Write-Host "Full log: AWS console -> Glue -> ETL jobs -> $job -> Runs -> $runId" -ForegroundColor Red
        exit 1
    }
}

Step "DONE: pipeline ran on AWS"
Write-Host "Athena: open the Athena console, choose workgroup '$($Out.athena_workgroup.value)', then run e.g."
Write-Host "  SELECT COUNT(*) FROM $($Out.database_names.value.gold).gold_hourly_consumption;"