<#
Runs the outstanding Azure changes in one go, and can be left running:
  1. commit and push the changed files (the GitHub pipeline then tests them)
  2. build the new image in Azure from the committed code
  3. update alice-web and alice-mcp: new image, your es3cloud account allowed, alice.northants.it kept
  4. let the GitHub pipeline deploy (prints 5 values for you to paste into GitHub in the morning)
It stops at the first problem and says which step. Everything is written to a log in your user folder.
Run from D:\AISubstrate:   .\deploy\run-all.ps1
#>
param(
  [string]$SubscriptionId = '02120be9-a2b2-46e6-ab0e-0eb4c372421f',
  [string]$ExtAppId = '0f003e20-693d-4148-b609-a122e5ed29e3',
  [string]$ExtCallers = '04b07795-8ddb-461a-bbee-02f9e1bf7b46=Azure CLI test:copilot',
  [string]$AlsoAllow = 'stefan.oconnor@es3cloud.com',
  [string]$CustomDomain = 'alice.northants.it',
  [string]$GitHubRepo = 'stefanjoc-ux/Alice',
  [string]$GitHubSubject = 'repo:stefanjoc-ux@336622755/Alice@1403454494:environment:production'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$Setup = Join-Path $PSScriptRoot 'azure-setup.ps1'
$Log = Join-Path $env:USERPROFILE ('alice-run-' + (Get-Date -Format 'yyyyMMdd-HHmm') + '.log')
Start-Transcript -Path $Log | Out-Null
$step = ''
try {
  $step = '1/4 commit and push'
  Write-Host "`n== $step" -ForegroundColor Cyan
  # Named files only: never .env or data\ (also ignored by git), and not the .cmd files whose line endings differ.
  $files = @('apps.py', 'mileage.py', 'actions.py', 'app.py', 'admin_ui.py', 'CLAUDE.md', 'temple_ask.py', 'mcp_server.py',
             'rules_engine.py', 'tests/test_apps.py', 'deploy/azure-setup.ps1', 'deploy/run-all.ps1', 'infra/main.bicep')
  & git add -- $files; if ($LASTEXITCODE -ne 0) { throw 'git add failed.' }
  & git diff --cached --quiet
  if ($LASTEXITCODE -ne 0) {
    & git commit -m 'Apps area; Saved chats and Knowledge summaries names; scrolling menu; custom domain and second sign-in account'
    if ($LASTEXITCODE -ne 0) { throw 'git commit failed.' }
  } else { Write-Host 'Nothing new to commit.' }
  & git push; if ($LASTEXITCODE -ne 0) { throw 'git push failed.' }

  $step = '2/4 image'
  Write-Host "`n== $step" -ForegroundColor Cyan
  & $Setup -SubscriptionId $SubscriptionId -Step image

  $step = '3/4 apps'
  Write-Host "`n== $step" -ForegroundColor Cyan
  & $Setup -SubscriptionId $SubscriptionId -Step apps -ExtAppId $ExtAppId -ExtCallers $ExtCallers -AlsoAllow $AlsoAllow -CustomDomain $CustomDomain

  $step = '4/4 GitHub pipeline sign-in'
  Write-Host "`n== $step" -ForegroundColor Cyan
  & $Setup -SubscriptionId $SubscriptionId -Step github -GitHubRepo $GitHubRepo -GitHubSubject $GitHubSubject

  Write-Host "`nAll four steps finished. Alice: https://$CustomDomain  (paste the 5 GitHub values above into the repo)." -ForegroundColor Green
}
catch {
  Write-Host "`nStopped at step $step : $_" -ForegroundColor Red
  Write-Host 'Nothing after this step ran. Send Claude this screen (or the log) in the morning; every step is safe to run again.' -ForegroundColor Yellow
}
finally {
  Stop-Transcript | Out-Null
  Write-Host "Log: $Log"
}
