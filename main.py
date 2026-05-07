import argparse
import struct
import time
from threading import Thread
import sys

import serial.tools.list_ports
import vgamepad as vg

# Try to import Xbox controller support - try inputs first, then pygame
XBOX_SUPPORT = False
XBOX_LIB = None
pygame = None

try:
    from inputs import get_gamepad
    from inputs import devices as input_devices
    XBOX_SUPPORT = True
    XBOX_LIB = "inputs"
except (ImportError, Exception) as e:
    try:
        import pygame as pygame_module
        pygame = pygame_module
        XBOX_SUPPORT = True
        XBOX_LIB = "pygame"
        input_devices = None
    except (ImportError, Exception) as e2:
        XBOX_SUPPORT = False
        input_devices = None
        print("WARNING: No Xbox controller library found.")
        print("Install one of these to enable Xbox support:")
        print("  pip install inputs")
        print("  pip install pygame")

parser = argparse.ArgumentParser(description='DJI Mavic 3 RC231, RC-N1 + Xbox Controller Support')
parser.add_argument('-p', '--port', help='RC Serial Port')
parser.add_argument('-m', '--mode', help='Input mode: rc (RC-N1 only), xbox (Xbox only), auto (detect available)', 
                    default="auto", choices=['rc', 'xbox', 'auto'])

args = parser.parse_args()
gamepad = vg.VX360Gamepad()
input_mode = args.mode
serial_connected = False
xbox_connected = False
sequence_number = 0x34eb
lt_trigger = 0
rt_trigger = 0

gamepad.reset()
time.sleep(1)

INPUT_POLL_INTERVAL = 0.01
SERIAL_POLL_INTERVAL = 0.1
RETRY_SLEEP_INTERVAL = 1

CRC_TABLE = [
    0x0000, 0x1189, 0x2312, 0x329b, 0x4624, 0x57ad, 0x6536, 0x74bf,
    0x8c48, 0x9dc1, 0xaf5a, 0xbed3, 0xca6c, 0xdbe5, 0xe97e, 0xf8f7,
    0x1081, 0x0108, 0x3393, 0x221a, 0x56a5, 0x472c, 0x75b7, 0x643e,
    0x9cc9, 0x8d40, 0xbfdb, 0xae52, 0xdaed, 0xcb64, 0xf9ff, 0xe876,
    0x2102, 0x308b, 0x0210, 0x1399, 0x6726, 0x76af, 0x4434, 0x55bd,
    0xad4a, 0xbcc3, 0x8e58, 0x9fd1, 0xeb6e, 0xfae7, 0xc87c, 0xd9f5,
    0x3183, 0x200a, 0x1291, 0x0318, 0x77a7, 0x662e, 0x54b5, 0x453c,
    0xbdcb, 0xac42, 0x9ed9, 0x8f50, 0xfbef, 0xea66, 0xd8fd, 0xc974,
    0x4204, 0x538d, 0x6116, 0x709f, 0x0420, 0x15a9, 0x2732, 0x36bb,
    0xce4c, 0xdfc5, 0xed5e, 0xfcd7, 0x8868, 0x99e1, 0xab7a, 0xbaf3,
    0x5285, 0x430c, 0x7197, 0x601e, 0x14a1, 0x0528, 0x37b3, 0x263a,
    0xdecd, 0xcf44, 0xfddf, 0xec56, 0x98e9, 0x8960, 0xbbfb, 0xaa72,
    0x6306, 0x728f, 0x4014, 0x519d, 0x2522, 0x34ab, 0x0630, 0x17b9,
    0xef4e, 0xfec7, 0xcc5c, 0xddd5, 0xa96a, 0xb8e3, 0x8a78, 0x9bf1,
    0x7387, 0x620e, 0x5095, 0x411c, 0x35a3, 0x242a, 0x16b1, 0x0738,
    0xffcf, 0xee46, 0xdcdd, 0xcd54, 0xb9eb, 0xa862, 0x9af9, 0x8b70,
    0x8408, 0x9581, 0xa71a, 0xb693, 0xc22c, 0xd3a5, 0xe13e, 0xf0b7,
    0x0840, 0x19c9, 0x2b52, 0x3adb, 0x4e64, 0x5fed, 0x6d76, 0x7cff,
    0x9489, 0x8500, 0xb79b, 0xa612, 0xd2ad, 0xc324, 0xf1bf, 0xe036,
    0x18c1, 0x0948, 0x3bd3, 0x2a5a, 0x5ee5, 0x4f6c, 0x7df7, 0x6c7e,
    0xa50a, 0xb483, 0x8618, 0x9791, 0xe32e, 0xf2a7, 0xc03c, 0xd1b5,
    0x2942, 0x38cb, 0x0a50, 0x1bd9, 0x6f66, 0x7eef, 0x4c74, 0x5dfd,
    0xb58b, 0xa402, 0x9699, 0x8710, 0xf3af, 0xe226, 0xd0bd, 0xc134,
    0x39c3, 0x284a, 0x1ad1, 0x0b58, 0x7fe7, 0x6e6e, 0x5cf5, 0x4d7c,
    0xc60c, 0xd785, 0xe51e, 0xf497, 0x8028, 0x91a1, 0xa33a, 0xb2b3,
    0x4a44, 0x5bcd, 0x6956, 0x78df, 0x0c60, 0x1de9, 0x2f72, 0x3efb,
    0xd68d, 0xc704, 0xf59f, 0xe416, 0x90a9, 0x8120, 0xb3bb, 0xa232,
    0x5ac5, 0x4b4c, 0x79d7, 0x685e, 0x1ce1, 0x0d68, 0x3ff3, 0x2e7a,
    0xe70e, 0xf687, 0xc41c, 0xd595, 0xa12a, 0xb0a3, 0x8238, 0x93b1,
    0x6b46, 0x7acf, 0x4854, 0x59dd, 0x2d62, 0x3ceb, 0x0e70, 0x1ff9,
    0xf78f, 0xe606, 0xd49d, 0xc514, 0xb1ab, 0xa022, 0x92b9, 0x8330,
    0x7bc7, 0x6a4e, 0x58d5, 0x495c, 0x3de3, 0x2c6a, 0x1ef1, 0x0f78
]

