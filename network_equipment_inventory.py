import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

DB_FILE = "network_inventory.db"

DEVICE_TYPES = [
    "Router", "Switch", "Firewall", "Access Point", "Modem",
    "Server", "Printer", "IP Phone", "UPS", "Camera",
    "Patch Panel", "Controller", "Other"
]

STATUSES = ["In Use", "Not Deployed", "Faulty", "Retired"]


class InventoryApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Network Equipment Inventory")
        self.root.geometry("1250x760")
        self.root.minsize(1050, 650)

        self.selected_id = None
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.create_database()

        self.vars = {
            "name": tk.StringVar(),
            "device_type": tk.StringVar(),
            "maker": tk.StringVar(),
            "model": tk.StringVar(),
            "serial_number": tk.StringVar(),
            # "barcode": tk.StringVar(),
            "mac_address": tk.StringVar(),
            "status": tk.StringVar(value="Not Deployed"),
            "location": tk.StringVar(),
            "ip_address": tk.StringVar(),
        }
        self.search_var = tk.StringVar()

        self.build_ui()
        self.load_devices()

        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def create_database(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                device_type TEXT NOT NULL,
                maker TEXT,
                model TEXT,
                serial_number TEXT UNIQUE,
                # barcode TEXT UNIQUE,
                mac_address TEXT,
                status TEXT NOT NULL,
                location TEXT,
                ip_address TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Section.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("Treeview", rowheight=28)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"))

        # Header
        header = ttk.Frame(self.root, padding=(18, 14))
        header.pack(fill="x")
        ttk.Label(header, text="Network Equipment Inventory",
                  style="Title.TLabel").pack(side="left")
        ttk.Label(
            header,
            text="USB barcode scanners work as keyboard input",
            foreground="#555555"
        ).pack(side="right")

        # Main content
        main = ttk.Frame(self.root, padding=(18, 0, 18, 12))
        main.pack(fill="both", expand=True)

        # Form
        form = ttk.LabelFrame(main, text="Device Details", padding=14)
        form.pack(fill="x")

        fields = [
            ("Device Name *", "name"),
            ("Device Type *", "device_type"),
            ("Maker", "maker"),
            ("Model", "model"),
            ("Serial Number", "serial_number"),
            # ("Barcode / Asset Tag", "barcode"),
            ("MAC Address", "mac_address"),
            ("Status *", "status"),
            ("Location", "location"),
            ("IP Address", "ip_address"),
        ]

        for i, (label, key) in enumerate(fields):
            row = i // 2
            col = (i % 2) * 2

            ttk.Label(form, text=label).grid(
                row=row, column=col, sticky="w", padx=(0, 8), pady=6
            )

            if key == "device_type":
                widget = ttk.Combobox(
                    form, textvariable=self.vars[key],
                    values=DEVICE_TYPES, state="readonly", width=30
                )
            elif key == "status":
                widget = ttk.Combobox(
                    form, textvariable=self.vars[key],
                    values=STATUSES, state="readonly", width=30
                )
            else:
                widget = ttk.Entry(form, textvariable=self.vars[key], width=34)

            widget.grid(row=row, column=col + 1, sticky="ew", pady=6)

            if key == "barcode":
                widget.bind("<Return>", self.barcode_scanned)
                self.barcode_entry = widget
            elif key == "serial_number":
                widget.bind("<Return>", self.serial_scanned)

        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        # Barcode help
        scan_frame = ttk.Frame(form)
        scan_frame.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(2, 6))
        ttk.Label(
            scan_frame,
            text="Barcode scanner: click the Barcode / Asset Tag field, scan the label, "
                 "then press Enter (most USB scanners send Enter automatically).",
            foreground="#555555"
        ).pack(side="left")

        # Buttons
        buttons = ttk.Frame(main, padding=(0, 10, 0, 8))
        buttons.pack(fill="x")

        ttk.Button(buttons, text="Save Device", command=self.save_device).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Update Selected", command=self.update_device).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete Selected", command=self.delete_device).pack(side="left", padx=6)
        ttk.Button(buttons, text="Clear Form", command=self.clear_form).pack(side="left", padx=6)
        ttk.Button(buttons, text="Focus Barcode Scanner", command=self.focus_barcode).pack(side="left", padx=6)
        ttk.Button(buttons, text="Export CSV", command=self.export_csv).pack(side="right")

        # Search
        search_frame = ttk.Frame(main)
        search_frame.pack(fill="x", pady=(0, 8))
        ttk.Label(search_frame, text="Search:").pack(side="left", padx=(0, 8))
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=45)
        search_entry.pack(side="left")
        search_entry.bind("<KeyRelease>", lambda e: self.load_devices())
        ttk.Button(search_frame, text="Clear Search",
                   command=lambda: (self.search_var.set(""), self.load_devices())
                   ).pack(side="left", padx=6)

        self.count_label = ttk.Label(search_frame, text="")
        self.count_label.pack(side="right")

        # Table
        table_frame = ttk.Frame(main)
        table_frame.pack(fill="both", expand=True)

        columns = (
            "id", "name", "type", "maker", "model", "serial", "barcode",
            "mac", "status", "location", "ip"
        )

        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="browse"
        )

        headings = {
            "id": "ID", "name": "Device Name", "type": "Type",
            "maker": "Maker", "model": "Model", "serial": "Serial Number",
            "barcode": "Barcode / Asset Tag", "mac": "MAC Address",
            "status": "Status", "location": "Location", "ip": "IP Address"
        }

        widths = {
            "id": 50, "name": 150, "type": 110, "maker": 110, "model": 110,
            "serial": 145, "barcode": 145, "mac": 140, "status": 105,
            "location": 120, "ip": 120
        }

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], minwidth=70, anchor="w")

        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")

        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.bind("<<TreeviewSelect>>", self.select_device)

    def barcode_scanned(self, event=None):
        code = self.vars["barcode"].get().strip()
        if not code:
            return "break"

        row = self.conn.execute(
            "SELECT * FROM devices WHERE barcode = ?", (code,)
        ).fetchone()

        if row:
            self.populate_form(row)
            messagebox.showinfo(
                "Device Found",
                f"Barcode {code} belongs to '{row['name']}'.\n"
                "The existing record has been loaded."
            )
        else:
            self.status_message(f"Scanned barcode: {code} — ready for a new record.")

        return "break"

    def serial_scanned(self, event=None):
        # Useful when a barcode label contains a serial number.
        serial = self.vars["serial_number"].get().strip()
        if not serial:
            return "break"

        row = self.conn.execute(
            "SELECT * FROM devices WHERE serial_number = ?", (serial,)
        ).fetchone()

        if row:
            self.populate_form(row)
            messagebox.showinfo(
                "Device Found",
                f"Serial number {serial} belongs to '{row['name']}'."
            )
        return "break"

    def focus_barcode(self):
        self.barcode_entry.focus_set()
        self.barcode_entry.select_range(0, tk.END)
        self.status_message("Barcode field focused. Scan the device label.")

    def status_message(self, text):
        self.count_label.config(text=text)

    def validate(self):
        name = self.vars["name"].get().strip()
        device_type = self.vars["device_type"].get().strip()
        status = self.vars["status"].get().strip()

        if not name:
            messagebox.showwarning("Required Field", "Device Name is required.")
            return False
        if not device_type:
            messagebox.showwarning("Required Field", "Device Type is required.")
            return False
        if not status:
            messagebox.showwarning("Required Field", "Status is required.")
            return False

        return True

    def values(self):
        return {key: var.get().strip() for key, var in self.vars.items()}

    def save_device(self):
        if not self.validate():
            return

        data = self.values()
        now = datetime.now().isoformat(timespec="seconds")

        try:
            self.conn.execute("""
                INSERT INTO devices (
                    name, device_type, maker, model, serial_number, barcode,
                    mac_address, status, location, ip_address, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["name"], data["device_type"], data["maker"], data["model"],
                data["serial_number"] or None, data["barcode"] or None,
                data["mac_address"], data["status"], data["location"],
                data["ip_address"], now, now
            ))
            self.conn.commit()
            self.load_devices()
            self.clear_form()
            messagebox.showinfo("Saved", "Device added to the inventory.")
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Duplicate Device",
                "The serial number or barcode already exists in the inventory."
            )

    def update_device(self):
        if self.selected_id is None:
            messagebox.showwarning("No Selection", "Select a device to update.")
            return
        if not self.validate():
            return

        data = self.values()
        now = datetime.now().isoformat(timespec="seconds")

        try:
            self.conn.execute("""
                UPDATE devices SET
                    name=?, device_type=?, maker=?, model=?, serial_number=?,
                    barcode=?, mac_address=?, status=?, location=?,
                    ip_address=?, updated_at=?
                WHERE id=?
            """, (
                data["name"], data["device_type"], data["maker"], data["model"],
                data["serial_number"] or None, data["barcode"] or None,
                data["mac_address"], data["status"], data["location"],
                data["ip_address"], now, self.selected_id
            ))
            self.conn.commit()
            self.load_devices()
            messagebox.showinfo("Updated", "Device record updated.")
        except sqlite3.IntegrityError:
            messagebox.showerror(
                "Duplicate Device",
                "The serial number or barcode belongs to another device."
            )

    def delete_device(self):
        if self.selected_id is None:
            messagebox.showwarning("No Selection", "Select a device to delete.")
            return

        if not messagebox.askyesno(
            "Confirm Delete",
            "Are you sure you want to permanently delete this device?"
        ):
            return

        self.conn.execute("DELETE FROM devices WHERE id=?", (self.selected_id,))
        self.conn.commit()
        self.load_devices()
        self.clear_form()

    def clear_form(self):
        self.selected_id = None
        for key, var in self.vars.items():
            var.set("")
        self.vars["status"].set("Not Deployed")
        for item in self.tree.selection():
            self.tree.selection_remove(item)

    def populate_form(self, row):
        self.selected_id = row["id"]
        for key in self.vars:
            self.vars[key].set(row[key] or "")

    def select_device(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return

        values = self.tree.item(selection[0], "values")
        device_id = values[0]

        row = self.conn.execute(
            "SELECT * FROM devices WHERE id=?", (device_id,)
        ).fetchone()

        if row:
            self.populate_form(row)

    def load_devices(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        search = self.search_var.get().strip()
        if search:
            like = f"%{search}%"
            rows = self.conn.execute("""
                SELECT * FROM devices
                WHERE name LIKE ? OR device_type LIKE ? OR maker LIKE ?
                   OR model LIKE ? OR serial_number LIKE ? OR barcode LIKE ?
                   OR mac_address LIKE ? OR status LIKE ? OR location LIKE ?
                   OR ip_address LIKE ?
                ORDER BY id DESC
            """, (like,) * 10).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM devices ORDER BY id DESC"
            ).fetchall()

        for row in rows:
            self.tree.insert("", "end", values=(
                row["id"], row["name"], row["device_type"], row["maker"],
                row["model"], row["serial_number"] or "", row["barcode"] or "",
                row["mac_address"], row["status"], row["location"],
                row["ip_address"]
            ))

        self.count_label.config(text=f"{len(rows)} device(s)")

    def export_csv(self):
        rows = self.conn.execute(
            "SELECT * FROM devices ORDER BY id"
        ).fetchall()

        if not rows:
            messagebox.showinfo("Export", "There are no devices to export.")
            return

        filename = filedialog.asksaveasfilename(
            title="Export Inventory",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not filename:
            return

        headers = [
            "ID", "Device Name", "Device Type", "Maker", "Model",
            "Serial Number", "Barcode / Asset Tag", "MAC Address",
            "Status", "Location", "IP Address", "Created At", "Updated At"
        ]

        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            for row in rows:
                writer.writerow([
                    row["id"], row["name"], row["device_type"], row["maker"],
                    row["model"], row["serial_number"] or "", row["barcode"] or "",
                    row["mac_address"], row["status"], row["location"],
                    row["ip_address"], row["created_at"], row["updated_at"]
                ])

        messagebox.showinfo("Export Complete", f"Inventory exported to:\n{filename}")

    def close(self):
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = InventoryApp(root)
    root.mainloop()
