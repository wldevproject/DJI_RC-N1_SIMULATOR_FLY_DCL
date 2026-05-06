# DJI RC-N1 & Xbox Controller Simulator Emulator

Fork of the original project:
https://github.com/IvanYaky/DJI_RC-N1_SIMULATOR_FLY_DCL

This fork adds support for controllers beyond DJI RC-N1, including Xbox-style gamepads.

For donations and the original project, please visit the creator above.
This fork is only a personal/open-source modification of their work.
---

Latest version V3.1.0 (2025)

- ✨ Added Xbox 360/One/Series X|S Controller support
- ✨ Added GUI Controller Tester tool
- 🔄 Dual input mode: DJI RC-N1 or Xbox Controller
- 🎯 Auto-detection of connected input devices
- ✅ Backward compatible with previous versions
- 🐛 critical fix, com port open error on some PC's

---

- 🎮 Connect your DJI Remote Controller **OR** Xbox Controller to your PC and use it to play simulators
- ✅ Confirmed: DJI Mavic 3 RC231, Xbox 360 Controller for Windows
- 🔀 Support for other DJI models: [justin97530/miniDjiController](https://github.com/justin97530/miniDjiController)
- 🔀 DJI Mini 2: [usatenko/DjiMini2RCasJoystick](https://github.com/usatenko/DjiMini2RCasJoystick)
- 🔀 DJI Phantom 3: [mishavoloshchuk/mDjiController](https://github.com/mishavoloshchuk/mDjiController)

---

## What is this?

This program connects either:

1. **DJI Mavic 3 Remote Controller (RC-N1)** - as a USB serial input device
2. **Xbox Controller (360/One/Series)** - as a USB gamepad input

Both are emulated as **Xbox 360 gamepad** for Windows, allowing you to use either controller with flight simulators like DCL - The Game.

<img height="400" src="DJI-RC-N1-Remote-Controller.png" width="400"/>

---

## Installation

### Prerequisites

- Python 3.9 or later
- Windows PC

### Setup

1. **Install required packages:**

```bash
pip install vgamepad pyserial inputs pygame
```

`inputs` is used first for Xbox controller detection. If your device behaves better with `pygame`, the app can fall back to that path.

2. **For DJI RC-N1 only:**
   - Download and install [DJI Assistant 2](https://www.dji.com/downloads/softwares/dji-assistant-2-consumer-drones-series)
   - Close DJI Assistant 2 after installation (driver will remain)

## Usage

### Mode 1: DJI RC-N1 Controller

```bash
# Auto-detect RC-N1 (if connected via USB Type-C)
python main.py

# Or specify serial port explicitly
python main.py -p COM9
```

### Mode 2: Xbox Controller (360/One/Series)

```bash
# Use Xbox controller directly
python main.py -m xbox
```

### Mode 3: Auto-detect (Default)

```bash
# Automatically detect and use whichever is connected
python main.py -m auto
```

### Batch Files (Windows)

- **start.bat** - Run in RC-N1 mode
- **test_controller.bat** - Open GUI Controller Tester

## Features

### 🎯 DJI RC-N1 Mode

- Read stick positions from RC-N1 via USB serial
- Camera wheel controls (scroll up/down for restart/recover)
- Simulator mode for fast response
- Support for DJI Mavic 3 RC-N1 and RC231

### 🎮 Xbox Controller Mode

- Support for Xbox 360, Xbox One, Xbox Series X|S
- Works with both standard sticks and hall effect-style controllers as long as Windows exposes them as an Xbox/XInput gamepad
- Full analog stick and trigger support
- All digital buttons (A/B/X/Y/LB/RB)
- Automatic connection detection

### 🧪 GUI Controller Tester

- Real-time visualization of all controller inputs
- Live analog stick and trigger values
- Digital button status display
- Connection status indicator
- Great for testing and debugging

Run with: `python test_controller_gui.py` or `test_controller.bat`

![](Xbox-Controller-Tester.png)

---

## TROUBLESHOOTING

**RC-N1 Connection Issues:**

- App automatically searches for serial port with "DJI USB VCOM For Protocol"
- Make sure your device is attached via **bottom Type-C connector**
  ![](connect_ok.png)

**Xbox Controller Not Detected:**

- Ensure controller is plugged in via USB or wirelessly connected
- Check Windows Game Controller settings (Control Panel)
- Try the GUI Tester to verify connection
- If one controller model reports slightly different axis/button codes, the tester and runtime now use broader Xbox mappings
- Install both Xbox input backends if needed: `pip install inputs pygame`

**Controller input not working in game:**

- Make sure game is configured for Xbox 360 gamepad input
- Test using the GUI Controller Tester first
- If a controller is recognized in the tester but not in-game, check the axis direction and trigger behavior in `test_controller_gui.py`

**Serial Port Error on RC-N1:**

- Reinstall DJI Assistant 2 drivers
- Try a different USB port
- Check Device Manager for "DJI USB" devices

[Tested with DCL - The game](https://store.steampowered.com/app/964570/DCL__The_Game/)

    Preset:
    Mode 2
    Acro
    Zero throttle at stick center

![](preset1.png)
![](preset2.png)
