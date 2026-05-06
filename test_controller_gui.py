import tkinter as tk
from tkinter import ttk, messagebox
from threading import Lock, Thread
import time

try:
    from inputs import get_gamepad
    from inputs import devices
    XBOX_SUPPORT = True
    XBOX_BACKEND = "inputs"
    XBOX_DEVICE_NAME = devices.gamepads[0].name if getattr(devices, "gamepads", []) else "Xbox controller"
except ImportError:
    XBOX_SUPPORT = False
    XBOX_BACKEND = None
    XBOX_DEVICE_NAME = "Unknown controller"

AXIS_CODES = {
    "LX": {"ABS_X"},
    "LY": {"ABS_Y"},
    "RX": {"ABS_RX"},
    "RY": {"ABS_RY"},
    # Different drivers expose triggers with slightly different names.
    "LT": {"ABS_Z", "ABS_THROTTLE"},
    "RT": {"ABS_RZ", "ABS_RUDDER"},
}

BUTTON_CODES = {
    "Y": {"BTN_NORTH"},
    "A": {"BTN_SOUTH"},
    "B": {"BTN_EAST"},
    "X": {"BTN_WEST"},
    "LB": {"BTN_TL"},
    "RB": {"BTN_TR"},
    "START": {"BTN_START", "BTN_MODE"},
    "BACK": {"BTN_SELECT"},
    "LS_PRESS": {"BTN_THUMBL"},
    "RS_PRESS": {"BTN_THUMBR"},
}

AXIS_LOOKUP = {code: name for name, codes in AXIS_CODES.items() for code in codes}
BUTTON_LOOKUP = {code: name for name, codes in BUTTON_CODES.items() for code in codes}

class ControllerTesterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Xbox Controller Tester")
        self.root.geometry("900x700")
        self.root.resizable(False, False)
        
        if not XBOX_SUPPORT:
            messagebox.showerror("Error", "inputs library not found. Install with: pip install inputs")
            return
        
        # Controller state
        self.controller_state = {
            "LX": 0, "LY": 0, "RX": 0, "RY": 0,
            "LT": 0, "RT": 0,
            "Y": False, "B": False, "A": False, "X": False,
            "LB": False, "RB": False,
            "START": False, "BACK": False,
            "LS_PRESS": False, "RS_PRESS": False
        }
        
        self.connected = False
        self.running = True
        self.input_thread = None
        self.state_lock = Lock()
        self.state_dirty = True
        self.refresh_options = [16, 33, 50, 100]
        self.gui_refresh_ms = 33
        self._last_rendered_values = {}
        self._last_rendered_buttons = {}
        self._last_info_text = None
        self._backend_label_text = f"Backend: {XBOX_BACKEND} | Device: {XBOX_DEVICE_NAME}"
        
        # Create GUI
        self.create_widgets()
        self.root.after(self.gui_refresh_ms, self.refresh_gui_loop)
        self.start_input_thread()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """Create GUI elements"""
        
        # Title
        title = ttk.Label(self.root, text="🎮 Xbox Controller Tester", font=("Arial", 18, "bold"))
        title.pack(pady=10)
        
        # Status bar
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = ttk.Label(self.status_frame, text="🔴 Waiting for controller...", 
                                      foreground="red", font=("Arial", 11))
        self.status_label.pack(side=tk.LEFT)

        self.backend_label = ttk.Label(
            self.status_frame,
            text=self._backend_label_text,
            font=("Arial", 10),
            foreground="gray"
        )
        self.backend_label.pack(side=tk.RIGHT)
        
        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left section - Joysticks
        left_frame = ttk.LabelFrame(main_container, text="Analog Sticks & Triggers", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Left Joystick
        ttk.Label(left_frame, text="Left Joystick (LX, LY)", font=("Arial", 10, "bold")).pack()
        self.lx_var = tk.IntVar()
        self.ly_var = tk.IntVar()
        
        ttk.Label(left_frame, text="LX:").pack()
        lx_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL, 
                             variable=self.lx_var, state='disabled')
        lx_scale.pack(fill=tk.X, pady=2)
        self.lx_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
        self.lx_label.pack()
        
        ttk.Label(left_frame, text="LY:").pack(pady=(10, 0))
        ly_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL,
                             variable=self.ly_var, state='disabled')
        ly_scale.pack(fill=tk.X, pady=2)
        self.ly_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
        self.ly_label.pack()
        
        # Right Joystick
        ttk.Label(left_frame, text="Right Joystick (RX, RY)", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        self.rx_var = tk.IntVar()
        self.ry_var = tk.IntVar()
        
        ttk.Label(left_frame, text="RX:").pack()
        rx_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL,
                             variable=self.rx_var, state='disabled')
        rx_scale.pack(fill=tk.X, pady=2)
        self.rx_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
        self.rx_label.pack()
        
        ttk.Label(left_frame, text="RY:").pack(pady=(10, 0))
        ry_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL,
                             variable=self.ry_var, state='disabled')
        ry_scale.pack(fill=tk.X, pady=2)
        self.ry_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
        self.ry_label.pack()
        
        # Triggers
        ttk.Label(left_frame, text="Triggers (LT, RT)", font=("Arial", 10, "bold")).pack(pady=(15, 0))
        self.lt_var = tk.IntVar()
        self.rt_var = tk.IntVar()
        
        ttk.Label(left_frame, text="LT (Left Trigger):").pack()
        lt_scale = ttk.Scale(left_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                             variable=self.lt_var, state='disabled')
        lt_scale.pack(fill=tk.X, pady=2)
        self.lt_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
        self.lt_label.pack()
        
        ttk.Label(left_frame, text="RT (Right Trigger):").pack(pady=(10, 0))
        rt_scale = ttk.Scale(left_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                             variable=self.rt_var, state='disabled')
        rt_scale.pack(fill=tk.X, pady=2)
        self.rt_label = ttk.Label(left_frame, text="0", font=("Arial", 9))
        self.rt_label.pack()
        
        # Right section - Buttons
        right_frame = ttk.LabelFrame(main_container, text="Digital Buttons", padding=10)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Button grid
        button_grid = ttk.Frame(right_frame)
        button_grid.pack(fill=tk.BOTH, expand=True)
        
        buttons_config = [
            ("Y", 0, 0), ("X", 0, 1),
            ("B", 1, 0), ("A", 1, 1),
            ("LB", 2, 0), ("RB", 2, 1),
            ("START", 3, 0), ("BACK", 3, 1),
            ("LS", 4, 0), ("RS", 4, 1),
        ]
        
        self.button_labels = {}
        for btn_name, row, col in buttons_config:
            btn_frame = ttk.Frame(button_grid)
            btn_frame.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            
            btn_label = ttk.Label(btn_frame, text=btn_name, font=("Arial", 10, "bold"),
                                 background="lightgray", foreground="black", width=12, 
                                 padding=10, relief="raised")
            btn_label.pack(fill=tk.BOTH, expand=True)
            self.button_labels[btn_name] = btn_label
        
        # Configure grid weights
        for i in range(5):
            button_grid.grid_rowconfigure(i, weight=1)
        button_grid.grid_columnconfigure(0, weight=1)
        button_grid.grid_columnconfigure(1, weight=1)
        
        # Bottom info
        info_frame = ttk.Frame(self.root)
        info_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.info_label = ttk.Label(info_frame, text="Waiting for input...", 
                                    font=("Arial", 10), foreground="blue")
        self.info_label.pack()

        # Performance controls
        perf_frame = ttk.Frame(self.root)
        perf_frame.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Label(perf_frame, text="Refresh rate:", font=("Arial", 9)).pack(side=tk.LEFT)
        self.refresh_var = tk.StringVar(value=str(self.gui_refresh_ms))
        refresh_box = ttk.Combobox(
            perf_frame,
            textvariable=self.refresh_var,
            values=[str(value) for value in self.refresh_options],
            width=6,
            state="readonly"
        )
        refresh_box.pack(side=tk.LEFT, padx=(8, 12))
        refresh_box.bind("<<ComboboxSelected>>", self.on_refresh_change)

        ttk.Label(perf_frame, text="Lower = smoother, higher = lighter CPU", font=("Arial", 9)).pack(side=tk.LEFT)
        
        # Button frame
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        reset_btn = ttk.Button(btn_frame, text="Reset", command=self.reset_values)
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        exit_btn = ttk.Button(btn_frame, text="Exit", command=self.on_closing)
        exit_btn.pack(side=tk.RIGHT, padx=5)
    
    def start_input_thread(self):
        """Start thread to read controller input"""
        self.input_thread = Thread(target=self.read_input_loop, daemon=True)
        self.input_thread.start()

    def _normalize_trigger_state(self, value):
        """Map trigger values to 0..255 regardless of the driver range."""
        if value < 0:
            # Some drivers report triggers in a signed range.
            value = int((value + 32768) * 255 / 65535)
        return max(0, min(255, int(value)))

    def on_refresh_change(self, _event=None):
        """Apply a new GUI refresh interval from the dropdown."""
        try:
            value = int(self.refresh_var.get())
        except ValueError:
            self.refresh_var.set(str(self.gui_refresh_ms))
            return

        if value not in self.refresh_options:
            self.refresh_var.set(str(self.gui_refresh_ms))
            return

        self.gui_refresh_ms = value
        self.refresh_var.set(str(value))
    
    def read_input_loop(self):
        """Read controller input continuously"""
        retry_count = 0
        max_retries = 5
        
        while self.running:
            try:
                events = get_gamepad()
                retry_count = 0  # Reset retry count on successful read
                
                if not self.connected:
                    self.connected = True
                    self.root.after(0, self.update_status_connected)
                
                state_changed = False
                for event in events:
                    if event.ev_type == 'Absolute':
                        axis_name = AXIS_LOOKUP.get(event.code)
                        if axis_name:
                            value = self._normalize_trigger_state(event.state) if axis_name in {"LT", "RT"} else int(event.state)
                            with self.state_lock:
                                if self.controller_state[axis_name] != value:
                                    self.controller_state[axis_name] = value
                                    state_changed = True
                    
                    elif event.ev_type == 'Key':
                        button_name = BUTTON_LOOKUP.get(event.code)
                        if button_name:
                            value = event.state == 1
                            with self.state_lock:
                                if self.controller_state[button_name] != value:
                                    self.controller_state[button_name] = value
                                    state_changed = True

                if state_changed:
                    self.state_dirty = True
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    if self.connected:
                        self.connected = False
                        self.root.after(0, self.update_status_disconnected)
                time.sleep(0.5)

    def refresh_gui_loop(self):
        """Refresh the GUI at a fixed rate to avoid excessive redraws."""
        if not self.running:
            return

        if self.state_dirty:
            self.state_dirty = False
            self.update_gui()

        self.root.after(self.gui_refresh_ms, self.refresh_gui_loop)
    
    def update_gui(self):
        """Update GUI with current controller state"""
        with self.state_lock:
            snapshot = dict(self.controller_state)

        value_widgets = {
            "LX": (self.lx_var, self.lx_label, 6),
            "LY": (self.ly_var, self.ly_label, 6),
            "RX": (self.rx_var, self.rx_label, 6),
            "RY": (self.ry_var, self.ry_label, 6),
            "LT": (self.lt_var, self.lt_label, 3),
            "RT": (self.rt_var, self.rt_label, 3),
        }
        for key, (var, label, width) in value_widgets.items():
            value = snapshot[key]
            if self._last_rendered_values.get(key) != value:
                var.set(value)
                label.config(text=f"{value:{width}d}")
                self._last_rendered_values[key] = value

        button_map = {
            "Y": "Y", "B": "B", "A": "A", "X": "X",
            "LB": "LB", "RB": "RB",
            "START": "START", "BACK": "BACK",
            "LS": "LS_PRESS", "RS": "RS_PRESS"
        }

        pressed_buttons = []
        for display_name, state_key in button_map.items():
            is_pressed = snapshot[state_key]
            if self._last_rendered_buttons.get(display_name) != is_pressed:
                label = self.button_labels[display_name]
                if is_pressed:
                    label.config(background="lime", foreground="black", relief="sunken")
                else:
                    label.config(background="lightgray", foreground="black", relief="raised")
                self._last_rendered_buttons[display_name] = is_pressed
            if is_pressed:
                pressed_buttons.append(display_name)

        info_text = f"Buttons pressed: {', '.join(pressed_buttons)}" if pressed_buttons else "Ready"
        if info_text != self._last_info_text:
            self.info_label.config(text=info_text)
            self._last_info_text = info_text
    
    def update_status_connected(self):
        """Update status when connected"""
        self.status_label.config(
            text=f"🟢 Controller Connected: {XBOX_DEVICE_NAME}",
            foreground="green"
        )
    
    def update_status_disconnected(self):
        """Update status when disconnected"""
        self.status_label.config(text="🔴 Controller Disconnected", foreground="red")
    
    def reset_values(self):
        """Reset all values to zero"""
        with self.state_lock:
            self.controller_state = {
                "LX": 0, "LY": 0, "RX": 0, "RY": 0,
                "LT": 0, "RT": 0,
                "Y": False, "B": False, "A": False, "X": False,
                "LB": False, "RB": False,
                "START": False, "BACK": False,
                "LS_PRESS": False, "RS_PRESS": False
            }
        self._last_rendered_values.clear()
        self._last_rendered_buttons.clear()
        self._last_info_text = None
        self.state_dirty = True
        self.update_gui()
    
    def on_closing(self):
        """Handle window close"""
        self.running = False
        if self.input_thread:
            self.input_thread.join(timeout=2)
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = ControllerTesterGUI(root)
    root.mainloop()