HDR_CRC_TABLE = [
    0x00,0x5E,0xBC,0xE2,0x61,0x3F,0xDD,0x83,0xC2,0x9C,0x7E,0x20,0xA3,0xFD,0x1F,0x41,
    0x9D,0xC3,0x21,0x7F,0xFC,0xA2,0x40,0x1E,0x5F,0x01,0xE3,0xBD,0x3E,0x60,0x82,0xDC,
    0x23,0x7D,0x9F,0xC1,0x42,0x1C,0xFE,0xA0,0xE1,0xBF,0x5D,0x03,0x80,0xDE,0x3C,0x62,
    0xBE,0xE0,0x02,0x5C,0xDF,0x81,0x63,0x3D,0x7C,0x22,0xC0,0x9E,0x1D,0x43,0xA1,0xFF,
    0x46,0x18,0xFA,0xA4,0x27,0x79,0x9B,0xC5,0x84,0xDA,0x38,0x66,0xE5,0xBB,0x59,0x07,
    0xDB,0x85,0x67,0x39,0xBA,0xE4,0x06,0x58,0x19,0x47,0xA5,0xFB,0x78,0x26,0xC4,0x9A,
    0x65,0x3B,0xD9,0x87,0x04,0x5A,0xB8,0xE6,0xA7,0xF9,0x1B,0x45,0xC6,0x98,0x7A,0x24,
    0xF8,0xA6,0x44,0x1A,0x99,0xC7,0x25,0x7B,0x3A,0x64,0x86,0xD8,0x5B,0x05,0xE7,0xB9,
    0x8C,0xD2,0x30,0x6E,0xED,0xB3,0x51,0x0F,0x4E,0x10,0xF2,0xAC,0x2F,0x71,0x93,0xCD,
    0x11,0x4F,0xAD,0xF3,0x70,0x2E,0xCC,0x92,0xD3,0x8D,0x6F,0x31,0xB2,0xEC,0x0E,0x50,
    0xAF,0xF1,0x13,0x4D,0xCE,0x90,0x72,0x2C,0x6D,0x33,0xD1,0x8F,0x0C,0x52,0xB0,0xEE,
    0x32,0x6C,0x8E,0xD0,0x53,0x0D,0xEF,0xB1,0xF0,0xAE,0x4C,0x12,0x91,0xCF,0x2D,0x73,
    0xCA,0x94,0x76,0x28,0xAB,0xF5,0x17,0x49,0x08,0x56,0xB4,0xEA,0x69,0x37,0xD5,0x8B,
    0x57,0x09,0xEB,0xB5,0x36,0x68,0x8A,0xD4,0x95,0xCB,0x29,0x77,0xF4,0xAA,0x48,0x16,
    0xE9,0xB7,0x55,0x0B,0x88,0xD6,0x34,0x6A,0x2B,0x75,0x97,0xC9,0x4A,0x14,0xF6,0xA8,
    0x74,0x2A,0xC8,0x96,0x15,0x4B,0xA9,0xF7,0xB6,0xE8,0x0A,0x54,0xD7,0x89,0x6B,0x35
]

