import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import struct
from typing import Dict, List, Tuple, Optional, Any

# Constants
PROPERTY_NAME_OFFSET = -6
CHARACTERS = [
    "DEMI", "Lily", "Kili", "Ela", "Taron",
    "Sova", "Fortune", "Huntress", "Blythe", "Fow-Chan"
]
PROPERTY_KEYWORDS = ["Level", "CurrentXP", "BlueBallsXP", "UnspentPP", "CurrentDevotion", "DevotionLevel"]

class SaveFileHandler:
    """Handles reading and writing save file data."""
    
    @staticmethod
    def reverse_string(s: str) -> str:
        """Reverse a string."""
        return s[::-1]

    @staticmethod
    def unpack_int(byte_data: bytes) -> int:
        """Unpack 4 bytes to an integer (little-endian)."""
        if len(byte_data) < 4:
            raise ValueError("Not enough data to unpack an integer")
        return struct.unpack('<I', byte_data)[0]

    @staticmethod
    def int_to_bytes_le(n: int) -> bytes:
        """Convert integer to 4 bytes (little-endian)."""
        return struct.pack('<I', n)

    @staticmethod
    def overwrite_int(content: bytes, offset: int, new_val: int) -> bytes:
        """Overwrite an integer in the content."""
        return content[:offset] + SaveFileHandler.int_to_bytes_le(new_val) + content[offset + 4:]

    @staticmethod
    def read_int_properties(filename: str) -> Tuple[List[Dict[str, Any]], bytes]:
        """Read .sav file and extract integer properties."""
        with open(filename, "rb") as file:
            content = file.read()

        results = []
        i = 0
        while i < len(content):
            start_pos = content.find(b"IntProperty", i)
            if start_pos == -1:
                break

            name_start_pos = start_pos + PROPERTY_NAME_OFFSET
            name_end_pos = name_start_pos
            while name_end_pos > 0 and content[name_end_pos:name_end_pos + 1] != b"\0":
                name_end_pos -= 1
            name_end_pos += 1

            if name_end_pos > 0:
                raw_name = content[name_end_pos:start_pos + 1].decode('utf-8')
                prop_name = SaveFileHandler.reverse_string(raw_name)

                int_pos = start_pos + len("IntProperty") + 1
                to_data_length = SaveFileHandler.unpack_int(content[int_pos:int_pos + 4])
                int_pos += 4 + to_data_length

                start_of_data = int_pos + 1

                try:
                    value = SaveFileHandler.unpack_int(content[start_of_data:start_of_data + 4])
                    results.append({
                        'name': SaveFileHandler.reverse_string(prop_name),
                        'value': value,
                        'data_start': start_of_data
                    })
                except ValueError as e:
                    print(f"Error unpacking value at position {start_of_data}: {e}")

            i = start_pos + 1

        return results, content


