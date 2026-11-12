# Test API endpoints
$ErrorActionPreference = "Continue"

$apiUrl = "https://5tto05ko0e.execute-api.eu-central-1.amazonaws.com"

Write-Host "Testing GreenTrack API Endpoints" -ForegroundColor Cyan
Write-Host "API URL: $apiUrl" -ForegroundColor White
Write-Host ""

# Test 1: Consumption endpoint
Write-Host "1. Testing /consumption endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$apiUrl/consumption" -Method GET -UseBasicParsing
    Write-Host "   Status: $($response.StatusCode)" -ForegroundColor Green
    $data = $response.Content | ConvertFrom-Json
    Write-Host "   Records returned: $($data.data.Count)" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 2: Forecast endpoint
Write-Host "2. Testing /forecast endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$apiUrl/forecast" -Method GET -UseBasicParsing
    Write-Host "   Status: $($response.StatusCode)" -ForegroundColor Green
    $data = $response.Content | ConvertFrom-Json
    Write-Host "   Forecast points: $($data.predictions.Count)" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 3: Anomalies endpoint
Write-Host "3. Testing /anomalies endpoint..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "$apiUrl/anomalies" -Method GET -UseBasicParsing
    Write-Host "   Status: $($response.StatusCode)" -ForegroundColor Green
    $data = $response.Content | ConvertFrom-Json
    Write-Host "   Anomalies found: $($data.anomalies.Count)" -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 4: Chat endpoint
Write-Host "4. Testing /chat endpoint..." -ForegroundColor Yellow
$body = @{
    message = "What is my current energy consumption?"
} | ConvertTo-Json

try {
    $response = Invoke-WebRequest -Uri "$apiUrl/chat" -Method POST -Body $body -ContentType "application/json" -UseBasicParsing
    Write-Host "   Status: $($response.StatusCode)" -ForegroundColor Green
    $data = $response.Content | ConvertFrom-Json
    Write-Host "   Response received: $($data.response.Substring(0, [Math]::Min(50, $data.response.Length)))..." -ForegroundColor Green
} catch {
    Write-Host "   Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "API testing complete!" -ForegroundColor Cyan
