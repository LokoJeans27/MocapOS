# MocapOS GPU Detector
# Detects NVIDIA GPU series and outputs recommended PyTorch/CUDA version

$OutputFile = $args[0]
if (-not $OutputFile) { $OutputFile = "$env:TEMP\mocapos_gpu_info.txt" }

function Get-GPUInfo {
    try {
        $gpu = Get-WmiObject -Query "SELECT * FROM Win32_VideoController WHERE Name LIKE '%NVIDIA%'" -ErrorAction Stop
        if (-not $gpu) {
            return @{ Found = $false; Error = "No NVIDIA GPU detected" }
        }

        $name = $gpu.Name
        $series = "unknown"
        $cc = "unknown"
        $recommendation = "unknown"

        # Detect series by name patterns
        if ($name -match "RTX\s*50\d{2}") {
            $series = "5000"
            $cc = "10.0/12.0 (Blackwell)"
            $recommendation = "PYTORCH_2_6_CU126"
        }
        elseif ($name -match "RTX\s*40\d{2}") {
            $series = "4000"
            $cc = "8.9 (Ada)"
            $recommendation = "PYTORCH_2_3_CU121"
        }
        elseif ($name -match "RTX\s*30\d{2}") {
            $series = "3000"
            $cc = "8.6 (Ampere)"
            $recommendation = "PYTORCH_2_3_CU121"
        }
        elseif ($name -match "RTX\s*20\d{2}") {
            $series = "2000"
            $cc = "7.5 (Turing)"
            $recommendation = "PYTORCH_2_3_CU121"
        }
        elseif ($name -match "GTX\s*10\d{2}|GT\s*10\d{2}") {
            $series = "1000"
            $cc = "6.1 (Pascal)"
            $recommendation = "PYTORCH_2_3_CU121"
        }
        elseif ($name -match "RTX\s*A\d{4}|A\d{4}\s") {
            $series = "Professional"
            $cc = "8.6+ (Ampere/Ada)"
            $recommendation = "PYTORCH_2_3_CU121"
        }
        elseif ($name -match "Tesla|T4|V100") {
            $series = "Datacenter"
            $cc = "7.0+"
            $recommendation = "PYTORCH_2_3_CU121"
        }
        else {
            $series = "Other NVIDIA"
            $cc = "Unknown"
            $recommendation = "PYTORCH_2_3_CU121"
        }

        return @{
            Found = $true
            Name = $name
            Series = $series
            ComputeCapability = $cc
            Recommendation = $recommendation
        }
    }
    catch {
        return @{ Found = $false; Error = $_.Exception.Message }
    }
}

$info = Get-GPUInfo

# Write output file
$lines = @()
$lines += "GPU_FOUND=$($info.Found)"
$lines += "GPU_NAME=$($info.Name)"
$lines += "GPU_SERIES=$($info.Series)"
$lines += "GPU_CC=$($info.ComputeCapability)"
$lines += "GPU_RECOMMENDATION=$($info.Recommendation)"
if ($info.Error) { $lines += "GPU_ERROR=$($info.Error)" }

$lines | Out-File -FilePath $OutputFile -Encoding UTF8

# Also output to console for Inno Setup to capture
foreach ($line in $lines) { Write-Output $line }
