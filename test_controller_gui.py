import tkinter as tk
from tkinter import ttk, messagebox
from threading import Lock, Thread
import time

pygame = None

try:
    from inputs import get_gamepad
    from inputs import devices as input_devices
    XBOX_SUPPORT = True
    XBOX_BACKEND = "inputs"
    XBOX_DEVICE_NAME = input_devices.gamepads[0].name if getattr(input_devices, "gamepads", []) else "Xbox controller"
except (ImportError, Exception):
    input_devices = None
    try:
        import pygame as pygame_module
        pygame = pygame_module
        XBOX_SUPPORT = True
        XBOX_BACKEND = "pygame"
        XBOX_DEVICE_NAME = "Xbox controller"
    except (ImportError, Exception):
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
        self.root.geometry("980x760")
        self.root.minsize(900, 700)
        self.root.resizable(True, True)
        
        if not XBOX_SUPPORT:
            messagebox.showerror("Error", "No controller backend found. Install with: pip install inputs or pip install pygame")
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
        self.button_colors = {
            True: {"background": "#8FE388", "foreground": "#0F172A", "relief": "sunken"},
            False: {"background": "#E5E7EB", "foreground": "#111827", "relief": "raised"},
        }
        self.controller_canvas = None
        self.controller_shapes = {}
        self.stick_canvases = {}
        self.stick_markers = {}
        self.axis_summary_labels = {}
        
        # Create GUI
        self.configure_styles()
        self.create_widgets()
        self.root.after(self.gui_refresh_ms, self.refresh_gui_loop)
        self.start_input_thread()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        """Create GUI elements"""
        self.root.configure(background="#F4F6F8")

        # Title
        header_frame = ttk.Frame(self.root, style="Surface.TFrame")
        header_frame.pack(fill=tk.X, padx=14, pady=(14, 8))

        title = ttk.Label(header_frame, text="Xbox Controller Tester", style="Title.TLabel")
        title.pack(anchor="center", pady=(10, 4))

        subtitle = ttk.Label(
            header_frame,
            text="Live input monitor for sticks, triggers, and digital buttons",
            style="Muted.TLabel"
        )
        subtitle.pack(anchor="center", pady=(0, 10))
        
        # Status bar
        self.status_frame = ttk.Frame(self.root, style="Surface.TFrame")
        self.status_frame.pack(fill=tk.X, padx=14, pady=(0, 8))
        
        self.status_label = ttk.Label(
            self.status_frame,
            text="Waiting for controller...",
            style="StatusOff.TLabel"
        )
        self.status_label.pack(side=tk.LEFT, padx=12, pady=10)

        self.backend_label = ttk.Label(
            self.status_frame,
            text=self._backend_label_text,
            style="Muted.TLabel"
        )
        self.backend_label.pack(side=tk.RIGHT, padx=12, pady=10)
        
        # Main container
        main_container = ttk.Frame(self.root, style="App.TFrame")
        main_container.pack(fill=tk.BOTH, expand=True, padx=14, pady=(0, 10))
        
        # Left section - Joysticks
        left_frame = ttk.LabelFrame(main_container, text="Analog Sticks & Triggers", style="Card.TLabelframe", padding=12)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        
        # Left Joystick
        ttk.Label(left_frame, text="Left Joystick (LX, LY)", style="Section.TLabel").pack()
        self.lx_var = tk.IntVar()
        self.ly_var = tk.IntVar()
        
        ttk.Label(left_frame, text="LX:", style="Field.TLabel").pack(pady=(6, 0))
        lx_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL, 
                             variable=self.lx_var, state='disabled')
        lx_scale.pack(fill=tk.X, pady=2)
        self.lx_label = ttk.Label(left_frame, text="0", style="Value.TLabel")
        self.lx_label.pack()
        
        ttk.Label(left_frame, text="LY:", style="Field.TLabel").pack(pady=(8, 0))
        ly_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL,
                             variable=self.ly_var, state='disabled')
        ly_scale.pack(fill=tk.X, pady=2)
        self.ly_label = ttk.Label(left_frame, text="0", style="Value.TLabel")
        self.ly_label.pack()
        
        # Right Joystick
        ttk.Label(left_frame, text="Right Joystick (RX, RY)", style="Section.TLabel").pack(pady=(14, 0))
        self.rx_var = tk.IntVar()
        self.ry_var = tk.IntVar()
        
        ttk.Label(left_frame, text="RX:", style="Field.TLabel").pack(pady=(6, 0))
        rx_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL,
                             variable=self.rx_var, state='disabled')
        rx_scale.pack(fill=tk.X, pady=2)
        self.rx_label = ttk.Label(left_frame, text="0", style="Value.TLabel")
        self.rx_label.pack()
        
        ttk.Label(left_frame, text="RY:", style="Field.TLabel").pack(pady=(8, 0))
        ry_scale = ttk.Scale(left_frame, from_=-32768, to=32767, orient=tk.HORIZONTAL,
                             variable=self.ry_var, state='disabled')
        ry_scale.pack(fill=tk.X, pady=2)
        self.ry_label = ttk.Label(left_frame, text="0", style="Value.TLabel")
        self.ry_label.pack()
        
        # Triggers
        ttk.Label(left_frame, text="Triggers (LT, RT)", style="Section.TLabel").pack(pady=(14, 0))
        self.lt_var = tk.IntVar()
        self.rt_var = tk.IntVar()
        
        ttk.Label(left_frame, text="LT (Left Trigger):", style="Field.TLabel").pack(pady=(6, 0))
        lt_scale = ttk.Scale(left_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                             variable=self.lt_var, state='disabled')
        lt_scale.pack(fill=tk.X, pady=2)
        self.lt_label = ttk.Label(left_frame, text="0", style="Value.TLabel")
        self.lt_label.pack()
        
        ttk.Label(left_frame, text="RT (Right Trigger):", style="Field.TLabel").pack(pady=(8, 0))
        rt_scale = ttk.Scale(left_frame, from_=0, to=255, orient=tk.HORIZONTAL,
                             variable=self.rt_var, state='disabled')
        rt_scale.pack(fill=tk.X, pady=2)
        self.rt_label = ttk.Label(left_frame, text="0", style="Value.TLabel")
        self.rt_label.pack()
        
        # Right section - Buttons
        right_frame = ttk.LabelFrame(main_container, text="Interactive Controller View", style="Card.TLabelframe", padding=12)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))
        sticks_frame = ttk.Frame(right_frame, style="Surface.TFrame")
        sticks_frame.pack(fill=tk.X, pady=(0, 12))
        self.create_stick_monitor(sticks_frame, "Left Stick", "LX", "LY", 0)
        self.create_stick_monitor(sticks_frame, "Right Stick", "RX", "RY", 1)

        button_grid = ttk.Frame(right_frame, style="Surface.TFrame")
        button_grid.pack(fill=tk.BOTH, expand=True)

        buttons_config = [
            ("Y", 0, 0), ("X", 0, 1), ("B", 0, 2), ("A", 0, 3),
            ("LB", 1, 0), ("RB", 1, 1), ("START", 1, 2), ("BACK", 1, 3),
            ("LS", 2, 0), ("RS", 2, 1),
        ]

        self.button_labels = {}
        for btn_name, row, col in buttons_config:
            btn_frame = ttk.Frame(button_grid, style="Surface.TFrame")
            btn_frame.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            btn_label = ttk.Label(
                btn_frame,
                text=btn_name,
                font=("Segoe UI", 9, "bold"),
                background=self.button_colors[False]["background"],
                foreground=self.button_colors[False]["foreground"],
                width=7,
                anchor="center",
                padding=(6, 10),
                relief=self.button_colors[False]["relief"]
            )
            btn_label.pack(fill=tk.BOTH, expand=True)
            self.button_labels[btn_name] = btn_label

        for i in range(3):
            button_grid.grid_rowconfigure(i, weight=1)
        for i in range(4):
            button_grid.grid_columnconfigure(i, weight=1)
        
        # Bottom info
        info_frame = ttk.Frame(self.root, style="Surface.TFrame")
        info_frame.pack(fill=tk.X, padx=14, pady=(0, 8))
        
        self.info_label = ttk.Label(info_frame, text="Waiting for input...", style="Info.TLabel")
        self.info_label.pack(anchor="w", padx=12, pady=(8, 4))

        # Performance controls
        perf_frame = ttk.Frame(info_frame, style="Surface.TFrame")
        perf_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

        ttk.Label(perf_frame, text="Refresh rate:", style="Field.TLabel").pack(side=tk.LEFT)
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

        ttk.Label(perf_frame, text="Lower = smoother, higher = lighter CPU", style="Muted.TLabel").pack(side=tk.LEFT)
        
        # Button frame
        btn_frame = ttk.Frame(self.root, style="App.TFrame")
        btn_frame.pack(fill=tk.X, padx=14, pady=(0, 14))
        
        reset_btn = ttk.Button(btn_frame, text="Reset", style="Action.TButton", command=self.reset_values)
        reset_btn.pack(side=tk.LEFT, padx=5)
        
        exit_btn = ttk.Button(btn_frame, text="Exit", style="Action.TButton", command=self.on_closing)
        exit_btn.pack(side=tk.RIGHT, padx=5)

    def configure_styles(self):
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure("App.TFrame", background="#F4F6F8")
        style.configure("Surface.TFrame", background="#FFFFFF")
        style.configure("Card.TLabelframe", background="#FFFFFF", borderwidth=1)
        style.configure("Card.TLabelframe.Label", background="#FFFFFF", foreground="#0F172A", font=("Segoe UI", 10, "bold"))
        style.configure("Title.TLabel", background="#FFFFFF", foreground="#0F172A", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", background="#FFFFFF", foreground="#111827", font=("Segoe UI", 10, "bold"))
        style.configure("Field.TLabel", background="#FFFFFF", foreground="#374151", font=("Segoe UI", 9))
        style.configure("Value.TLabel", background="#FFFFFF", foreground="#111827", font=("Consolas", 10, "bold"))
        style.configure("Muted.TLabel", background="#FFFFFF", foreground="#6B7280", font=("Segoe UI", 9))
        style.configure("Info.TLabel", background="#FFFFFF", foreground="#1D4ED8", font=("Segoe UI", 10, "bold"))
        style.configure("StatusOn.TLabel", background="#FFFFFF", foreground="#15803D", font=("Segoe UI", 10, "bold"))
        style.configure("StatusOff.TLabel", background="#FFFFFF", foreground="#B91C1C", font=("Segoe UI", 10, "bold"))
        style.configure("Action.TButton", font=("Segoe UI", 9), padding=(10, 6))

    def create_stick_monitor(self, parent, title, axis_x, axis_y, column):
        card = ttk.Frame(parent, style="Surface.TFrame")
        card.grid(row=0, column=column, padx=6, sticky="nsew")
        parent.grid_columnconfigure(column, weight=1)

        ttk.Label(card, text=title, style="Section.TLabel").pack(anchor="center", pady=(0, 6))
        canvas = tk.Canvas(card, width=150, height=150, background="#FFFFFF", highlightthickness=0, bd=0)
        canvas.pack()
        canvas.create_oval(18, 18, 132, 132, outline="#CBD5E1", width=1)
        canvas.create_line(75, 18, 75, 132, fill="#CBD5E1")
        canvas.create_line(18, 75, 132, 75, fill="#CBD5E1")
        marker = canvas.create_oval(70, 70, 80, 80, fill="#0F172A", outline="")
        self.stick_canvases[title] = canvas
        self.stick_markers[title] = marker

        summary = ttk.Label(card, text=f"{axis_x}: 0    {axis_y}: 0", style="Value.TLabel")
        summary.pack(anchor="center", pady=(6, 0))
        self.axis_summary_labels[title] = (summary, axis_x, axis_y)
    
    def start_input_thread(self):
        """Start thread to read controller input"""
        self.input_thread = Thread(target=self.read_input_loop, daemon=True)
        self.input_thread.start()

    def _set_connected(self, connected):
        if self.connected != connected:
            self.connected = connected
            callback = self.update_status_connected if connected else self.update_status_disconnected
            self.root.after(0, callback)

    def _normalize_trigger_state(self, value):
        """Map trigger values to 0..255 regardless of the driver range."""
        if value < 0:
            # Some drivers report triggers in a signed range.
            value = int((value + 32768) * 255 / 65535)
        return max(0, min(255, int(value)))

    def _normalize_pygame_axis(self, value):
        return max(-32768, min(32767, int(value * 32767)))

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
        if XBOX_BACKEND == "inputs":
            self.read_input_loop_inputs()
        elif XBOX_BACKEND == "pygame":
            self.read_input_loop_pygame()

    def read_input_loop_inputs(self):
        """Read controller input continuously using the inputs backend."""
        retry_count = 0
        max_retries = 5
        
        while self.running:
            try:
                events = get_gamepad()
                retry_count = 0  # Reset retry count on successful read
                self._set_connected(True)
                
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
                
            except Exception:
                retry_count += 1
                if retry_count > max_retries:
                    self._set_connected(False)
                time.sleep(0.5)

    def read_input_loop_pygame(self):
        """Read controller input continuously using the pygame backend."""
        pygame.init()
        pygame.joystick.init()
        joystick = None
        last_joystick_name = None

        while self.running:
            try:
                joystick_count = pygame.joystick.get_count()
                if joystick_count == 0:
                    joystick = None
                    last_joystick_name = None
                    self._set_connected(False)
                    time.sleep(0.5)
                    continue

                if joystick is None or joystick.get_name() != last_joystick_name:
                    joystick = pygame.joystick.Joystick(0)
                    joystick.init()
                    last_joystick_name = joystick.get_name()

                self._set_connected(True)
                state_changed = False

                for event in pygame.event.get():
                    if event.type == pygame.JOYAXISMOTION:
                        value = None
                        if event.axis == 0:
                            key = "LX"
                            value = self._normalize_pygame_axis(event.value)
                        elif event.axis == 1:
                            key = "LY"
                            value = self._normalize_pygame_axis(-event.value)
                        elif event.axis == 2:
                            key = "RX"
                            value = self._normalize_pygame_axis(event.value)
                        elif event.axis == 3:
                            key = "RY"
                            value = self._normalize_pygame_axis(-event.value)
                        elif event.axis == 4:
                            key = "LT"
                            value = self._normalize_trigger_state(int((event.value + 1) * 127.5))
                        elif event.axis == 5:
                            key = "RT"
                            value = self._normalize_trigger_state(int((event.value + 1) * 127.5))
                        else:
                            continue

                        with self.state_lock:
                            if self.controller_state[key] != value:
                                self.controller_state[key] = value
                                state_changed = True

                    elif event.type in (pygame.JOYBUTTONDOWN, pygame.JOYBUTTONUP):
                        button_map = {
                            0: "A",
                            1: "B",
                            2: "X",
                            3: "Y",
                            4: "LB",
                            5: "RB",
                            6: "BACK",
                            7: "START",
                            8: "LS_PRESS",
                            9: "RS_PRESS",
                        }
                        button_name = button_map.get(event.button)
                        if not button_name:
                            continue

                        value = event.type == pygame.JOYBUTTONDOWN
                        with self.state_lock:
                            if self.controller_state[button_name] != value:
                                self.controller_state[button_name] = value
                                state_changed = True

                if state_changed:
                    self.state_dirty = True

                time.sleep(0.01)
            except Exception:
                joystick = None
                last_joystick_name = None
                self._set_connected(False)
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

        self.update_stick_monitors(snapshot)

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
                label.config(**self.button_colors[is_pressed])
                self._last_rendered_buttons[display_name] = is_pressed
            if is_pressed:
                pressed_buttons.append(display_name)

        info_text = f"Buttons pressed: {', '.join(pressed_buttons)}" if pressed_buttons else "Ready"
        if info_text != self._last_info_text:
            self.info_label.config(text=info_text)
            self._last_info_text = info_text

    def update_stick_monitors(self, snapshot):
        stick_configs = {
            "Left Stick": ("LX", "LY"),
            "Right Stick": ("RX", "RY"),
        }

        for title, (axis_x, axis_y) in stick_configs.items():
            canvas = self.stick_canvases.get(title)
            marker = self.stick_markers.get(title)
            label_data = self.axis_summary_labels.get(title)
            if not canvas or not marker or not label_data:
                continue

            x_value = snapshot[axis_x]
            y_value = snapshot[axis_y]
            offset_x = self.normalize_axis_offset(x_value, 52)
            offset_y = self.normalize_axis_offset(y_value, 52)
            canvas.coords(marker, 70 + offset_x, 70 + offset_y, 80 + offset_x, 80 + offset_y)

            summary, _, _ = label_data
            summary.config(text=f"{axis_x}: {x_value:6d}    {axis_y}: {y_value:6d}")

    def normalize_axis_offset(self, value, travel):
        return int(max(-travel, min(travel, value * travel / 32767 if value else 0)))
    
    def update_status_connected(self):
        """Update status when connected"""
        self.status_label.config(
            text=f"Controller connected: {XBOX_DEVICE_NAME}",
            style="StatusOn.TLabel"
        )
    
    def update_status_disconnected(self):
        """Update status when disconnected"""
        self.status_label.config(text="Controller disconnected", style="StatusOff.TLabel")
    
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
