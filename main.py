import os
import sys
import tkinter as tk
import tkinter.ttk as ttk
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
MISC_KEYWORDS = ["BIO", "Tech", "Credits", "CheckedTrophyCount", "PandoraUnlockTriggerTally"]

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
                raw_name = content[name_end_pos:start_pos].decode('utf-8')
                prop_name = SaveFileHandler.reverse_string(raw_name)
                prop_name = ''.join(c for c in prop_name if c.isprintable())

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
    """Get absolute path to resource, works for dev and for PyInstaller"""
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

        self.root.geometry("1000x600")
        root.tk.call('tk', 'scaling', 2)

        self.filepath = ""
        self.savepath = ""
        self.properties: List[Dict[str, Any]] = []
        self.content = b""
        self.edited_values: Dict[str, int] = {}
        self.file_loaded = False
        self.property_labels: Dict[str, tk.Label] = {}
        self.property_entries: Dict[str, tk.Entry] = {}
        self.character_var: Optional[tk.StringVar] = None
        self.character_dropdown: Optional[ttk.OptionMenu] = None

        self.set_window_icon()

        self.create_widgets()
        self.disable_save_button()

    def set_window_icon(self):
        """Set the application window icon."""
        try:
            icon_path = resource_path("icon.ico")
            self.root.iconbitmap(icon_path)
        except:
            pass

    def create_widgets(self) -> None:
        """Create and arrange all UI widgets."""

        ttk.Label(self.root, text="Load .sav file").grid(row=0, column=0, padx=5, pady=5)
        self.file_entry = ttk.Entry(self.root, width=40)
        self.file_entry.grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(self.root, text="Browse", command=self.open_file_dialog).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(self.root, text="Save as").grid(row=1, column=0, padx=5, pady=5)
        self.save_entry = ttk.Entry(self.root, width=40)
        self.save_entry.grid(row=1, column=1, padx=5, pady=5)
        self.save_button = ttk.Button(self.root, text="Apply & Save", command=self.save_file)
        self.save_button.grid(row=1, column=2, padx=5, pady=5)

        self.tab_control = ttk.Notebook(self.root)
        self.tab_control.grid(row=2, column=0, columnspan=3, sticky="nsew", padx=5, pady=5)

        self.character_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.character_tab, text="Characters")
        self.create_character_tab()

        self.misc_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.misc_tab, text="MISC")
        self.create_misc_tab()

        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

    def create_character_tab(self):
        """Create the character properties tab."""
       
        self.char_scroll_frame = ttk.Frame(self.character_tab)
        self.char_scroll_frame.pack(fill="both", expand=True)

        self.char_canvas = tk.Canvas(self.char_scroll_frame)
        self.char_scrollbar = ttk.Scrollbar(
            self.char_scroll_frame,
            orient="vertical",
            command=self.char_canvas.yview
        )
        self.char_property_frame = ttk.Frame(self.char_canvas)

        self.char_canvas.pack(side="left", fill="both", expand=True)
        self.char_scrollbar.pack(side="right", fill="y")
        self.char_canvas.create_window((0, 0), window=self.char_property_frame, anchor="nw")
        self.char_canvas.configure(yscrollcommand=self.char_scrollbar.set)

        self.char_property_frame.bind("<Configure>", lambda e: self.char_canvas.configure(scrollregion=self.char_canvas.bbox("all")))
        self.char_canvas.bind_all("<MouseWheel>", lambda e: self.char_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        self.character_var = tk.StringVar()
        self.character_dropdown = ttk.OptionMenu(
            self.char_property_frame,
            self.character_var,
            "",
            *CHARACTERS,
            command=lambda name: self.update_character_properties(name)
        )
        self.character_dropdown.grid(row=0, column=0, columnspan=3, pady=5)

    def create_misc_tab(self):
        """Create the MISC properties tab."""

        self.misc_scroll_frame = ttk.Frame(self.misc_tab)
        self.misc_scroll_frame.pack(fill="both", expand=True)

        self.misc_canvas = tk.Canvas(self.misc_scroll_frame)
        self.misc_scrollbar = ttk.Scrollbar(
            self.misc_scroll_frame,
            orient="vertical",
            command=self.misc_canvas.yview
        )
        self.misc_property_frame = ttk.Frame(self.misc_canvas)

        self.misc_canvas.pack(side="left", fill="both", expand=True)
        self.misc_scrollbar.pack(side="right", fill="y")
        self.misc_canvas.create_window((0, 0), window=self.misc_property_frame, anchor="nw")
        self.misc_canvas.configure(yscrollcommand=self.misc_scrollbar.set)

        self.misc_property_frame.bind("<Configure>", lambda e: self.misc_canvas.configure(scrollregion=self.misc_canvas.bbox("all")))
        self.misc_canvas.bind_all("<MouseWheel>", lambda e: self.misc_canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        ttk.Label(
            self.misc_property_frame,
            text="Common Properties",
            font=('Helvetica', 10, 'bold')
        ).grid(row=0, column=0, columnspan=3, pady=5, sticky="w")

        ttk.Label(
            self.misc_property_frame,
            text="Advanced Properties (Unsafe)",
            font=('Helvetica', 10, 'bold')
        ).grid(row=100, column=0, columnspan=3, pady=5, sticky="w")

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

        for widget in self.char_property_frame.winfo_children()[1:]:
            widget.destroy()

        for widget in self.misc_property_frame.winfo_children()[2:]:
            if isinstance(widget, (ttk.Label, ttk.Entry, ttk.Button)):
                widget.destroy()

        self.property_labels = {}
        self.property_entries = {}

    def display_properties(self) -> None:
        """Display all properties in their respective tabs."""
        unlocked_map = CharacterPropertyManager.get_unlocked_characters(self.properties)
        display_names = [
            f"{char} {'(Locked)' if not unlocked_map[char] else ''}" 
            for char in CHARACTERS
        ]
        
        menu = self.character_dropdown['menu']
        menu.delete(0, 'end')
        for name in display_names:
            menu.add_command(
                label=name,
                command=lambda n=name: [
                    self.character_var.set(n),
                    self.update_character_properties(n.split()[0])
                ]
            )


        self.character_var.set(display_names[0])
        self.update_character_properties(display_names[0].split()[0])
        
        self.update_misc_properties()

    def update_character_properties(self, selected_character: str) -> None:
        normalized_character = selected_character.split(' ')[0]

        # Clear previous widgets (except dropdown)
        for widget in self.char_property_frame.winfo_children()[1:]:
            widget.destroy()

        property_table = CharacterPropertyManager.build_character_property_table(self.properties)
        props_for_char = property_table.get(normalized_character, {})

        row = 1
        for key in PROPERTY_KEYWORDS:
            if key in props_for_char:
                prop = props_for_char[key]
                self.create_character_property_widget(row, prop)
                row += 1

        self.char_property_frame.update_idletasks()
        self.char_canvas.config(scrollregion=self.char_canvas.bbox("all"))

    def create_character_property_widget(self, row: int, prop: Dict[str, Any]) -> None:
        """Create widgets for a character property."""
        label = ttk.Label(
            self.char_property_frame,
            text=prop.get('display_name', prop['name']),
            anchor='w'
        )
        label.grid(row=row, column=0, sticky='w', padx=5, pady=2)

        entry = ttk.Entry(self.char_property_frame, width=20)
        entry.insert(0, str(prop['value']))
        entry.config(state='normal')
        entry.grid(row=row, column=1, padx=5, pady=2)

        self.property_labels[prop['name']] = label
        self.property_entries[prop['name']] = entry

        # Set up change tracking
        entry_var = tk.StringVar()
        entry_var.set(str(prop['value']))
        entry.config(textvariable=entry_var)
        
        def on_change(*args, lbl=label):
            current_text = lbl.cget("text")
            if not current_text.startswith("*"):
                lbl.config(text=f"* {current_text}")
        
        entry_var.trace_add("write", on_change)

        # Apply button
        apply_btn = ttk.Button(
            self.char_property_frame,
            text="Apply",
            command=lambda: self.apply_property_change(entry, prop)
        )
        apply_btn.grid(row=row, column=2, padx=5, pady=2)

    def update_misc_properties(self) -> None:
        """Update MISC tab with all non-character properties."""
        # Clear previous widgets (keep headers)
        for widget in self.misc_property_frame.winfo_children()[2:]:
            if isinstance(widget, (ttk.Label, ttk.Entry, ttk.Button)):
                widget.destroy()

        # Organize properties
        misc_props = []
        advanced_props = []
        
        for prop in self.properties:
            prop_name = prop['name']
            is_misc = any(keyword in prop_name for keyword in MISC_KEYWORDS)
            is_character = any(
                keyword in prop_name and char in prop_name
                for keyword in PROPERTY_KEYWORDS
                for char in CHARACTERS
            )
            
            if is_misc and not is_character:
                misc_props.append(prop)
            elif not is_character:
                advanced_props.append(prop)
        
        # Display safe MISC properties
        row = 1
        for prop in misc_props:
            self.create_misc_property_widget(row, prop, False)
            row += 1
            
        # Display advanced properties
        row = 101
        for prop in advanced_props:
            self.create_misc_property_widget(row, prop, True)
            row += 1
            
        self.misc_property_frame.update_idletasks()
        self.misc_canvas.config(scrollregion=self.misc_canvas.bbox("all"))

    def create_misc_property_widget(self, row: int, prop: Dict[str, Any], is_advanced: bool) -> None:
        """Create widgets for a MISC property."""
        # Label
        label_text = prop.get('display_name', prop['name'])
        if is_advanced:
            label_text = f"* {label_text}"
            
        label = ttk.Label(
            self.misc_property_frame,
            text=label_text,
            foreground="red" if is_advanced else "black"
        )
        print(label_text)
        label.grid(row=row, column=0, sticky='w', padx=5, pady=2)
        
        # Create the entry widget
        entry = ttk.Entry(self.misc_property_frame, width=20)
        entry.grid(row=row, column=1, padx=5, pady=2)
        
        # Set the value directly
        entry.delete(0, tk.END)
        entry.insert(0, str(prop['value']))
        
        # Apply button
        apply_btn = ttk.Button(
            self.misc_property_frame,
            text="Apply",
            command=lambda: self.apply_property_change(entry, prop)
        )
        apply_btn.grid(row=row, column=2, padx=5, pady=2)
        
        # Change tracking
        def on_change(event):
            current_text = label.cget("text")
            if not current_text.startswith("*"):
                label.config(text=f"* {current_text}")
                
        entry.bind('<KeyRelease>', on_change)

    def create_character_property_widget(self, row: int, prop: Dict[str, Any]) -> None:
        """Create widgets for a character property."""
        label = ttk.Label(
            self.char_property_frame,
            text=prop.get('display_name', prop['name']),
            anchor='w'
        )
        label.grid(row=row, column=0, sticky='w', padx=5, pady=2)

        # Create the entry widget first
        entry = ttk.Entry(self.char_property_frame, width=20)
        entry.grid(row=row, column=1, padx=5, pady=2)
        
        # Set the value directly in the entry widget
        entry.delete(0, tk.END)
        entry.insert(0, str(prop['value']))
        
        # Store references
        self.property_labels[prop['name']] = label
        self.property_entries[prop['name']] = entry

        # Apply button
        apply_btn = ttk.Button(
            self.char_property_frame,
            text="Apply",
            command=lambda: self.apply_property_change(entry, prop)
        )
        apply_btn.grid(row=row, column=2, padx=5, pady=2)

        # Change tracking using direct entry access
        def on_change(event):
            current_text = label.cget("text")
            if not current_text.startswith("*"):
                label.config(text=f"* {current_text}")
        
        entry.bind('<KeyRelease>', on_change)

    def apply_property_change(self, entry: ttk.Entry, prop_info: Dict[str, Any]) -> None:
        """Apply a single property change."""
        try:
            new_val = int(entry.get())  # This is correct
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
