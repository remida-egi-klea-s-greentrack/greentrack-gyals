# Update Lambda functions via S3 (for large packages)
$ErrorActionPreference = "Stop"

$awsCmd = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$region = "eu-central-1"
$zipFile = "build/lambda.zip"
$s3Bucket = "g2-greentrack-tfstate-886565871385"
$s3Key = "lambda-packages/lambda.zip"

Write-Host "AWS Lambda Update via S3" -ForegroundColor Cyan
Write-Host ""

# Check ZIP exists
if (-not (Test-Path $zipFile)) {
    Write-Host "Lambda package not found: $zipFile" -ForegroundColor Red
    exit 1
}

$zipSize = (Get-Item $zipFile).Length / 1MB
Write-Host "Lambda package size: $([math]::Round($zipSize, 2)) MB" -ForegroundColor White
Write-Host "Note: Package is too large for direct upload, using S3" -ForegroundColor Yellow
Write-Host ""

# Upload to S3
Write-Host "Uploading to S3..." -ForegroundColor Cyan
Write-Host "Bucket: $s3Bucket" -ForegroundColor White
Write-Host "Key: $s3Key" -ForegroundColor White
Write-Host ""

try {
    & $awsCmd s3 cp $zipFile "s3://$s3Bucket/$s3Key" --region $region
    Write-Host "Upload complete" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "Failed to upload to S3: $_" -ForegroundColor Red
    exit 1
}

# Update Lambda functions
$functions = @(
    "g2-greentrack-production-consumption",
    "g2-greentrack-production-forecast",
    "g2-greentrack-production-anomalies",
    "g2-greentrack-production-chat"
)

Write-Host "Updating Lambda functions from S3..." -ForegroundColor Yellow
Write-Host ""

foreach ($func in $functions) {
    Write-Host "Updating $func..." -ForegroundColor Cyan
    
    try {
        $output = & $awsCmd lambda update-function-code `
            --function-name $func `
            --s3-bucket $s3Bucket `
            --s3-key $s3Key `
            --region $region `
            --output json 2>&1
        
        if ($LASTEXITCODE -eq 0) {
            $result = $output | ConvertFrom-Json
            Write-Host "  Updated successfully (Version: $($result.Version))" -ForegroundColor Green
            
            Write-Host "  Waiting for function to be ready..." -ForegroundColor Yellow
            & $awsCmd lambda wait function-updated --function-name $func --region $region 2>&1 | Out-Null
            Write-Host "  Function ready" -ForegroundColor Green
        } else {
            Write-Host "  Failed: $output" -ForegroundColor Red
        }
        Write-Host ""
        
    } catch {
        Write-Host "  Failed to update: $_" -ForegroundColor Red
        Write-Host ""
    }
}

Write-Host "All Lambda functions updated!" -ForegroundColor Green
Write-Host ""
Write-Host "API Gateway URL: https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com" -ForegroundColor White
