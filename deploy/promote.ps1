<#
Move Alice's traffic to the newest revision (after the pipeline has deployed it with no traffic), or back.
  .\deploy\promote.ps1 -SubscriptionId <id>              newest revision of alice-web and alice-mcp gets 100%
  .\deploy\promote.ps1 -SubscriptionId <id> -Rollback    the previous revision gets 100% again
  .\deploy\promote.ps1 -SubscriptionId <id> -Status      just show what is live
Check the new revision first if you like: in the portal, open alice-web > Revisions and use its own URL.
#>
param(
  [Parameter(Mandatory = $true)][string]$SubscriptionId,
  [string]$ResourceGroup = 'alice-rg',
  [switch]$Rollback,
  [switch]$Status
)
$ErrorActionPreference = 'Stop'
az account set --subscription $SubscriptionId
foreach ($app in @('alice-web', 'alice-mcp')) {
  $revs = az containerapp revision list -n $app -g $ResourceGroup --query "sort_by([?properties.active], &properties.createdTime)[].{name:name, traffic:properties.trafficWeight, health:properties.healthState, created:properties.createdTime}" -o json | ConvertFrom-Json
  Write-Host "`n$app"
  $revs | ForEach-Object { Write-Host ("  {0,-34} traffic {1,3}%  {2,-10} {3}" -f $_.name, $_.traffic, $_.health, $_.created) }
  if ($Status -or $revs.Count -eq 0) { continue }
  $target = if ($Rollback) { if ($revs.Count -lt 2) { Write-Host '  Nothing to roll back to.'; continue }; $revs[$revs.Count - 2].name } else { $revs[$revs.Count - 1].name }
  $pick = $revs | Where-Object { $_.name -eq $target }
  if (-not $Rollback -and $pick.health -ne 'Healthy') { Write-Host "  $target is $($pick.health), not Healthy: left as it is." -ForegroundColor Yellow; continue }
  az containerapp ingress traffic set -n $app -g $ResourceGroup --revision-weight "$target=100" -o none
  Write-Host "  Live: $target" -ForegroundColor Green
}
