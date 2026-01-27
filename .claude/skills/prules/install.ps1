# prules skill installation script for Windows PowerShell
# Usage: .\install.ps1 -TargetProject "D:\path\to\project"

param(
    [Parameter(Mandatory=$true)]
    [string]$TargetProject
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SkillName = "prules"
$SourceDir = $PSScriptRoot
$TargetDir = Join-Path $TargetProject ".claude\skills\$SkillName"

Write-Host "Installing prules skill..." -ForegroundColor Cyan
Write-Host "Source: $SourceDir"
Write-Host "Target: $TargetDir"
Write-Host ""

# Create target directory
$SkillsDir = Join-Path $TargetProject ".claude\skills"
if (-not (Test-Path $SkillsDir)) {
    New-Item -ItemType Directory -Path $SkillsDir -Force | Out-Null
}

# Check if target already exists
if (Test-Path $TargetDir) {
    Write-Host "WARNING: Target already exists: $TargetDir" -ForegroundColor Yellow
    $response = Read-Host "Overwrite? (y/N)"
    if ($response -ne "y" -and $response -ne "Y") {
        Write-Host "Installation cancelled" -ForegroundColor Red
        exit 1
    }
    Remove-Item -Path $TargetDir -Recurse -Force
}

# Ask for installation method
Write-Host ""
Write-Host "Choose installation method:"
Write-Host "1) Copy files (independent copy)"
Write-Host "2) Create symbolic link (shared updates, requires admin)"
$choice = Read-Host "Select (1/2)"

if ($choice -eq "1") {
    # Copy files
    Copy-Item -Path $SourceDir -Destination $TargetDir -Recurse
    Write-Host "SUCCESS: Copied prules skill to: $TargetDir" -ForegroundColor Green
}
elseif ($choice -eq "2") {
    # Create symbolic link (requires admin privileges)
    try {
        New-Item -ItemType SymbolicLink -Path $TargetDir -Target $SourceDir -Force | Out-Null
        Write-Host "SUCCESS: Created symbolic link: $TargetDir -> $SourceDir" -ForegroundColor Green
    }
    catch {
        Write-Host "ERROR: Failed to create symbolic link (may need admin privileges)" -ForegroundColor Red
        Write-Host "Please run PowerShell as Administrator, or choose copy method" -ForegroundColor Yellow
        exit 1
    }
}
else {
    Write-Host "ERROR: Invalid choice" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Installation complete!" -ForegroundColor Green
Write-Host ""
Write-Host "You can now use /prules command in the target project"
