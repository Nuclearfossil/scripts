<#
.SYNOPSIS
    Recursively deletes a directory.
.DESCRIPTION
    Deletes the folder at the given path, including all files and subdirectories.
.EXAMPLE
    rmd .\build
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Path
)

$item = Get-Item -LiteralPath $Path -ErrorAction Stop

if (-not $item.PSIsContainer) {
    throw "Path is not a directory: $Path"
}

$resolvedPath = $item.FullName
$rootPath = [System.IO.Path]::GetPathRoot($resolvedPath)

if ($resolvedPath.TrimEnd('\') -eq $rootPath.TrimEnd('\')) {
    throw "Refusing to remove a filesystem root: $resolvedPath"
}

$folderName = $item.Name
Write-Host "Are you sure you want to delete $folderName? Yes or No? " -NoNewline
$confirmation = [System.Console]::ReadKey($true)
Write-Host $confirmation.KeyChar

if ($confirmation.KeyChar -eq 'Y') {
    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
}
