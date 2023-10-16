import tkinter as tk
from tkinter import ttk, Text, filedialog
import configparser
import re
import sys
import subprocess

class MantellaConfigEditor:
    def __init__(self, root):
        self.root = root
        self.root.title("Mantella Config Editor")

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True)

        self.config = configparser.ConfigParser()
        self.config.read('config.ini')

        self.widget_values = {}

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
                elif line.startswith('# '):
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

        # Create buttons for the entire window (common across all tabs)
        self.create_buttons()

    def create_section_widgets(self, tab, section):
        options = self.config.options(section)
        row = 0

        for option in options:
            label = ttk.Label(tab, text=self.comments[f"{section}.{option}"])
            label.grid(row=row, column=0, padx=10, pady=2, sticky='w', columnspan=2)

            # Paths section has file browsing
            if section == "Paths" and option.endswith('_folder'):
                entry = ttk.Entry(tab, width=90)
                entry.insert(0, self.config.get(section, option))
            # prompt option is a multiline string
            elif (option == 'prompt' or option == 'system_message'):
                entry = Text(tab)
                entry.insert(1.0, self.config.get(section, option))
            else:
                entry = ttk.Entry(tab)
                entry.insert(0, self.config.get(section, option))
            entry.grid(row=row+1, column=0, padx=10, pady=5, sticky='w')
            self.widget_values[f"{section}.{option}"] = entry

            # add Browse button for widgets under Paths
            if section == "Paths" and option.endswith('_folder'):
                browse_button = ttk.Button(tab, text="Browse...", command=lambda e=entry: self.browse_folder(e))
                browse_button.grid(row=row+1, column=1, padx=10, pady=5, sticky='e')

            row += 2

    def create_buttons(self):
        # Create buttons for the entire window (common across all tabs)
        buttons_frame = ttk.Frame(self.root)
        buttons_frame.pack(side='bottom', fill='both', expand=True)

        # Save widget values to config.ini button
        save_button = ttk.Button(buttons_frame, text="Save All", command=lambda: self.save_all_changes())
        save_button.pack(side='left', padx=10, pady=10)

        # Exit button
        exit_button = ttk.Button(buttons_frame, text="Exit", command=lambda: self.exit())
        exit_button.pack(side='right', padx=10, pady=10)

        # Save widget values to config.ini and stop button
        save_and_stop_button = ttk.Button(buttons_frame, text="Save All and Run", command=lambda: [self.save_all_changes(), self.stop()])
        save_and_stop_button.pack(side='right', padx=10, pady=10)

    def browse_folder(self, entry):
        folder_path = filedialog.askdirectory()
        if folder_path:
            entry.delete(0, 'end')
            entry.insert(0, folder_path)

    # save the values of all widgets to self.config
    def save_all_changes(self):
        for section in self.config.sections():
            options = self.config.options(section)
            for option in options:
                # prompt option is a multiline string
                if (option == 'prompt') or (option == 'system_message'):
                    self.config.set(section, option, self.widget_values[f"{section}.{option}"].get(1.0, 'end-1c'))
                else:
                    self.config.set(section, option, self.widget_values[f"{section}.{option}"].get())

        self.write_to_config_preserve_comments();

    # write directly to config file in order to preserve config comments; config.write does not save comments
    def write_to_config_preserve_comments(self):
        with open('config_edited.ini', 'w') as configfile:
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

        # test if config_edited.ini is a parsable INI file and if it is then overwrite config.ini with config_edited.ini
        try:
            configparser.ConfigParser().read('config_edited.ini')
            subprocess.run('move config_edited.ini config.ini', shell=True)
            print("config.ini saved successfully.")
        except Exception as e:
            print(f"config_edited.ini is not a valid INI file. Please fix the errors and try again. {e}")

    def stop(self):
        self.root.destroy()

    def exit(self):
        sys.exit(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = MantellaConfigEditor(root)
    root.mainloop()

def start():
    root = tk.Tk()
    app = MantellaConfigEditor(root)
    root.mainloop()