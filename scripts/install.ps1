# Installs the latest Cowppuccin theme release for the Beef IDE.
#
# Usage:
#   irm https://raw.githubusercontent.com/RogueMacro/cowppuccin/main/scripts/install.ps1 | iex

& {
    $ErrorActionPreference = 'Stop'
    $ProgressPreference = 'SilentlyContinue' # Invoke-WebRequest is very slow with the progress bar on PS 5.1

    $repo = 'RogueMacro/cowppuccin'
    $assetName = 'theme.zip'
    $downloadUrl = "https://github.com/$repo/releases/latest/download/$assetName"

    if ([string]::IsNullOrWhiteSpace($env:BEEFPATH)) {
        Write-Host 'BEEFPATH environment variable is not set. Is the Beef IDE installed?' -ForegroundColor Red
        return
    }
    if (-not (Test-Path -LiteralPath $env:BEEFPATH -PathType Container)) {
        Write-Host "BEEFPATH points to '$env:BEEFPATH', which does not exist." -ForegroundColor Red
        return
    }

    $themesDir = Join-Path $env:BEEFPATH 'bin\themes'
    $installDir = Join-Path $themesDir 'Cowppuccin'
    $zipPath = Join-Path ([System.IO.Path]::GetTempPath()) ("cowppuccin-" + [guid]::NewGuid().ToString('N') + '.zip')

    # GitHub requires TLS 1.2; older Windows PowerShell may not enable it by default.
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    try {
        Write-Host "Downloading $downloadUrl ..."
        Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing

        # Creates themes\ and Cowppuccin\ as needed.
        New-Item -ItemType Directory -Path $installDir -Force | Out-Null

        Write-Host "Extracting to $installDir ..."
        Expand-Archive -LiteralPath $zipPath -DestinationPath $installDir -Force

        Write-Host "Cowppuccin installed to $installDir" -ForegroundColor Green
    }
    catch {
        Write-Host "Installation failed: $($_.Exception.Message)" -ForegroundColor Red
    }
    finally {
        if (Test-Path -LiteralPath $zipPath) {
            Remove-Item -LiteralPath $zipPath -Force -ErrorAction SilentlyContinue
        }
    }
}
