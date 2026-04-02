# Cortex Windows PATH fix
# Run this once to add Python scripts to PATH so 'cortex' works directly
$scriptsPath = (python -m site --user-scripts)
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($currentPath -notlike "*$scriptsPath*") {
    [Environment]::SetEnvironmentVariable("PATH", "$currentPath;$scriptsPath", "User")
    Write-Host "PATH updated to: $scriptsPath"
    Write-Host "Restart PowerShell then run: cortex init"
} else {
    Write-Host "Already in PATH: $scriptsPath"
    Write-Host "If cortex still not found, restart PowerShell."
}
