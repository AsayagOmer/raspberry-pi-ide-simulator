# PowerShell helper to build and run the Raspberry Pi IDE simulator in a Docker container
# ------------------------------------------------------------
# This script works on Windows without Docker Desktop.
# It uses WSL2 (Ubuntu) and the Docker engine package installed inside WSL.
# The container is given access to the host audio device (/dev/snd) so that
# microphone recording works, and DISPLAY is forwarded to an X server (VcXsrv).
# ------------------------------------------------------------

# 1. Verify WSL2 Ubuntu is installed
if (-not (wsl -l -v | Select-String "Ubuntu")) {
    Write-Host "Ubuntu not found in WSL. Installing Ubuntu..."
    wsl --install -d Ubuntu
    Write-Host "Please reboot your machine and re‑run this script."
    exit 1
}

# 2. Ensure Docker engine is available inside WSL
$dockerCheck = wsl -e bash -c "which docker || true"
if (-not $dockerCheck) {
    Write-Host "Docker not found in WSL. Installing docker.io..."
    wsl -e sudo apt-get update -y
    wsl -e sudo apt-get install -y docker.io
    # Start the daemon for the current session
    wsl -e sudo service docker start
} else {
    # Start the daemon if not already running
    wsl -e sudo service docker start
}

# 3. Build the Docker image (uses the Dockerfile in the repo)
Write-Host "Building Docker image pi-ide-sim ..."
wsl -e docker build -t pi-ide-sim .

# 4. Run the container with GUI and audio forwarding
# Ensure an X server (VcXsrv or Xming) is running on the host.
if (-not $env:DISPLAY) {
    Write-Host "DISPLAY variable not set. Setting to localhost:0.0"
    $env:DISPLAY = "localhost:0.0"
}

$NetworkMode = "host"
if ($args -contains "--offline") {
    $NetworkMode = "none"
}

Write-Host "Launching simulator container (Network: $NetworkMode)..."
# -v "${PWD}:/app:ro" mounts the project read‑only inside the container
# --device /dev/snd forwards the sound device for recording
wsl -e docker run --rm `
    -e DISPLAY=$env:DISPLAY `
    -v "${PWD}:/app:ro" `
    --network $NetworkMode `
    --device /dev/snd `
    pi-ide-sim
