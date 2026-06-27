<#
.SYNOPSIS
    Checks for a newer PowerShell release and updates PowerShell when available.
.DESCRIPTION
    Compares the current PowerShell version with the latest stable release from
    the PowerShell GitHub repository. If an update is available, this script
    updates PowerShell using winget.
.PARAMETER CheckOnly
    Only reports whether an update is available. Does not install anything.
.PARAMETER Force
    Runs winget even when the current version appears to be up to date.
.EXAMPLE
    .\Update-PowerShell.ps1
.EXAMPLE
    .\Update-PowerShell.ps1 -CheckOnly
.EXAMPLE
    .\Update-PowerShell.ps1 -Force
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$CheckOnly,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$packageId = 'Microsoft.PowerShell'
$releaseApiUrl = 'https://api.github.com/repos/PowerShell/PowerShell/releases/latest'

function Get-LatestPowerShellVersion {
    $headers = @{
        Accept = 'application/vnd.github+json'
        'User-Agent' = 'Update-PowerShell.ps1'
    }

    $release = Invoke-RestMethod -Uri $releaseApiUrl -Headers $headers
    $tagName = [string]$release.tag_name

    if ([string]::IsNullOrWhiteSpace($tagName)) {
        throw 'GitHub release response did not include a tag name.'
    }

    [version]($tagName.TrimStart('v'))
}

function Assert-WingetAvailable {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget was not found. Install App Installer from the Microsoft Store, then run this script again.'
    }
}

$currentVersion = [version]$PSVersionTable.PSVersion.ToString()
$latestVersion = Get-LatestPowerShellVersion
$updateAvailable = $latestVersion -gt $currentVersion

Write-Host "Current PowerShell version: $currentVersion"
Write-Host "Latest PowerShell version:  $latestVersion"

if (-not $updateAvailable -and -not $Force) {
    Write-Host 'PowerShell is already up to date.'
    exit 0
}

if ($CheckOnly) {
    if ($updateAvailable) {
        Write-Host 'A PowerShell update is available.'
    }
    else {
        Write-Host 'No PowerShell update is required, but -Force would run winget anyway.'
    }

    exit 0
}

Assert-WingetAvailable

if ($PSCmdlet.ShouldProcess($packageId, "Upgrade to PowerShell $latestVersion using winget")) {
    winget upgrade `
        --id $packageId `
        --exact `
        --source winget `
        --accept-package-agreements `
        --accept-source-agreements

    if ($LASTEXITCODE -ne 0) {
        throw "winget upgrade failed with exit code $LASTEXITCODE."
    }

    Write-Host 'PowerShell update completed. Restart your terminal to use the updated version.'
}
