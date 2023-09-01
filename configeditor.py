import tkinter as tk
from tkinter import ttk, Text, filedialog
import configparser
import re
import sys

class ConfigEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Mantella Config Editor")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        def read_config_file(filename):
            with open(filename, 'r') as file:
                return file.read()

        def extract_comments(config_text):
            comments = {}
            comment = ''
            section = None

            lines = config_text.split('\n')
            for line in lines:
                if line.startswith('[') and line.endswith(']'):
                    section = line[1:-1]
                    continue
                elif line.startswith('; '):
                    comment += line[1:] + '\n'
                    continue
                elif '=' in line:
                    parameter, value = line.split('=', 1)
                    parameter = parameter.strip()

                    if section is not None:
                        # save parameter's comment; without the last \n
                        comments[f"{section}.{parameter}"] = comment[0:-1]
                        comment = ''

            return comments

        config_text = read_config_file('config.ini')
        self.comments = extract_comments(config_text)

        for section in self.config.sections():
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=section)
            self.create_section_widgets(tab, section)

    def create_section_widgets(self, tab, section):
        options = self.config.options(section)
        row = 0

        for option in options:
            label = ttk.Label(tab, text=self.comments[f"{section}.{option}"])
            label.grid(row=row, column=0, padx=10, pady=2, sticky='w', columnspan=2)

            if section == "Paths":
                entry = ttk.Entry(tab, width=90)
                entry.insert(0, self.config.get(section, option))
            elif (option == 'prompt'):
                entry = Text(tab)
                entry.insert(1.0, self.config.get(section, option))
            else:
                entry = ttk.Entry(tab)
                entry.insert(0, self.config.get(section, option))
            entry.grid(row=row+1, column=0, padx=10, pady=5, sticky='w')

            if section == "Paths":
                browse_button = ttk.Button(tab, text="Browse...", command=lambda e=entry: self.browse_folder(e))
                browse_button.grid(row=row+1, column=1, padx=10, pady=5, sticky='e')

            row += 2

        save_button = ttk.Button(tab, text="Save", command=lambda: self.save_changes(section, tab))
        save_button.grid(row=row, column=0, padx=10, pady=10, sticky='w')

        close_button = ttk.Button(tab, text="Close", command=lambda: self.stop())
        close_button.grid(row=row, column=1, padx=10, pady=10, sticky='w')

    def browse_folder(self, entry):
        folder_path = filedialog.askdirectory()
        if folder_path:
            entry.delete(0, 'end')
            entry.insert(0, folder_path)

    def save_changes(self, section, tab):
        for widget in tab.winfo_children():
            if isinstance(widget, ttk.Entry):
                option = widget.grid_info()['row']
                value = widget.get()
                # self.config.set(section, self.config.options(section)[option], value)

        with open('config.ini', 'w') as configfile:
            for section in self.config.sections():
                configfile.write('['+section+']\n')

                options = self.config.options(section)
                for option in options:
                    commentlines = self.comments[f"{section}.{option}"].split('\n')
                    for commentline in commentlines:
                        configfile.write(';'+ commentline +'\n')

                    # quad whitespace for multiline parameters
                    optionvalue = self.config.get(section, option).replace('\n', '\n    ')
                    configfile.write(f"{option} = {optionvalue}\n\n")
                configfile.write('\n')

    def stop(self):
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = ConfigEditorApp(root)
    root.mainloop()
