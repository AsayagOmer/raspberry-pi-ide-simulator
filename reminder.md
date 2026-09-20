
## YOU MUST READ ME BEFORE EACH TASK!

### User Interface

How the GUI is. It follows these notes:

* Start with clear board, no components
* Enable ctrl+z, ctrl+v, ctrl+x, ctrl+c, ctrl+y for the code
* There is 2 buttons: "Run Code", "Stop".

### Hardware Components

* Do not change the components, unless I say to change a specific component.
* Make sure that the components are fully Aligned with their physical technical structure (ports, connections, shape, buttons, etc.)
* Each component need to be possible to rotate.
* Each component need to be erasable (by pressing delete while the user cursor on the component).
* Supported components:
  * Raspberry Pi 4 MODEL B
  * Pirate Audio: Dual Mic for Raspberry Pi [Pirate Audio: Dual Mic for Raspberry Pi - פייטל](https://piitel.co.il/shop/pirate-audio-dual-mic-for-raspberry-pi/)
  * Mini USB 2.0 external speaker [רמקולי USB מיני - פייטל](https://piitel.co.il/shop/mini-usb-speakers/)

### Logs

* Any device that connected or disconnected, will write to the hardware log file (the format: <device_name> is connected/disconnected <what_port>); Only in the log file, we're informed connected/disconnected. __Make sure that only in that log file.__
* Any major event in the UI and major logic event should be written to event log file.

### Notes

* Push to GitHub after any significant change.
* Make sure the gitignore file is up to the date, including only necessary file to run.

---

Please inform me that you read it, say: "Omer, I read the reminder as requested".
