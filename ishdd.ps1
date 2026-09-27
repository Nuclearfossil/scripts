<#
.SYNOPSIS
    Lists logical drives and their associated disk details.
.DESCRIPTION
    Retrieves all partitions with drive letters, resolves each drive to its underlying
    disk, and shows the drive letter, disk model, and media type in a table.
.EXAMPLE
    .\ishdd.ps1
    Displays the current mounted drives and their disk information.
#>

[CmdletBinding()]
param()

Get-Partition |
  Where-Object DriveLetter |
  ForEach-Object {
    $disk = $_ | Get-Disk
    $physical = Get-PhysicalDisk | Where-Object DeviceId -eq $disk.Number
    [PSCustomObject]@{
      Drive = "$($_.DriveLetter):"
      Model = $disk.FriendlyName
      Type  = $physical.MediaType
    }
  } | Format-Table -AutoSize