# VM Server & Simulator Setup Instructions

These instructions explain how to connect a local Raspberry Pi Simulator (running on your home PC) to a FastAPI server running on a university Linux VM (via Omnissa Horizon), without using a VPN.

## 1. Start the Server on the VM
1. Log into your university's **Omnissa Horizon** portal and open your Linux VM.
2. Open a terminal inside the Linux desktop.
3. Install the required Python packages (if you haven't already):
   ```bash
   sudo apt update
   sudo apt install python3-pip python3-venv -y
   python3 -m venv .venv
   source .venv/bin/activate
   pip install fastapi uvicorn python-multipart
   ```
4. Start the server on port 8000:
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```
*(Leave this terminal window open so the server keeps running!)*

## 2. Create the Public Tunnel (Pinggy)
Because the university firewall blocks direct outside connections to the VM, we use a reverse tunnel to expose it to the internet safely.

1. Open a **second, new terminal window** inside your Horizon Linux VM.
2. Run this exact command to create the tunnel:
   ```bash
   ssh -p 443 -R0:localhost:8000 a.pinggy.io
   ```
3. Type `yes` if it asks you to confirm the connection.
4. The terminal will output a couple of public URLs (e.g., `https://qahza-...run.pinggy-free.link`).
5. **Copy one of these URLs.**

## 3. Configure the Simulator on your Home PC
1. On your home Windows PC, open the simulator workspace.
2. Open the `elderly_assistant_sim.py` file.
3. Replace the `SERVER_URL` on line 4 with the public URL you copied from Pinggy. 
   **Important:** Do NOT include `:8000` or a trailing slash at the end of the URL.
   ```python
   SERVER_URL = "https://qahza-your-unique-id.run.pinggy-free.link"
   ```

## 4. Run the Code!
1. Start your simulator IDE: `python main.py`
2. Add the **Raspberry Pi 4**, **Pirate Audio (Mic)**, and **Mini USB Speaker** to the workspace and ensure they are connected.
3. Click **📂 Open File** and select `elderly_assistant_sim.py`.
4. Click **▶ Run Code**.
5. Press the **A** button on the simulated Pirate Audio screen.

Your local PC will record audio, tunnel it securely across the internet straight into your Horizon VM, and the VM will save it as `server_received.wav`!
