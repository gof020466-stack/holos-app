$WshShell = New-Object -ComObject WScript.Shell
$Lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Голос.lnk'
$Shortcut = $WshShell.CreateShortcut($Lnk)
$Shortcut.TargetPath = Join-Path $PSScriptRoot 'start.bat'
$Shortcut.WorkingDirectory = $PSScriptRoot
$Shortcut.WindowStyle = 7
$Shortcut.Description = "Голос — голосовой ввод без интернета"
$Shortcut.Save()

Write-Host "Shortcut created: $Lnk"
