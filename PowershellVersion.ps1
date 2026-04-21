<#
.SYNOPSIS
    Gets the version of PowerShell running in the current session.
.DESCRIPTION
    Retrieves the PSVersion property from the global $PSVersionTable variable.
.EXAMPLE
    .\GetPowerShellVersion.ps1
#>

$PSVersionTable.PSVersion
