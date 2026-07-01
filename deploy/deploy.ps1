# One-time AWS setup + first deploy (PowerShell)
# Requires: aws cli, npm — and `aws login` already done

param(
    [string]$Region = "us-east-1",
    [string]$StackName = "factory-qa",
    [string]$DbHost = "",
    [string]$DbPassword = "change-me",
    [string]$JwtSecret = "change-me-in-production"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "==> Resolving default VPC subnets..."
$vpc = aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text --region $Region
$subnets = aws ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" "Name=default-for-az,Values=true" --query "Subnets[*].SubnetId" --output text --region $Region
$subnetIds = ($subnets -split "\s+") | Where-Object { $_ }

if (-not $DbHost) {
    Write-Host "WARNING: No -DbHost. Create RDS PostgreSQL first, then re-run with -DbHost your-rds-endpoint"
    $DbHost = "127.0.0.1"
}

Write-Host "==> Deploying CloudFormation stack..."
$paramOverrides = @(
    "ProjectName=factory-qa",
    "VpcId=$vpc",
    "DbHost=$DbHost",
    "DbPassword=$DbPassword",
    "JwtSecretKey=$JwtSecret"
)
foreach ($sid in $subnetIds) { $paramOverrides += "SubnetIds=$sid" }

aws cloudformation deploy `
    --template-file deploy/stack.yaml `
    --stack-name $StackName `
    --parameter-overrides $paramOverrides `
    --capabilities CAPABILITY_NAMED_IAM `
    --region $Region

Write-Host "==> Reading stack outputs..."
$outputs = aws cloudformation describe-stacks --stack-name $StackName --region $Region --query "Stacks[0].Outputs" --output json | ConvertFrom-Json
$apiUrl = ($outputs | Where-Object { $_.OutputKey -eq "ApiUrl" }).OutputValue
$bucket = ($outputs | Where-Object { $_.OutputKey -eq "FrontendBucketName" }).OutputValue
$cfUrl = ($outputs | Where-Object { $_.OutputKey -eq "CloudFrontUrl" }).OutputValue
$cfId = ($outputs | Where-Object { $_.OutputKey -eq "CloudFrontDistributionId" }).OutputValue

Write-Host "==> Building frontend (API -> $apiUrl)..."
Push-Location frontend
$env:VITE_API_URL = $apiUrl
npm ci --silent
npm run build
Pop-Location

Write-Host "==> Uploading frontend to S3..."
aws s3 sync frontend/dist/ "s3://$bucket/" --delete --region $Region
aws cloudfront create-invalidation --distribution-id $cfId --paths "/*" --region $Region | Out-Null

Write-Host ""
Write-Host "Done."
Write-Host "  API:      $apiUrl"
Write-Host "  Frontend: $cfUrl"
Write-Host ""
Write-Host "Next: deploy the backend separately to ECS/RDS and set CORS_ORIGINS on the API to $cfUrl"
