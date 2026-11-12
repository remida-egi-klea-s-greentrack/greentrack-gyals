# DATA-06/07: deploys the data stack with Terraform and uploads the raw file, which starts the pipeline (bronze -> silver -> gold).

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
        Write-Host "STOPPED: $what failed. See the output above." -ForegroundColor Red
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
$StateMachine = $Out.state_machine_arn.value
$LatestRun = "executions[0].executionArn"

if (-not (Test-Path $RawFile)) {
    Write-Host "STOPPED: raw file not found: $RawFile" -ForegroundColor Red
    exit 1
}
$Before = aws stepfunctions list-executions --state-machine-arn $StateMachine --max-results 1 --query $LatestRun --output text
Check "reading the pipeline runs"

Step "4. Upload the raw file to s3://$BronzeBucket/incoming/ (this starts the pipeline)"
aws s3 cp $RawFile "s3://$BronzeBucket/incoming/household_power_consumption.txt"
Check "upload"

Step "5. Pipeline run (Step Functions: bronze -> silver -> gold)"
$Run = $Before
for ($i = 0; $i -lt 12 -and $Run -eq $Before; $i++) {
    Start-Sleep -Seconds 10
    $Run = aws stepfunctions list-executions --state-machine-arn $StateMachine --max-results 1 --query $LatestRun --output text
}
if ($Run -eq $Before) {
    Write-Host "STOPPED: the upload did not start the pipeline within 2 minutes." -ForegroundColor Red
    exit 1
}
Write-Host "Started: $Run"
$started = Get-Date
do {
    Start-Sleep -Seconds 30
    $state = aws stepfunctions describe-execution --execution-arn $Run --query status --output text
    $mins = [int]((Get-Date) - $started).TotalMinutes
    Write-Host "  pipeline : $state ($mins min)"
} while ($state -eq "RUNNING")

if ($state -ne "SUCCEEDED") {
    $cause = aws stepfunctions describe-execution --execution-arn $Run --query cause --output text
    Write-Host "STOPPED: pipeline ended as $state" -ForegroundColor Red
    Write-Host "Cause: $cause" -ForegroundColor Red
    Write-Host "Details: AWS console -> Step Functions -> $($StateMachine.Split(':')[-1]) -> latest execution" -ForegroundColor Red
    exit 1
}

Step "DONE: pipeline ran on AWS"
Write-Host "Athena: open the Athena console, choose workgroup '$($Out.athena_workgroup.value)', then run e.g."
Write-Host "  SELECT COUNT(*) FROM $($Out.database_names.value.gold).gold_hourly_consumption;"