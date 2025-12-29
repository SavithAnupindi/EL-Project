import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3, os, datetime, random, threading, time, math, csv
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as pdf_canvas

DB = "silo_system.sqlite3"
SIMULATED = False 

def ensure_db():
    conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT)''')
    cur.execute('''CREATE TABLE IF NOT EXISTS silos (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        owner_id INTEGER, 
        name TEXT, 
        radius_m REAL, 
        height_m REAL, 
        token TEXT, 
        threshold_moisture REAL, 
        threshold_temp REAL, 
        threshold_level_percent REAL,
        next_service_date DATE
    )''')
    cur.execute('''CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        silo_id INTEGER, 
        timestamp TIMESTAMP, 
        distance_m REAL, 
        level_percent REAL, 
        temp_c REAL, 
        humidity REAL, 
        raw_json TEXT
    )''')
    
    cur.execute("SELECT count(*) FROM silos")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO users (name,email) VALUES (?,?)", ('Farm Admin','admin@farm.local'))
        uid = cur.lastrowid
        
        today = datetime.date.today()
        service_future = today + datetime.timedelta(days=90)
        
        silos_seed = [
            ('Silo 01 (Wheat)', 2.5, 8.0, 13.5, 35.0, 15.0, service_future),
            ('Silo 02 (Corn)', 2.5, 8.0, 14.0, 30.0, 10.0, service_future)
        ]
        
        for idx, s in enumerate(silos_seed):
            cur.execute("INSERT INTO silos (owner_id,name,radius_m,height_m,token,threshold_moisture,threshold_temp,threshold_level_percent,next_service_date) VALUES (?,?,?,?,?,?,?,?,?)",
                        (uid, s[0], s[1], s[2], f'tk-0{idx}', s[3], s[4], s[5], s[6]))
            sid = cur.lastrowid
            
        
            now = datetime.datetime.now()
            base_lvl = 75.0 if idx == 0 else 45.0
            for i in range(20):
                ts = now - datetime.timedelta(hours=2*(20-i))
                lvl = base_lvl 
                dist = s[2] * (1 - lvl/100.0)
                temp = 24.5 
                hum = 12.0
                cur.execute('INSERT INTO telemetry (silo_id,timestamp,distance_m,level_percent,temp_c,humidity,raw_json) VALUES (?,?,?,?,?,?,?)',
                            (sid, ts, dist, lvl, temp, hum, '{"seed":true}'))
        conn.commit()
    cur.close(); conn.close()

def add_new_silo_db(name, radius, height):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    next_service = datetime.date.today() + datetime.timedelta(days=180)
    cur.execute("INSERT INTO silos (owner_id,name,radius_m,height_m,token,threshold_moisture,threshold_temp,threshold_level_percent,next_service_date) VALUES (?,?,?,?,?,?,?,?,?)",
                (1, name, radius, height, f'tk-{int(time.time())}', 14.0, 40.0, 10.0, next_service))
    conn.commit()
    sid = cur.lastrowid
    conn.close()
    return sid

def update_silo_details_db(silo_id, name, radius, height):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("UPDATE silos SET name=?, radius_m=?, height_m=? WHERE id=?", (name, radius, height, silo_id))
    conn.commit()
    conn.close()

def get_all_silos():
    conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = conn.cursor()
    cur.execute("SELECT id, name, radius_m, height_m, threshold_moisture, threshold_temp, threshold_level_percent, next_service_date FROM silos")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_latest(silo_id):
    conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = conn.cursor()
    cur.execute('SELECT timestamp, level_percent, temp_c, humidity FROM telemetry WHERE silo_id=? ORDER BY timestamp DESC LIMIT 1', (silo_id,))
    row = cur.fetchone()
    conn.close()
    if row:
        ts = row[0] if isinstance(row[0], datetime.datetime) else datetime.datetime.fromisoformat(str(row[0]))
        return {'timestamp': ts, 'level_percent': row[1], 'temp_c': row[2], 'humidity': row[3]}
    return None

def get_history(silo_id, limit=100):
    conn = sqlite3.connect(DB, detect_types=sqlite3.PARSE_DECLTYPES)
    cur = conn.cursor()
    cur.execute('SELECT timestamp, level_percent, temp_c, humidity FROM telemetry WHERE silo_id=? ORDER BY timestamp DESC LIMIT ?', (silo_id, limit))
    rows = cur.fetchall()
    conn.close()
    res = []
    for r in rows:
        ts = r[0] if isinstance(r[0], datetime.datetime) else datetime.datetime.fromisoformat(str(r[0]))
        res.append({'timestamp': ts, 'level_percent': r[1], 'temp_c': r[2], 'humidity': r[3]})
    return res[::-1]

def insert_telemetry(silo_id, lvl, temp, hum):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("SELECT height_m FROM silos WHERE id=?", (silo_id,))
    h_row = cur.fetchone()
    h = h_row[0] if h_row else 10.0
    dist = h * (1 - lvl/100.0)
    ts = datetime.datetime.now()
    cur.execute('INSERT INTO telemetry (silo_id,timestamp,distance_m,level_percent,temp_c,humidity,raw_json) VALUES (?,?,?,?,?,?,?)',
                (silo_id, ts, dist, lvl, temp, hum, '{"manual":true}'))
    conn.commit()
    conn.close()

def update_thresholds_db(silo_id, m, t, l):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute('UPDATE silos SET threshold_moisture=?, threshold_temp=?, threshold_level_percent=? WHERE id=?', (m, t, l, silo_id))
    conn.commit()
    conn.close()

def simulator_thread():
    while True:
        try:
            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute("SELECT id, height_m FROM silos")
            silos = cur.fetchall()
            for s in silos:
                sid, h = s
                cur.execute("SELECT level_percent FROM telemetry WHERE silo_id=? ORDER BY timestamp DESC LIMIT 1", (sid,))
                lr = cur.fetchone()
                prev_lvl = lr[0] if lr else 50.0
                
                consumption = random.uniform(0.01, 0.15) 
                noise = random.uniform(-0.05, 0.05)
                change = -(consumption) + noise
                new_lvl = max(0, min(100, prev_lvl + change))
                dist = h * (1 - new_lvl/100.0)
                temp = 24 + random.uniform(-1, 5) 
                hum = 13 + random.uniform(-2, 2)
                ts = datetime.datetime.now()
                cur.execute('INSERT INTO telemetry (silo_id,timestamp,distance_m,level_percent,temp_c,humidity,raw_json) VALUES (?,?,?,?,?,?,?)',
                            (sid, ts, dist, new_lvl, temp, hum, '{"sim":true}'))
            conn.commit()
            conn.close()
        except Exception:
            pass
        time.sleep(5) 

class SiloManagementApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Silo Management System")
        self.geometry("1480x950")
        self.configure(bg="#111928") 
        
        self.silos_map = {} 
        self.current_silo_id = None
        self.silo_data = {} 
        self._updating = False
        
        self._configure_styles()
        self._build_layout()
        self._load_silo_list()
        
        self.after(500, self.update_loop)

    def _configure_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.colors = {
            'bg_main': "#111827",      
            'bg_card': "#1f2937",      
            'bg_input': "#374151",     
            'text_primary': "#f3f4f6", 
            'text_secondary': "#9ca3af", 
            'accent': "#38bdf8",       
            'success': "#34d399",      
            'warning': "#fbbf24",      
            'danger': "#f87171",       
        }
        
        f_header = ("Roboto", 24, "bold")
        f_sub = ("Roboto", 12, "bold")
        f_body = ("Roboto", 11)
        f_value = ("Roboto", 26, "bold")
        
        self.style.configure("TFrame", background=self.colors['bg_main'])
        self.style.configure("Card.TFrame", background=self.colors['bg_card'], relief="flat")
        
        self.style.configure("TLabel", background=self.colors['bg_main'], foreground=self.colors['text_primary'], font=f_body)
        self.style.configure("Card.TLabel", background=self.colors['bg_card'], foreground=self.colors['text_secondary'], font=f_body)
        self.style.configure("Header.TLabel", background=self.colors['bg_main'], foreground=self.colors['accent'], font=f_header)
        self.style.configure("SubHeader.TLabel", background=self.colors['bg_card'], foreground=self.colors['text_primary'], font=f_sub)
        self.style.configure("Value.TLabel", background=self.colors['bg_card'], foreground="#ffffff", font=f_value)
        self.style.configure("Alert.TLabel", background=self.colors['bg_card'], foreground=self.colors['danger'], font=("Roboto", 12, "bold"))
        self.style.configure("Info.TLabel", background=self.colors['bg_card'], foreground=self.colors['accent'], font=("Roboto", 12))

        self.style.configure("TButton", font=("Roboto", 11, "bold"), background=self.colors['bg_input'], foreground="white", borderwidth=0, padding=8)
        self.style.map("TButton", background=[('active', self.colors['accent'])], foreground=[('active', 'black')])
        
        self.style.configure("Action.TButton", background=self.colors['accent'], foreground="black")
        self.style.map("Action.TButton", background=[('active', '#ffffff')])
        
        self.style.configure("Danger.TButton", background=self.colors['danger'], foreground="black")
        self.style.map("Danger.TButton", background=[('active', '#ffffff')])

    def _build_layout(self):
        top_bar = ttk.Frame(self)
        top_bar.pack(fill=tk.X, padx=25, pady=20)
        
        ttk.Label(top_bar, text="SILO MANAGEMENT SYSTEM", style="Header.TLabel").pack(side=tk.LEFT)
        
        controls_right = ttk.Frame(top_bar)
        controls_right.pack(side=tk.RIGHT)
        
        ttk.Button(controls_right, text="Edit Silo", command=self.edit_silo_popup).pack(side=tk.RIGHT, padx=5)
        ttk.Button(controls_right, text="+ Add Silo", command=self.add_silo_popup, style="Action.TButton").pack(side=tk.RIGHT, padx=5)
        
        self.silo_combo = ttk.Combobox(controls_right, state="readonly", font=("Roboto", 12), width=25)
        self.silo_combo.pack(side=tk.RIGHT, padx=10)
        self.silo_combo.bind("<<ComboboxSelected>>", self._on_silo_change)
        
        ttk.Label(controls_right, text="Select Silo:", font=("Roboto", 12, "bold")).pack(side=tk.RIGHT)

        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=(0, 25))
        
        left_col = ttk.Frame(main_container)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 15))
        
        right_col = ttk.Frame(main_container)
        right_col.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(15, 0))
        
        self._build_visual_card(left_col)
        self._build_maintenance_card(left_col)
        self._build_stats_card(left_col)
        
        self._build_charts_card(right_col)
        self._build_controls_card(right_col)

    def _build_visual_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=20)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(header, text="REAL-TIME LEVEL", style="SubHeader.TLabel").pack(side=tk.LEFT)
        
        # Increase canvas height significantly to avoid text clipping
        self.canvas_w = 460
        self.canvas_h = 500 
        self.canvas = tk.Canvas(card, bg=self.colors['bg_card'], highlightthickness=0, height=self.canvas_h, width=self.canvas_w)
        self.canvas.pack(pady=10)
        self._draw_silo_outline()

    def _build_maintenance_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=20)
        card.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(card, text="MAINTENANCE & HEALTH", style="SubHeader.TLabel").pack(anchor="w", pady=(0,15))
        
        grid = ttk.Frame(card, style="Card.TFrame")
        grid.pack(fill=tk.X)
        
        ttk.Label(grid, text="Next Service Due:", style="Card.TLabel").grid(row=0, column=0, sticky="w", pady=5)
        self.lbl_service = ttk.Label(grid, text="--", style="Info.TLabel")
        self.lbl_service.grid(row=0, column=1, sticky="e", padx=20)
        
        ttk.Label(grid, text="Sensor Battery:", style="Card.TLabel").grid(row=0, column=2, sticky="w", pady=5, padx=(40,0))
        self.lbl_battery = ttk.Label(grid, text="100% (Good)", foreground=self.colors['success'], background=self.colors['bg_card'], font=("Roboto", 11))
        self.lbl_battery.grid(row=0, column=3, sticky="e", padx=20)

        ttk.Label(grid, text="Connection Status:", style="Card.TLabel").grid(row=1, column=0, sticky="w", pady=5)
        self.lbl_conn = ttk.Label(grid, text="ONLINE ●", foreground=self.colors['success'], background=self.colors['bg_card'], font=("Roboto", 11, "bold"))
        self.lbl_conn.grid(row=1, column=1, sticky="e", padx=20)
        
        ttk.Label(grid, text="Grain Condition:", style="Card.TLabel").grid(row=1, column=2, sticky="w", pady=5, padx=(40,0))
        self.lbl_cond = ttk.Label(grid, text="Checking...", foreground=self.colors['accent'], background=self.colors['bg_card'], font=("Roboto", 11, "bold"))
        self.lbl_cond.grid(row=1, column=3, sticky="e", padx=20)

    def _build_stats_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=20)
        card.pack(fill=tk.X)
        
        ttk.Label(card, text="INVENTORY METRICS", style="SubHeader.TLabel").grid(row=0, column=0, columnspan=2, sticky="w", pady=(0,15))
        
        self.lbl_vol = ttk.Label(card, text="0 m³", style="Value.TLabel")
        self.lbl_vol.grid(row=1, column=0, sticky="w", padx=(0, 60))
        ttk.Label(card, text="Current Volume", style="Card.TLabel").grid(row=2, column=0, sticky="w")
        
        self.lbl_mass = ttk.Label(card, text="0 t", style="Value.TLabel")
        self.lbl_mass.grid(row=1, column=1, sticky="w")
        ttk.Label(card, text="Est. Mass (Wheat)", style="Card.TLabel").grid(row=2, column=1, sticky="w")
        
        self.lbl_days = ttk.Label(card, text="-- Days", style="Value.TLabel", foreground=self.colors['warning'])
        self.lbl_days.grid(row=1, column=2, sticky="w", padx=(60,0))
        ttk.Label(card, text="Est. Days Until Empty", style="Card.TLabel").grid(row=2, column=2, sticky="w", padx=(60,0))

    def _build_charts_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=15)
        card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill=tk.X, pady=(0,5))
        ttk.Label(header, text="ENVIRONMENTAL TRENDS", style="SubHeader.TLabel").pack(side=tk.LEFT)
        
        ttk.Button(header, text="Reset Graph View", command=self.reset_graph_view).pack(side=tk.RIGHT)
        
        fig, self.ax = plt.subplots(figsize=(6, 4), facecolor=self.colors['bg_card'])
        self.ax.set_facecolor(self.colors['bg_input'])
        self.ax.tick_params(colors=self.colors['text_secondary'])
        for spine in self.ax.spines.values(): spine.set_color(self.colors['bg_input'])
        
        self.canvas_chart = FigureCanvasTkAgg(fig, master=card)
        self.canvas_chart.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def _build_controls_card(self, parent):
        card = ttk.Frame(parent, style="Card.TFrame", padding=20)
        card.pack(fill=tk.X)
        
        ttk.Label(card, text="SYSTEM ALERTS", style="SubHeader.TLabel").pack(anchor="w", pady=(0,5))
        self.lbl_status = ttk.Label(card, text="● SYSTEM NORMAL", font=("Roboto", 13), foreground=self.colors['success'], background=self.colors['bg_card'])
        self.lbl_status.pack(anchor="w", pady=5)
        
        sep = ttk.Separator(card, orient='horizontal')
        sep.pack(fill=tk.X, pady=15)

        thresh_frame = ttk.Frame(card, style="Card.TFrame")
        thresh_frame.pack(fill=tk.X)
        
        font_lbl = ("Roboto", 12)
        font_ent = ("Roboto", 12, "bold")
        
        ttk.Label(thresh_frame, text="THRESHOLDS SETTINGS", style="SubHeader.TLabel").grid(row=0, column=0, columnspan=4, sticky="w", pady=(0,15))
        
        ttk.Label(thresh_frame, text="Max Temp (°C):", style="Card.TLabel", font=font_lbl).grid(row=1, column=0, sticky="w")
        self.ent_th_temp = ttk.Entry(thresh_frame, width=8, font=font_ent)
        self.ent_th_temp.grid(row=1, column=1, sticky="w", padx=10)
        
        ttk.Label(thresh_frame, text="Max Humidity (%):", style="Card.TLabel", font=font_lbl).grid(row=1, column=2, sticky="w", padx=(30,0))
        self.ent_th_hum = ttk.Entry(thresh_frame, width=8, font=font_ent)
        self.ent_th_hum.grid(row=1, column=3, sticky="w", padx=10)
        
        # Ensure command links to self.save_thresholds
        ttk.Button(thresh_frame, text="Update Thresholds", command=self.save_thresholds).grid(row=1, column=4, padx=(30,0))

        act_frame = ttk.Frame(card, style="Card.TFrame")
        act_frame.pack(fill=tk.X, pady=(25,0))
        
        ttk.Button(act_frame, text="Export CSV Data", command=self.export_csv).pack(side=tk.RIGHT, padx=5)
        ttk.Button(act_frame, text="Download PDF Report", command=self.generate_pdf).pack(side=tk.RIGHT, padx=5)
        ttk.Button(act_frame, text="Manual Reading Entry", command=self.manual_entry_popup).pack(side=tk.LEFT)

    # --- DEFINING METHOD HERE TO FIX ATTRIBUTE ERROR ---
    def save_thresholds(self):
        try:
            nt = float(self.ent_th_temp.get())
            nm = float(self.ent_th_hum.get())
            nl = self.silo_data['tl']
            update_thresholds_db(self.current_silo_id, nm, nt, nl)
            self.silo_data['tt'] = nt
            self.silo_data['tm'] = nm
            messagebox.showinfo("Success", "Thresholds updated.")
            self.update_loop(single_shot=True)
        except:
            messagebox.showerror("Error", "Invalid numeric input.")

    def reset_graph_view(self):
        self.ax.autoscale(enable=True, axis='both', tight=True)
        self.ax.relim()
        self.canvas_chart.draw()

    def add_silo_popup(self):
        top = tk.Toplevel(self)
        top.title("Add New Silo")
        top.geometry("400x350")
        top.configure(bg=self.colors['bg_card'])
        
        def lbl(txt): return ttk.Label(top, text=txt, background=self.colors['bg_card'], foreground="white")
        
        lbl("Silo Name:").pack(pady=(20,5))
        e_name = ttk.Entry(top, width=30)
        e_name.pack()
        
        lbl("Radius (meters):").pack(pady=(10,5))
        e_rad = ttk.Entry(top, width=30)
        e_rad.pack()
        
        lbl("Height (meters):").pack(pady=(10,5))
        e_height = ttk.Entry(top, width=30)
        e_height.pack()
        
        def save():
            try:
                name = e_name.get()
                r = float(e_rad.get())
                h = float(e_height.get())
                if not name: raise ValueError
                
                new_id = add_new_silo_db(name, r, h)
                top.destroy()
                self._load_silo_list()
                
                self.silo_combo.set(name)
                self._on_silo_change(None)
                messagebox.showinfo("Success", f"Silo '{name}' added successfully!")
            except:
                messagebox.showerror("Error", "Please enter valid numeric dimensions and a name.")
                
        ttk.Button(top, text="Create Silo", command=save, style="Action.TButton").pack(pady=30)

    def edit_silo_popup(self):
        if not self.current_silo_id:
            messagebox.showwarning("Selection", "No silo selected.")
            return

        top = tk.Toplevel(self)
        top.title("Edit Silo Details")
        top.geometry("400x350")
        top.configure(bg=self.colors['bg_card'])
        
        def lbl(txt): return ttk.Label(top, text=txt, background=self.colors['bg_card'], foreground="white")
        
        lbl("Silo Name:").pack(pady=(20,5))
        e_name = ttk.Entry(top, width=30)
        e_name.insert(0, self.silo_combo.get())
        e_name.pack()
        
        lbl("Radius (meters):").pack(pady=(10,5))
        e_rad = ttk.Entry(top, width=30)
        e_rad.insert(0, str(self.silo_data['r']))
        e_rad.pack()
        
        lbl("Height (meters):").pack(pady=(10,5))
        e_height = ttk.Entry(top, width=30)
        e_height.insert(0, str(self.silo_data['h']))
        e_height.pack()
        
        def save():
            try:
                name = e_name.get()
                r = float(e_rad.get())
                h = float(e_height.get())
                if not name: raise ValueError
                
                update_silo_details_db(self.current_silo_id, name, r, h)
                self.silo_data['r'] = r
                self.silo_data['h'] = h
                
                top.destroy()
                self._load_silo_list()
                self.silo_combo.set(name) 
                messagebox.showinfo("Success", f"Silo '{name}' updated.")
                self.update_loop(single_shot=True)
            except:
                messagebox.showerror("Error", "Invalid inputs.")
                
        ttk.Button(top, text="Save Changes", command=save, style="Action.TButton").pack(pady=30)

    def _draw_silo_outline(self):
        self.canvas.delete("all")
        cx = self.canvas_w / 2
        
        # Adjusted coordinates to move silo UP and provide space below
        self.silo_width = 300
        self.silo_body_h = 300 # Reduced slightly
        self.roof_h = 60
        
        self.silo_x1 = cx - self.silo_width/2
        self.silo_x2 = cx + self.silo_width/2
        
        self.silo_y_top = 70
        self.silo_y_btm = self.silo_y_top + self.silo_body_h
        
        self.canvas.create_polygon(
            self.silo_x1, self.silo_y_top, 
            cx, self.silo_y_top - self.roof_h, 
            self.silo_x2, self.silo_y_top, 
            fill="#374151", outline="#9ca3af", width=2
        )
        
        self.canvas.create_rectangle(
            self.silo_x1, self.silo_y_top, self.silo_x2, self.silo_y_btm,
            outline="#9ca3af", width=2, fill="#111827"
        )
        
        self.clip_area = (self.silo_x1 + 4, self.silo_y_top, self.silo_x2 - 4, self.silo_y_btm)
        # Position text well below the bottom
        self.canvas.create_text(cx, self.silo_y_btm + 50, text="-- %", fill="white", font=("Roboto", 28, "bold"), tags="txt_lvl")

    def _update_visuals(self, pct):
        self.canvas.delete("grain_bar")
        self.canvas.delete("txt_lvl")
        
        fill_h = self.silo_body_h * (pct/100.0)
        y_surface = self.silo_y_btm - fill_h
        
        bar_h = 4
        gap = 2
        
        current_y = self.silo_y_btm - bar_h
        
        color = self.colors['warning']
        if pct < self.silo_data.get('tl', 10): color = self.colors['danger']
        elif pct > 90: color = self.colors['success']

        while current_y > y_surface:
            self.canvas.create_rectangle(
                self.silo_x1 + 6, current_y, 
                self.silo_x2 - 6, current_y + bar_h,
                fill=color, outline="", tags="grain_bar"
            )
            current_y -= (bar_h + gap)
            
        cx = self.canvas_w / 2
        # Ensure text stays at bottom
        self.canvas.create_text(cx, self.silo_y_btm + 50, text=f"{pct:.1f}%", fill="white", font=("Roboto", 28, "bold"), tags="txt_lvl")

    def _load_silo_list(self):
        silos = get_all_silos()
        vals = []
        self.silos_map = {}
        for s in silos:
            sid, name, r, h, tm, tt, tl, nxt_svc = s
            self.silos_map[name] = {'id': sid, 'r': r, 'h': h, 'tm': tm, 'tt': tt, 'tl': tl, 'svc': nxt_svc}
            vals.append(name)
        
        self.silo_combo['values'] = vals
        if vals and not self.current_silo_id:
            self.silo_combo.current(0)
            self._on_silo_change(None)
        elif self.silo_combo.get() in self.silos_map:
            self._on_silo_change(None)

    def _on_silo_change(self, event):
        name = self.silo_combo.get()
        if not name: return
        self.silo_data = self.silos_map[name]
        self.current_silo_id = self.silo_data['id']
        
        self.ent_th_temp.delete(0, tk.END)
        self.ent_th_temp.insert(0, str(self.silo_data['tt']))
        self.ent_th_hum.delete(0, tk.END)
        self.ent_th_hum.insert(0, str(self.silo_data['tm']))
        
        svc_date = self.silo_data['svc']
        if isinstance(svc_date, str):
            self.lbl_service.config(text=svc_date)
        elif svc_date:
            self.lbl_service.config(text=svc_date.strftime('%Y-%m-%d'))
        else:
            self.lbl_service.config(text="Not Scheduled")
            
        self.update_loop(single_shot=True)

    def manual_entry_popup(self):
        top = tk.Toplevel(self)
        top.title("Manual Entry")
        top.geometry("300x250")
        top.configure(bg=self.colors['bg_card'])
        
        def l(t): ttk.Label(top, text=t, background=self.colors['bg_card'], font=("Roboto", 11)).pack(pady=5)
        
        l("Level %:")
        e_lvl = ttk.Entry(top); e_lvl.pack()
        l("Temp °C:")
        e_tmp = ttk.Entry(top); e_tmp.pack()
        l("Humidity %:")
        e_hum = ttk.Entry(top); e_hum.pack()
        
        def save():
            try:
                insert_telemetry(self.current_silo_id, float(e_lvl.get()), float(e_tmp.get()), float(e_hum.get()))
                top.destroy()
                self.update_loop(single_shot=True)
            except: messagebox.showerror("Error", "Invalid numbers")
                
        ttk.Button(top, text="Submit Reading", command=save, style="Action.TButton").pack(pady=20)

    def export_csv(self):
        rows = get_history(self.current_silo_id, limit=5000)
        if not rows: return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
        if path:
            with open(path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "Level %", "Temp C", "Humidity %"])
                for r in rows:
                    writer.writerow([r['timestamp'], r['level_percent'], r['temp_c'], r['humidity']])
            messagebox.showinfo("Export", "CSV Exported successfully.")

    def generate_pdf(self):
        rows = get_history(self.current_silo_id, limit=100)
        if not rows: return
        path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF","*.pdf")])
        if not path: return
        
        c = pdf_canvas.Canvas(path, pagesize=A4)
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, 800, f"Silo Report: {self.silo_combo.get()}")
        c.setFont("Helvetica", 10)
        c.drawString(50, 780, f"Generated: {datetime.datetime.now()}")
        
        y = 750
        c.drawString(50, y, "Timestamp")
        c.drawString(200, y, "Level %")
        c.drawString(300, y, "Temp C")
        c.drawString(400, y, "Humidity %")
        y -= 20
        c.line(50, y+15, 500, y+15)
        
        for r in rows[:40]:
            c.drawString(50, y, str(r['timestamp']))
            c.drawString(200, y, f"{r['level_percent']:.1f}")
            c.drawString(300, y, f"{r['temp_c']:.1f}")
            c.drawString(400, y, f"{r['humidity']:.1f}")
            y -= 15
        c.save()
        messagebox.showinfo("PDF", "Report generated.")

    def update_loop(self, single_shot=False):
        if self.current_silo_id:
            latest = get_latest(self.current_silo_id)
            if latest:
                lvl = latest['level_percent']
                rad = self.silo_data['r']
                ht = self.silo_data['h']
                
                total_vol = math.pi * (rad**2) * ht
                curr_vol = total_vol * (lvl/100.0)
                mass = curr_vol * 0.78 
                
                self._update_visuals(lvl)
                self.lbl_vol.config(text=f"{curr_vol:.1f} m³")
                self.lbl_mass.config(text=f"{mass:.1f} t")
                
                # --- ALERT LOGIC ---
                issues = []
                temp_alert = latest['temp_c'] > self.silo_data['tt']
                hum_alert = latest['humidity'] > self.silo_data['tm']
                lvl_alert = lvl < self.silo_data['tl']
                
                if temp_alert: issues.append(f"HIGH TEMP ({latest['temp_c']:.1f}°C)")
                if hum_alert: issues.append(f"HIGH MOISTURE ({latest['humidity']:.1f}%)")
                if lvl_alert: issues.append("CRITICAL LOW LEVEL")
                
                if issues:
                    self.lbl_status.config(text=f"⚠ ALERT: {', '.join(issues)}", foreground=self.colors['danger'])
                else:
                    self.lbl_status.config(text="● SYSTEM NORMAL", foreground=self.colors['success'])

                # GRAIN CONDITION LOGIC (SPOILAGE RISK)
                if temp_alert or hum_alert:
                    self.lbl_cond.config(text="Warning: Spoilage Risk", foreground=self.colors['danger'])
                elif lvl_alert:
                    self.lbl_cond.config(text="Optimal (Refill Needed)", foreground=self.colors['warning'])
                else:
                    self.lbl_cond.config(text="Optimal", foreground=self.colors['success'])

                hr = datetime.datetime.now().hour
                bat = 100 - (hr % 5) 
                self.lbl_battery.config(text=f"{bat}% (Good)")

                hist = get_history(self.current_silo_id, limit=48)
                times = [h['timestamp'] for h in hist]
                levels = [h['level_percent'] for h in hist]
                temps = [h['temp_c'] for h in hist]
                
                self.ax.clear()
                self.ax.set_facecolor(self.colors['bg_input'])
                self.ax.plot(times, levels, color=self.colors['accent'], label='Level %', linewidth=2)
                self.ax.plot(times, temps, color='#f472b6', label='Temp °C', linewidth=2)
                self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                self.ax.grid(color=self.colors['bg_card'], linestyle='--')
                self.ax.legend(facecolor=self.colors['bg_card'], labelcolor='white')
                self.canvas_chart.draw()
                
                # EST DAYS LOGIC
                if len(hist) > 5:
                    start_lvl = hist[0]['level_percent']
                    end_lvl = hist[-1]['level_percent']
                    hours = (hist[-1]['timestamp'] - hist[0]['timestamp']).total_seconds() / 3600.0
                    drop = start_lvl - end_lvl 
                    
                    if drop > 0.5 and hours > 0.05:
                         rate_per_hour = drop / hours
                         hours_left = lvl / rate_per_hour
                         days = hours_left / 24.0
                         self.lbl_days.config(text=f"{days:.1f} Days")
                    else:
                        if lvl < 20.0:
                             self.lbl_days.config(text="Stable (Low Level)", foreground=self.colors['danger'])
                        else:
                             self.lbl_days.config(text="Stable", foreground=self.colors['warning'])
                else:
                    self.lbl_days.config(text="Calculating...")

        if not single_shot:
            self.after(5000, self.update_loop)

if __name__ == "__main__":
    ensure_db()
    if SIMULATED:
        threading.Thread(target=simulator_thread, daemon=True).start()
    app = SiloManagementApp()
    app.mainloop()