XBOX_AXIS_CODES = {
    "LX": "ABS_X",
    "LY": "ABS_Y",
    "RX": "ABS_RX",
    "RY": "ABS_RY",
    "LT": "ABS_Z",
    "RT": "ABS_RZ",
}

XBOX_AXIS_ALIASES = {
    "LT": {"ABS_Z", "ABS_THROTTLE"},
    "RT": {"ABS_RZ", "ABS_RUDDER"},
}

def calc_checksum(packet, plength):
    # Seeds
    # v = 0x1012 #Naza M
    # v = 0x1013 #Phantom 2
    # v = 0x7000 #Naza M V2
    v = 0x3692  #P3/P4/Mavic 

    for i in range(0, plength):
        vv = v >> 8
        v = vv ^ CRC_TABLE[((packet[i] ^ v) & 0xFF)]
    return v

def calc_pkt55_hdr_checksum(seed, packet, plength):
    chksum = seed
    for i in range(0, plength):
        chksum = HDR_CRC_TABLE[((packet[i] ^ chksum) & 0xFF)]
    return chksum

def detect_inputs_xbox():
    """Detect Xbox-style controllers using the inputs backend."""
    return bool(input_devices and getattr(input_devices, "gamepads", []))

def detect_pygame_xbox():
    """Detect Xbox-style controllers using the pygame backend."""
    if not pygame:
        return False
    pygame.init()
    pygame.joystick.init()
    return pygame.joystick.get_count() > 0

def update_camera_from_triggers():
    """Combine trigger values so RT drives positive and LT drives negative camera actions."""
    global camera
    camera = normalize_xbox_axis(rt_trigger, is_trigger=True) - normalize_xbox_axis(lt_trigger, is_trigger=True)

def send_duml(s, source, target, cmd_type, cmd_set, cmd_id, payload = None):
    global sequence_number
    packet = bytearray.fromhex(u'55')
    length = 13
    if payload is not None:
        length = length + len(payload)

    if length > 0x3ff:
        print("Packet too large")
        exit(1)

    packet += struct.pack('B', length & 0xff)
    packet += struct.pack('B', (length >> 8) | 0x4) # MSB of length and protocol version
    hdr_crc = calc_pkt55_hdr_checksum(0x77, packet, 3)
    packet += struct.pack('B', hdr_crc)
    packet += struct.pack('B', source)
    packet += struct.pack('B', target)
    packet += struct.pack('<H', sequence_number)
    packet += struct.pack('B', cmd_type)
    packet += struct.pack('B', cmd_set)
    packet += struct.pack('B', cmd_id)

    if payload is not None:
        packet += payload

    crc = calc_checksum(packet, len(packet))
    packet += struct.pack('<H',crc)
    s.write(packet)
    #print(' '.join(format(x, '02x') for x in packet))

    sequence_number += 1

print('DJI RC231 Emulator v3.2.0')

# Try to connect to RC-N1 if mode is 'rc' or 'auto'
s = None
if input_mode in ['rc', 'auto']:
    try:
        if args.port:
            print(f"Trying configured port: {args.port}")
            s = serial.Serial(port=args.port, baudrate=115200)
            print(f'✓ Opened serial port: {s.name}')
            serial_connected = True
        else:
            ports = serial.tools.list_ports.comports(True)
            candidate_ports = []

            for port in ports:
                try:
                    if port.description.find("For Protocol") != -1:
                        candidate_ports.append(port.name)
                        print(f"Found RC candidate: {port.name} ({port.description})")
                        s = serial.Serial(port=port.name, baudrate=115200)
                        print(f'✓ Opened serial port: {s.name}')
                        serial_connected = True
                        break
                except (OSError, serial.SerialException):
                    pass

            if not serial_connected:
                if candidate_ports:
                    print("No available RC serial port could be opened.")
                else:
                    print("No RC serial port detected.")
    except serial.SerialException as e:
        print(f'Could not open serial port: {e}')
        if input_mode == 'rc':
            sys.exit(1)

