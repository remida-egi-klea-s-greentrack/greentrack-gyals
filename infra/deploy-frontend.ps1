# Deploy frontend to S3 and invalidate CloudFront cache
$ErrorActionPreference = "Stop"

$awsCmd = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
$region = "eu-central-1"
$bucket = "g2-greentrack-production-frontend-886565871385"
$distributionId = "E3JZRO92L8GFNV"
$distPath = "..\app\frontend\dist"

Write-Host "Deploying GreenTrack Frontend" -ForegroundColor Cyan
Write-Host ""

# Check if dist exists
if (-not (Test-Path $distPath)) {
    Write-Host "Build directory not found: $distPath" -ForegroundColor Red
    Write-Host "Please run: npm run build in app/frontend" -ForegroundColor Yellow
    exit 1
}

Write-Host "S3 Bucket: $bucket" -ForegroundColor White
Write-Host "CloudFront Distribution: $distributionId" -ForegroundColor White
Write-Host ""

# Upload to S3
Write-Host "Uploading files to S3..." -ForegroundColor Cyan
try {
    & $awsCmd s3 sync $distPath "s3://$bucket/" `
        --region $region `
        --delete `
        --cache-control "public, max-age=31536000" `
        --exclude "*.html" 2>&1 | Out-Host
    
    # Upload HTML with different cache settings
    & $awsCmd s3 sync $distPath "s3://$bucket/" `
        --region $region `
        --exclude "*" `
        --include "*.html" `
        --cache-control "public, max-age=0, must-revalidate" 2>&1 | Out-Host
    
    Write-Host "Upload complete" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "Failed to upload to S3: $_" -ForegroundColor Red
    exit 1
}

# Invalidate CloudFront cache
Write-Host "Invalidating CloudFront cache..." -ForegroundColor Cyan
try {
    $invalidation = & $awsCmd cloudfront create-invalidation `
        --distribution-id $distributionId `
        --paths "/*" `
        --output json 2>&1 | ConvertFrom-Json
    
    Write-Host "Invalidation created: $($invalidation.Invalidation.Id)" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "Warning: Failed to invalidate CloudFront: $_" -ForegroundColor Yellow
    Write-Host "Cache will expire naturally" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "Frontend deployment complete!" -ForegroundColor Green
Write-Host ""
Write-Host "URLs:" -ForegroundColor Cyan
Write-Host "  CloudFront: https://d2qotsi80vpuyc.cloudfront.net" -ForegroundColor White
Write-Host "  API: https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com" -ForegroundColor White
