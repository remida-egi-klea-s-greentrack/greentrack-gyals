# Update all Lambda functions with new package
$ErrorActionPreference = "Stop"

# Set AWS CLI path
$awsCmd = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
if (-not (Test-Path $awsCmd)) {
    Write-Host "AWS CLI not found at: $awsCmd" -ForegroundColor Red
    exit 1
}

Write-Host "AWS CLI found" -ForegroundColor Green

Write-Host ""
Write-Host "Checking AWS credentials..." -ForegroundColor Cyan
try {
    $identity = & $awsCmd sts get-caller-identity --output json 2>&1 | ConvertFrom-Json
    Write-Host "Logged in as: $($identity.Arn)" -ForegroundColor Green
} catch {
    Write-Host "Not logged in to AWS" -ForegroundColor Red
    Write-Host "Please run: aws sso login" -ForegroundColor Yellow
    exit 1
}

$region = "eu-central-1"
$zipFile = "build/lambda.zip"

if (-not (Test-Path $zipFile)) {
    Write-Host "Lambda package not found: $zipFile" -ForegroundColor Red
    exit 1
}

$zipSize = (Get-Item $zipFile).Length / 1MB
Write-Host "Lambda package size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor Cyan
Write-Host ""

$functions = @(
    "g2-greentrack-production-consumption",
    "g2-greentrack-production-forecast",
    "g2-greentrack-production-anomalies",
    "g2-greentrack-production-chat"
)

Write-Host "Updating Lambda functions..." -ForegroundColor Yellow
Write-Host ""

foreach ($func in $functions) {
    Write-Host "Updating $func..." -ForegroundColor Cyan
    
    try {
        $result = & $awsCmd lambda update-function-code `
            --function-name $func `
            --zip-file "fileb://$zipFile" `
            --region $region `
            --output json 2>&1 | ConvertFrom-Json
        
        Write-Host "  Updated successfully (Version: $($result.Version))" -ForegroundColor Green
        
        Write-Host "  Waiting for function to be ready..." -ForegroundColor Yellow
        & $awsCmd lambda wait function-updated --function-name $func --region $region
        Write-Host "  Function ready" -ForegroundColor Green
        Write-Host ""
        
    } catch {
        Write-Host "  Failed to update: $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "All Lambda functions updated!" -ForegroundColor Green
Write-Host ""
Write-Host "API Gateway URL: https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com" -ForegroundColor White