# Check Xbox controller if mode is 'xbox' or 'auto' and Xbox support available
if (input_mode in ['xbox', 'auto'] and XBOX_SUPPORT):
    try:
        if XBOX_LIB == "inputs":
            xbox_connected = detect_inputs_xbox()
        elif XBOX_LIB == "pygame":
            xbox_connected = detect_pygame_xbox()
        
        if xbox_connected:
            print(f"✓ Xbox controller detected (via {XBOX_LIB})")
    except Exception as e:
        print(f"No Xbox controller found: {e}")
        if input_mode == 'xbox':
            sys.exit(1)

# Determine final input mode
if input_mode == 'auto':
    if serial_connected:
        input_mode = 'rc'
        print("\n→ Using RC-N1 as input source\n")
    elif xbox_connected:
        input_mode = 'xbox'
        print("\n→ Using Xbox controller as input source\n")
    else:
        print("\n✗ No input device found (RC-N1 or Xbox controller)")
        sys.exit(1)
elif input_mode == 'rc' and not serial_connected:
    print("\n✗ RC mode selected but RC-N1 not found")
    sys.exit(1)
elif input_mode == 'xbox' and not xbox_connected:
    print("\n✗ Xbox mode selected but Xbox controller not found")
    sys.exit(1)

print('\nEmulator started.')
print('Close terminal to stop.\n')

# Process input (min 364, center 1024, max 1684) -> (min 0, center 16384, max 32768)
def parseInput(input):
    output = (int.from_bytes(input, byteorder='little') - 1024) * 2 * 4096 // 165
    if output >= 32768:
        output = 32767

#    print(output, "test")

    return output

st = {"rh": 0, "rv": 0, "lh": 0, "lv": 0}
camera = 0

def normalize_xbox_axis(value, is_trigger=False):
    """Convert Xbox axis value (-32768 to 32767) to output range (0 to 32768)"""
    if is_trigger:
        # Trigger: 0 to 255 -> 0 to 32768
        return int(value * 128)
    else:
        # Joystick: -32768 to 32767 -> keep as is
        return int(value)

def normalize_trigger_value(value):
    """Map trigger values to 0..255 regardless of driver range."""
    if value < 0:
        value = int((value + 32768) * 255 / 65535)
    return max(0, min(255, int(value)))

def handle_xbox_input():
    """Thread function to read Xbox controller input"""
    global st, camera
    
    if XBOX_LIB == "inputs":
        handle_xbox_input_inputs()
    elif XBOX_LIB == "pygame":
        handle_xbox_input_pygame()
    else:
        print("No Xbox controller library available")

def handle_xbox_input_inputs():
    """Read Xbox input using 'inputs' library"""
    global st, camera, lt_trigger, rt_trigger

    while True:
        try:
            events = get_gamepad()
            for event in events:
                if event.ev_type == 'Absolute':
                    axis_name = None
                    for name, code in XBOX_AXIS_CODES.items():
                        if event.code == code or event.code in XBOX_AXIS_ALIASES.get(name, ()):
                            axis_name = name
                            break

                    if axis_name == "LX":
                        st["lh"] = normalize_xbox_axis(event.state)
                    elif axis_name == "LY":
                        st["lv"] = normalize_xbox_axis(-event.state)
                    elif axis_name == "RX":
                        st["rh"] = normalize_xbox_axis(event.state)
                    elif axis_name == "RY":
                        st["rv"] = normalize_xbox_axis(-event.state)
                    elif axis_name == "LT":
                        lt_trigger = normalize_trigger_value(event.state)
                        update_camera_from_triggers()
                    elif axis_name == "RT":
                        rt_trigger = normalize_trigger_value(event.state)
                        update_camera_from_triggers()
                
                elif event.ev_type == 'Key':
                    pass

            time.sleep(INPUT_POLL_INTERVAL)
        except Exception as e:
            print(f"Xbox input error: {e}")
            time.sleep(RETRY_SLEEP_INTERVAL)

