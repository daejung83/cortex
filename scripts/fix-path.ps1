# Cortex Windows PATH fix
# Run this once to add Python scripts to PATH so 'cortex' works directly

$scriptsPath = python -m site --user-scripts
$currentPath = [Environment]::GetEnvironmentVariable("PATH", "User")

if ($currentPath.Contains($scriptsPath)) {
    Write-Host "Already in PATH: $scriptsPath"
    Write-Host "If cortex still not found, restart PowerShell."
} else {
    $newPath = $currentPath + ";" + $scriptsPath
    [Environment]::SetEnvironmentVariable("PATH", $newPath, "User")
    Write-Host "PATH updated. Added: $scriptsPath"
    Write-Host "Restart PowerShell then run: cortex init"
}