class CharacterPropertyManager:
    """Manages character property data and relationships."""
    
    @staticmethod
    def get_unlocked_characters(properties: List[Dict[str, Any]]) -> Dict[str, bool]:
        """Determine which characters are unlocked based on property counts."""
        character_property_counts = {char: 0 for char in CHARACTERS}
        keyword_occurrence_counters = {key: 0 for key in PROPERTY_KEYWORDS}

        for prop in properties:
            prop_name_parts = prop['name'].split('_')
            for key in PROPERTY_KEYWORDS:
                if prop_name_parts[0] in key:
                    index = keyword_occurrence_counters[key]
                    if index < len(CHARACTERS):
                        character_property_counts[CHARACTERS[index]] += 1
                        keyword_occurrence_counters[key] += 1
                    break

        return {
            char: (character_property_counts[char] >= len(PROPERTY_KEYWORDS))
            for char in CHARACTERS
        }

    @staticmethod
    def build_character_property_table(properties: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """Organize properties by character and keyword."""
        table = {char: {} for char in CHARACTERS}
        keyword_occurrence_counters = {key: 0 for key in PROPERTY_KEYWORDS}

        for prop in properties:
            prop_name_parts = prop['name'].split('_')
            for key in PROPERTY_KEYWORDS:
                if prop_name_parts[0] in key:
                    occurrence_index = keyword_occurrence_counters[key]
                    if occurrence_index < len(CHARACTERS):
                        character_name = CHARACTERS[occurrence_index]
                        table[character_name][key] = {
                            **prop,
                            'display_name': f"{key} ({occurrence_index + 1})"
                        }
                        keyword_occurrence_counters[key] += 1
                    break

        return table

def resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

class SaveEditorUI:
    """Main application UI for the save editor."""
    
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Subverse Save Editor")

        # Initialize instance variables
        self.filepath = ""
        self.savepath = ""
        self.properties: List[Dict[str, Any]] = []
        self.content = b""
        self.edited_values: Dict[str, int] = {}
        self.file_loaded = False
        self.property_labels: Dict[str, tk.Label] = {}
        self.property_entries: Dict[str, tk.Entry] = {}
        self.character_var: Optional[tk.StringVar] = None
        self.character_dropdown: Optional[tk.OptionMenu] = None

        self.create_widgets()
        self.disable_save_button()

        self.set_window_icon()

    def set_window_icon(self):
        icon_path = resource_path("icon.ico")
        self.root.iconbitmap(icon_path)

    def create_widgets(self) -> None:
        """Create and arrange all UI widgets."""
        # File selection widgets
        tk.Label(self.root, text="Load .sav file").grid(row=0, column=0)
        self.file_entry = tk.Entry(self.root, width=40)
        self.file_entry.grid(row=0, column=1)
        tk.Button(self.root, text="Browse", command=self.open_file_dialog).grid(row=0, column=2)

        # Save widgets
        tk.Label(self.root, text="Save as").grid(row=1, column=0)
        self.save_entry = tk.Entry(self.root, width=40)
        self.save_entry.grid(row=1, column=1)
        self.save_button = tk.Button(self.root, text="Apply & Save", command=self.save_file)
        self.save_button.grid(row=1, column=2)

        # Scrollable properties area
        self.scroll_frame = tk.Frame(self.root)
        self.scroll_frame.grid(row=2, column=0, columnspan=3, pady=10, sticky="nsew")

        self.canvas = tk.Canvas(self.scroll_frame)
        self.scrollbar = tk.Scrollbar(self.scroll_frame, orient="vertical", command=self.canvas.yview)
        self.property_frame = tk.Frame(self.canvas)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.canvas.create_window((0, 0), window=self.property_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Configure grid weights
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.scroll_frame.grid_rowconfigure(0, weight=1)
        self.scroll_frame.grid_columnconfigure(0, weight=1)

    def disable_save_button(self) -> None:
        """Disable the save button until a file is loaded."""
        self.save_button.config(state=tk.DISABLED)

    def enable_save_button(self) -> None:
        """Enable the save button when a file is loaded."""
        self.save_button.config(state=tk.NORMAL)

    def open_file_dialog(self) -> None:
        """Handle file selection and loading."""
        self.clear_ui()
        file_path = filedialog.askopenfilename(filetypes=[("Save Files", "*.sav")])
        if file_path:
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, file_path)
            self.save_entry.delete(0, tk.END)
            self.save_entry.insert(0, file_path)
            
            try:
                self.properties, self.content = SaveFileHandler.read_int_properties(file_path)
                self.edited_values = {p['name']: p['value'] for p in self.properties}
                self.display_properties()
                self.file_loaded = True
                self.enable_save_button()
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load file: {str(e)}")
                self.file_loaded = False
                self.disable_save_button()

    def clear_ui(self) -> None:
        """Clear all UI elements related to properties."""
        self.properties = []
        self.edited_values = {}
        self.content = b""
        self.file_loaded = False

        # Clear property widgets
        for widget in self.property_frame.winfo_children():
            widget.destroy()

        self.property_labels = {}
        self.property_entries = {}

    def display_properties(self) -> None:
        """Display character selection and properties."""
        unlocked_map = CharacterPropertyManager.get_unlocked_characters(self.properties)
        display_names = [
            f"{char} {'(Not Unlocked)' if not unlocked_map[char] else ''}" 
            for char in CHARACTERS
        ]

        self.character_var = tk.StringVar(self.root)
        self.character_var.set(display_names[0])
        self.character_dropdown = tk.OptionMenu(
            self.property_frame, 
            self.character_var, 
            *display_names, 
            command=lambda name: self.update_properties(name.split()[0])
        )
        self.character_dropdown.grid(row=0, column=0, columnspan=3, pady=5)

        self.update_properties(CHARACTERS[0])

    def update_properties(self, selected_character: str) -> None:
        """Update displayed properties for the selected character."""
        # Clear previous property widgets
        for widget in self.property_frame.winfo_children()[1:]:
            widget.destroy()

        property_table = CharacterPropertyManager.build_character_property_table(self.properties)
        props_for_char = property_table.get(selected_character, {})

        for row, key in enumerate(PROPERTY_KEYWORDS, start=1):
            if key in props_for_char:
                prop = props_for_char[key]
                self.create_property_widgets(row, prop)

        self.property_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

    def create_property_widgets(self, row: int, prop: Dict[str, Any]) -> None:
        """Create widgets for a single property."""
        label = tk.Label(self.property_frame, text=prop.get('display_name', prop['name']), anchor='w')
        label.grid(row=row, column=0, sticky='w', padx=5, pady=2)

        entry = tk.Entry(self.property_frame, width=20)
        entry.insert(0, str(prop['value']))
        entry.grid(row=row, column=1, padx=5, pady=2)

        self.property_labels[prop['name']] = label
        self.property_entries[prop['name']] = entry

        # Set up change tracking
        entry_var = tk.StringVar()
        entry_var.set(str(prop['value']))
        entry.config(textvariable=entry_var)
        entry_var.trace_add("write", 
            lambda *args, lbl=label: self.mark_property_changed(lbl))

        # Apply button
        apply_btn = tk.Button(
            self.property_frame, 
            text="Apply", 
            command=lambda: self.apply_property_change(entry, prop))
        apply_btn.grid(row=row, column=2, padx=5, pady=2)

    def mark_property_changed(self, label: tk.Label) -> None:
        """Mark a property as changed in the UI."""
        current_text = label.cget("text")
        if not current_text.startswith("*"):
            label.config(text=f"* {current_text.strip()}")

    def apply_property_change(self, entry: tk.Entry, prop_info: Dict[str, Any]) -> None:
        """Apply a single property change."""
        try:
            new_val = int(entry.get())
            self.content = SaveFileHandler.overwrite_int(
                self.content, 
                prop_info['data_start'], 
                new_val
            )
            messagebox.showinfo(
                "Applied", 
                f"Applied new value {new_val} to {prop_info['name']}"
            )
        except ValueError:
            messagebox.showwarning(
                "Invalid", 
                f"Enter a valid integer for {prop_info['name']}"
            )

    def save_file(self) -> None:
        """Handle file saving."""
        if not self.file_loaded:
            messagebox.showwarning("Warning", "No file loaded.")
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".sav",
            filetypes=[("Save Files", "*.sav")],
            initialfile=self.save_entry.get()
        )
        
        if save_path:
            try:
                with open(save_path, "wb") as file:
                    file.write(self.content)
                messagebox.showinfo("Success", f"File saved to {save_path}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {str(e)}")


def main():
    root = tk.Tk()
    app = SaveEditorUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()