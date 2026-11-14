# PowerShell helper to build and run the Raspberry Pi IDE simulator in a Docker container
# ------------------------------------------------------------
# This script works on Windows without Docker Desktop.
# It uses WSL2 (Ubuntu) and the Docker engine package installed inside WSL.
# The container is given access to the host audio device (/dev/snd) so that
# microphone recording works, and DISPLAY is forwarded to an X server (VcXsrv).
# ------------------------------------------------------------

# 1. Verify WSL2 Ubuntu is installed
$wslList = [System.Text.Encoding]::Unicode.GetString((wsl.exe -l -q 2>&1 | %{[System.Text.Encoding]::Default.GetBytes($_)}))
if (-not ($wslList -match "Ubuntu")) {
    Write-Host "Ubuntu not found in WSL. Installing Ubuntu..."
    wsl --install -d Ubuntu
    Write-Host "Please reboot your machine and re-run this script."
    exit 1
}

# 2. Ensure Docker engine is available inside WSL natively (ignoring Windows Docker Desktop stubs)
$dockerCheck = wsl -e bash -c "dpkg -l | grep docker.io || true"
if (-not $dockerCheck) {
    Write-Host "Docker not found in WSL. Installing docker.io..."
    wsl -u root -- apt-get update -y
    wsl -u root -- apt-get install -y docker.io
    # Start the daemon for the current session
    wsl -u root -- service docker start
} else {
    # Start the daemon if not already running
    wsl -u root -- service docker start
}

# 3. Build the Docker image (uses the Dockerfile in the repo)
Write-Host "Building Docker image pi-ide-sim ..."
wsl -u root -- /usr/bin/docker build -t pi-ide-sim .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed! Exiting."
    exit $LASTEXITCODE
}

# 4. Extract native WSLg DISPLAY and run the container with GUI and audio forwarding
$WSL_DISPLAY = wsl -e bash -c "echo `$DISPLAY"
$WSL_WAYLAND = wsl -e bash -c "echo `$WAYLAND_DISPLAY"
$WSL_PWD = (wsl -e bash -c "pwd").Trim()

if ([string]::IsNullOrWhiteSpace($WSL_DISPLAY)) {
    $WSL_DISPLAY = ":0"
}

Write-Host "Launching simulator container via WSLg (Display: $WSL_DISPLAY)..."
# -v "${WSL_PWD}:/app" mounts the project inside the container
# --device /dev/snd forwards the sound device for recording (if natively available)
wsl -u root -- /usr/bin/docker run --rm `
    -e DISPLAY=$WSL_DISPLAY `
    -e WAYLAND_DISPLAY=$WSL_WAYLAND `
    -e PULSE_SERVER=/mnt/wslg/PulseServer `
    -e SDL_AUDIODRIVER=pulseaudio `
    -v /tmp/.X11-unix:/tmp/.X11-unix `
    -v /mnt/wslg:/mnt/wslg `
    -v "${WSL_PWD}:/app" `
    --network host `
    pi-ide-sim