def handle_xbox_input_pygame():
    """Read Xbox input using pygame library"""
    global st, camera, lt_trigger, rt_trigger
    
    pygame.init()
    pygame.joystick.init()
    joystick = None
    last_joystick_name = None
    
    while True:
        try:
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0:
                joystick = None
                last_joystick_name = None
                time.sleep(1)
                continue
            
            if joystick is None:
                joystick = pygame.joystick.Joystick(0)
                joystick.init()
                last_joystick_name = joystick.get_name()
            elif joystick.get_name() != last_joystick_name:
                joystick = pygame.joystick.Joystick(0)
                joystick.init()
                last_joystick_name = joystick.get_name()
            
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    # Axes: 0=LX, 1=LY, 2=RX, 3=RY, 4=LT, 5=RT
                    if event.axis == 0:  # Left X
                        st["lh"] = normalize_xbox_axis(int(event.value * 32767))
                    elif event.axis == 1:  # Left Y
                        st["lv"] = normalize_xbox_axis(int(-event.value * 32767))
                    elif event.axis == 2:  # Right X
                        st["rh"] = normalize_xbox_axis(int(event.value * 32767))
                    elif event.axis == 3:  # Right Y
                        st["rv"] = normalize_xbox_axis(int(-event.value * 32767))
                    elif event.axis == 4:  # Left Trigger
                        lt_trigger = normalize_trigger_value(int((event.value + 1) * 127.5))
                        update_camera_from_triggers()
                    elif event.axis == 5:  # Right Trigger
                        rt_trigger = normalize_trigger_value(int((event.value + 1) * 127.5))
                        update_camera_from_triggers()
                
                elif event.type == pygame.JOYBUTTONDOWN:
                    # Y button = 3, B button = 1
                    if event.button == 3:  # Y
                        gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
                    elif event.button == 1:  # B
                        gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
                
                elif event.type == pygame.JOYBUTTONUP:
                    if event.button == 3:  # Y
                        gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
                    elif event.button == 1:  # B
                        gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
            
            time.sleep(INPUT_POLL_INTERVAL)
        except Exception as e:
            print(f"Xbox input error (pygame): {e}")
            joystick = None
            last_joystick_name = None
            time.sleep(RETRY_SLEEP_INTERVAL)

def threaded_function():
    global st, camera
    while(True):
        time.sleep(SERIAL_POLL_INTERVAL)
        #print("working ...")
        gamepad.left_joystick(int(st["lh"]), int(st["lv"]))
        gamepad.right_joystick(int(st["rh"]), int(st["rv"]))
        if camera > 32000:
            gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y) #restart race
            gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
        elif camera < -32000:
            gamepad.press_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B) #recover drone
            gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
        else:
            gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_Y)
            gamepad.release_button(vg.XUSB_BUTTON.XUSB_GAMEPAD_B)
        gamepad.update()

thread = Thread(target = threaded_function, args = ())
thread.daemon = True
thread.start()

# Start Xbox input thread if needed
xbox_thread = None
if input_mode == 'xbox':
    xbox_thread = Thread(target = handle_xbox_input, args = ())
    xbox_thread.daemon = True
    xbox_thread.start()
    print("Xbox controller thread started\n")
#thread.join()

try:
    if input_mode == 'rc':
        # RC-N1 mode
        print('Mode: RC-N1 emulation\n')
        
        # enable simulator mode for RC (without this stick positions are sent very slow by RC)
        send_duml(s, 0x0a, 0x06, 0x40, 0x06, 0x24, b'\x01')

        while True:
            # read channel values
            send_duml(s, 0x0a, 0x06, 0x40, 0x06, 0x01, bytearray())

            # read duml
            buffer = bytearray()
            while True:
                b = s.read(1)
                if b == b'\x55':
                    buffer.extend(b)
                    ph = s.read(2)
                    buffer.extend(ph)
                    ph = struct.unpack('<H', ph)[0]
                    pl = 0b0000001111111111 & ph
                    pv = 0b1111110000000000 & ph
                    pv = pv >> 10
                    pc = s.read(1)
                    buffer.extend(pc)
                    pd = s.read(pl - 4)
                    buffer.extend(pd)
                    break
                else:
                    break
            data = buffer

            # Reverse-engineered. Controller input seems to always be len 38.
            if len(data) == 38:
                # Reverse-engineered
                st["rh"] = parseInput(data[13:15])
                st["rv"] = parseInput(data[16:18])

                st["lv"] = parseInput(data[19:21])
                st["lh"] = parseInput(data[22:24])

                camera = parseInput(data[25:27])
    
    else:
        # Xbox controller mode
        print('Mode: Xbox controller emulation')
        print('Controller connected and running.\n')
        
        # Just keep the thread running
        while True:
            time.sleep(1)
            
except serial.SerialException as e:
    # Stylistic: Newline to stop data update and spacing.
    print('\n\nCould not read/write:', e)
except KeyboardInterrupt:
    # Stylistic: Newline to stop data update and spacing.
    print('\n\nDetected keyboard interrupt.')
    pass

print('Stopping.')
