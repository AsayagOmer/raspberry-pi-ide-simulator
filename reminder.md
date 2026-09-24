
## YOU MUST READ ME BEFORE EACH TASK

### User Interface

How the GUI is. It follows these notes:

* Start with clear hardware workspace's board, no components
* The hardware workspace's board has a clear graph paper (light-gray squared sheet).
* The hardware workspace's board is a grid.
* In the bottom of the hardware workspace should be the last coordinates of the cursor on the hardware workspace's board.
* In the upper part of the hardware workspace's board should be forward Redo & undo.
* Enable ctrl+z, ctrl+v, ctrl+x, ctrl+c, ctrl+y for the code & hardware workspace.
* There is 2 buttons: "Run Code", "Stop".

### Hardware Components

* Do not change the components, unless I say to change a specific component.
* Make sure that the components are fully Aligned with their physical technical structure (ports, connections, shape, buttons, etc.)
* Each component need to be possible to rotate.
* The component can be connected to another component with matching port (in - for the connected component & out - the coomponent that was connected to).
* The component connected when they are in the same position in space.
* Each component need to be erasable (by pressing delete while the user cursor on the component).
* Supported components:
  * Raspberry Pi 4 MODEL B
  * Pirate Audio: Dual Mic for Raspberry Pi [Pirate Audio: Dual Mic for Raspberry Pi - פייטל](https://piitel.co.il/shop/pirate-audio-dual-mic-for-raspberry-pi/)
  * Mini USB 2.0 external speaker [רמקולי USB מיני - פייטל](https://piitel.co.il/shop/mini-usb-speakers/)

### Logs

* The logs are in a directory called 'logs'.
* Any device that connected or disconnected, will write to the hardware log file (the format: <device_name> is connected/disconnected <what_port>); Only in the log file, we're informed connected/disconnected. __Make sure that only in that log file.__
* Any major event in the UI and major logic event should be written to event log file.

### Tests

* Not included in the GitHub repository.

### Notes

* Push to GitHub after any significant change.
* Do not push to GitHub any personal information (such as: IPs, API keys, environment files, etc.)
* Make sure the gitignore file is up to the date, including only necessary file to run.

---

Please inform me that you read it again; in each answer, by saying: "Omer, I read the reminder as requested".
