#!/usr/bin/env python3
"""
Manual Installation Wizard for FM Reloaded.
Provides step-by-step guidance for installing mods without manifests.
"""

import json
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from typing import Dict, List, Optional, Any

# Import our analysis system
try:
    from mod_detector import analyze_mod_source, generate_basic_manifest, ModType
    from core.path_resolver import fm_user_dir
except ImportError as e:
    print(f"Import error in installation wizard: {e}")
    # Fallback implementations
    def analyze_mod_source(path):
        return None
    def generate_basic_manifest(analysis, **kwargs):
        return {}
    ModType = type('ModType', (), {'MISC': 'misc', 'BEPINEX_PLUGIN': 'misc'})


class ManualInstallWizard:
    """Wizard dialog for manual mod installation."""
    
    def __init__(self, parent, mod_source_path: Path, on_complete_callback):
        """
        Initialize the wizard.
        
        Args:
            parent: Parent tkinter window
            mod_source_path: Path to mod source (directory or zip)
            on_complete_callback: Function to call with manifest data
        """
        self.parent = parent
        self.mod_source_path = mod_source_path
        self.on_complete_callback = on_complete_callback
        self.analysis = None
        self.current_step = 1
        self.total_steps = 4
        
        # Wizard data
        self.wizard_data = {
            'mod_name': '',
            'author': '',
            'version': '1.0.0',
            'description': '',
            'mod_type': 'misc',
            'install_target': None,
            'manifest': None
        }
        
        # Create wizard window
        self.wizard_window = tk.Toplevel(parent)
        self.wizard_window.title("Manual Installation Wizard")
        self.wizard_window.geometry("700x600")
        self.wizard_window.resizable(False, False)
        
        # Make window modal
        self.wizard_window.transient(parent)
        self.wizard_window.grab_set()
        
        # Analyze the mod source
        self._analyze_mod()
        
        # Create UI
        self._create_ui()
        
        # Center window on parent
        self._center_window()
        
    def _analyze_mod(self):
        """Analyze the mod source to detect its characteristics."""
        try:
            self.analysis = analyze_mod_source(self.mod_source_path)
            if self.analysis:
                # Pre-fill wizard data with analysis results
                self.wizard_data['mod_name'] = self.analysis.suggested_name
                self.wizard_data['author'] = self.analysis.additional_info.get('author', '')
                self.wizard_data['version'] = self.analysis.additional_info.get('detected_version', '1.0.0')
                self.wizard_data['description'] = self.analysis.additional_info.get('description', '')
                self.wizard_data['mod_type'] = self.analysis.detected_type
        except Exception as e:
            print(f"Analysis failed: {e}")
            # Continue with empty analysis
    
    def _center_window(self):
        """Center the wizard window on the parent."""
        if self.parent:
            parent_x = self.parent.winfo_x()
            parent_y = self.parent.winfo_y()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            
            window_width = 700
            window_height = 600
            
            x = parent_x + (parent_width // 2) - (window_width // 2)
            y = parent_y + (parent_height // 2) - (window_height // 2)
            
            self.wizard_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    
    def _create_ui(self):
        """Create the wizard UI."""
        # Main container
        main_frame = ttk.Frame(self.wizard_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(main_frame, text="Manual Mod Installation", 
                              font=("", 16, "bold"))
        title_label.pack(pady=(0, 20))
        
        # Progress indicator
        self.progress_var = tk.StringVar(value=f"Step {self.current_step} of {self.total_steps}")
        progress_label = ttk.Label(main_frame, textvariable=self.progress_var)
        progress_label.pack(pady=(0, 10))
        
        # Content area (changes based on current step)
        self.content_frame = ttk.Frame(main_frame)
        self.content_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Navigation buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        self.back_button = ttk.Button(button_frame, text="<< Back", 
                                   command=self._on_back)
        self.back_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.next_button = ttk.Button(button_frame, text="Next >>", 
                                   command=self._on_next)
        self.next_button.pack(side=tk.RIGHT, padx=(5, 0))
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", 
                                    command=self._on_cancel)
        self.cancel_button.pack(side=tk.RIGHT)
        
        # Show initial step
        self._show_step_1()
    
    def _clear_content_frame(self):
        """Clear all widgets from the content frame."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()
    
    def _show_step_1(self):
        """Show step 1: Mod analysis results."""
        self._clear_content_frame()
        self.current_step = 1
        self._update_progress()
        
        ttk.Label(self.content_frame, text="Step 1: Mod Analysis Results",
                 font=("", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        if self.analysis:
            # Analysis results
            results_frame = ttk.LabelFrame(self.content_frame, text="Detected Information", padding="10")
            results_frame.pack(fill=tk.X, pady=(0, 10))
            
            # Mod type and confidence
            type_text = f"Detected Type: {self.analysis.detected_type.title()}"
            ttk.Label(results_frame, text=type_text).pack(anchor=tk.W)
            
            confidence_text = f"Confidence: {self.analysis.confidence:.0%}"
            ttk.Label(results_frame, text=confidence_text).pack(anchor=tk.W)
            
            # Suggestions
            if self.analysis.install_suggestions:
                ttk.Label(results_frame, text="Suggestions:",
                         font=("", 10, "bold")).pack(anchor=tk.W, pady=(10, 5))
                
                for suggestion in self.analysis.install_suggestions:
                    ttk.Label(results_frame, text=f"• {suggestion}",
                             wraplength=500).pack(anchor=tk.W, pady=2)
            
            # Warnings
            if self.analysis.warnings:
                warning_frame = ttk.LabelFrame(self.content_frame, text="Warnings", padding="10")
                warning_frame.pack(fill=tk.X, pady=(10, 0))
                
                for warning in self.analysis.warnings:
                    ttk.Label(warning_frame, text=f"⚠ {warning}",
                             foreground="orange", wraplength=500).pack(anchor=tk.W, pady=2)
        else:
            ttk.Label(self.content_frame, text="Could not analyze the mod files.",
                     foreground="red").pack(pady=50)
            ttk.Label(self.content_frame, text="You'll need to provide all information manually.",
                     wraplength=500).pack()
        
        # Update button states
        self.next_button.config(state=tk.NORMAL)
        self.back_button.config(state=tk.DISABLED)
    
    def _show_step_2(self):
        """Show step 2: Basic mod information."""
        self._clear_content_frame()
        self.current_step = 2
        self._update_progress()
        
        ttk.Label(self.content_frame, text="Step 2: Mod Information",
                 font=("", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Form fields
        form_frame = ttk.Frame(self.content_frame)
        form_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Mod name
        ttk.Label(form_frame, text="Mod Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=self.wizard_data['mod_name'])
        name_entry = ttk.Entry(form_frame, textvariable=self.name_var, width=50)
        name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        
        # Author
        ttk.Label(form_frame, text="Author:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.author_var = tk.StringVar(value=self.wizard_data['author'])
        author_entry = ttk.Entry(form_frame, textvariable=self.author_var, width=50)
        author_entry.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        
        # Version
        ttk.Label(form_frame, text="Version:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.version_var = tk.StringVar(value=self.wizard_data['version'])
        version_entry = ttk.Entry(form_frame, textvariable=self.version_var, width=50)
        version_entry.grid(row=2, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        
        # Description
        ttk.Label(form_frame, text="Description:").grid(row=3, column=0, sticky=tk.NW, pady=5)
        self.description_text = tk.Text(form_frame, height=4, width=50)
        self.description_text.insert("1.0", self.wizard_data['description'])
        self.description_text.grid(row=3, column=1, sticky=tk.EW, pady=5, padx=(10, 0))
        
        form_frame.columnconfigure(1, weight=1)
        
        # Update button states
        self.next_button.config(state=tk.NORMAL)
        self.back_button.config(state=tk.NORMAL)
    
    def _show_step_3(self):
        """Show step 3: Mod type selection."""
        self._clear_content_frame()
        self.current_step = 3
        self._update_progress()
        
        ttk.Label(self.content_frame, text="Step 3: Mod Type",
                 font=("", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        ttk.Label(self.content_frame, text="Select the type of mod this is:",
                 wraplength=600).pack(anchor=tk.W, pady=(0, 10))
        
        # Type selection
        type_frame = ttk.Frame(self.content_frame)
        type_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.mod_type_var = tk.StringVar(value=self.wizard_data['mod_type'])
        
        mod_types = [
            ("misc", "Miscellaneous (General files)"),
            ("bepinex", "BepInEx Plugin"),
            ("ui", "UI/Bundle Mod"),
            ("graphics", "Graphics Mod"),
            ("tactics", "Tactics Mod"),
            ("skins", "Skin Mod"),
            ("audio", "Audio Mod"),
            ("database", "Database Mod")
        ]
        
        for i, (value, text) in enumerate(mod_types):
            ttk.Radiobutton(type_frame, text=text, value=value,
                          variable=self.mod_type_var).pack(anchor=tk.W, pady=2)
        
        # Type description
        self.type_desc_label = ttk.Label(self.content_frame, text="", wraplength=600)
        self.type_desc_label.pack(anchor=tk.W, pady=(10, 0))
        
        # Update type description when selection changes
        self.mod_type_var.trace('w', self._update_type_description)
        self._update_type_description()
        
        # Update button states
        self.next_button.config(state=tk.NORMAL)
        self.back_button.config(state=tk.NORMAL)
    
    def _update_type_description(self, *args):
        """Update the type description based on selection."""
        descriptions = {
            "misc": "General files that don't fit other categories. Files will be installed to various locations based on their paths.",
            "bepinex": "BepInEx plugins that modify game behavior. Files will be installed to BepInEx/plugins or BepInEx/core.",
            "ui": "UI modifications and bundle files. Files will be installed to the FM26 game data directory.",
            "graphics": "Graphics packs (kits, faces, logos, etc.). Files will be installed to Documents/FM26/graphics/.",
            "tactics": "Tactic files (.fmf). Files will be installed to Documents/FM26/tactics/.",
            "skins": "Skin modifications. Files will be installed to the FM26 skins directory.",
            "audio": "Audio modifications. Files will be installed to Documents/FM26/audio/.",
            "database": "Database and editor data files. Files will be installed to Documents/FM26/editor data/."
        }
        
        desc = descriptions.get(self.mod_type_var.get(), "")
        self.type_desc_label.config(text=desc)
    
    def _show_step_4(self):
        """Show step 4: Installation target and confirmation."""
        self._clear_content_frame()
        self.current_step = 4
        self._update_progress()
        
        ttk.Label(self.content_frame, text="Step 4: Installation Target",
                 font=("", 12, "bold")).pack(anchor=tk.W, pady=(0, 10))
        
        # Generate preview manifest
        self._generate_preview_manifest()
        
        # Show manifest preview
        manifest_frame = ttk.LabelFrame(self.content_frame, text="Generated Manifest", padding="10")
        manifest_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        manifest_text = tk.Text(manifest_frame, height=15, width=70, wrap=tk.WORD)
        manifest_text.pack(fill=tk.BOTH, expand=True)
        
        # Format and show manifest
        manifest_json = json.dumps(self.wizard_data['manifest'], indent=2)
        manifest_text.insert("1.0", manifest_json)
        manifest_text.config(state=tk.DISABLED)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(manifest_frame, orient=tk.VERTICAL, command=manifest_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        manifest_text.config(yscrollcommand=scrollbar.set)
        
        # Instructions
        instructions = ("This manifest will be created and the mod will be installed.\n\n"
                     "Review the manifest above and click 'Complete' to proceed,\n"
                     "or 'Back' to make changes.")
        ttk.Label(self.content_frame, text=instructions, wraplength=600).pack(pady=(10, 0))
        
        # Update button states
        self.next_button.config(text="Complete", state=tk.NORMAL)
        self.back_button.config(state=tk.NORMAL)
    
    def _generate_preview_manifest(self):
        """Generate the preview manifest from wizard data."""
        # Update wizard data from form
        self.wizard_data['mod_name'] = self.name_var.get().strip()
        self.wizard_data['author'] = self.author_var.get().strip()
        self.wizard_data['version'] = self.version_var.get().strip()
        self.wizard_data['description'] = self.description_text.get("1.0", "end-1c").strip()
        self.wizard_data['mod_type'] = self.mod_type_var.get()
        
        # Generate manifest
        if self.analysis:
            manifest = generate_basic_manifest(
                self.analysis,
                user_name=self.wizard_data['mod_name'],
                user_description=self.wizard_data['description']
            )
        else:
            # Basic manifest from user input only
            manifest = {
                "name": self.wizard_data['mod_name'] or "Unknown Mod",
                "version": self.wizard_data['version'] or "1.0.0",
                "type": self.wizard_data['mod_type'],
                "author": self.wizard_data['author'] or "Unknown",
                "description": self.wizard_data['description'] or "Manual installation",
                "files": []  # User will need to configure files manually
            }
        
        self.wizard_data['manifest'] = manifest
    
    def _update_progress(self):
        """Update the progress indicator."""
        self.progress_var.set(f"Step {self.current_step} of {self.total_steps}")
    
    def _on_back(self):
        """Handle back button click."""
        if self.current_step > 1:
            # Save current step data
            if self.current_step == 2:
                self.wizard_data['mod_name'] = self.name_var.get().strip()
                self.wizard_data['author'] = self.author_var.get().strip()
                self.wizard_data['version'] = self.version_var.get().strip()
                self.wizard_data['description'] = self.description_text.get("1.0", "end-1c").strip()
            elif self.current_step == 3:
                self.wizard_data['mod_type'] = self.mod_type_var.get()
            
            # Show previous step
            if self.current_step == 2:
                self._show_step_1()
            elif self.current_step == 3:
                self._show_step_2()
            elif self.current_step == 4:
                self._show_step_3()
                
                # Change button back to "Next"
                self.next_button.config(text="Next >>")
    
    def _on_next(self):
        """Handle next button click."""
        if self.current_step < self.total_steps:
            # Validate current step
            if not self._validate_current_step():
                return
            
            # Save current step data
            if self.current_step == 1:
                # Analysis step - no data to save
                pass
            elif self.current_step == 2:
                self.wizard_data['mod_name'] = self.name_var.get().strip()
                self.wizard_data['author'] = self.author_var.get().strip()
                self.wizard_data['version'] = self.version_var.get().strip()
                self.wizard_data['description'] = self.description_text.get("1.0", "end-1c").strip()
            elif self.current_step == 3:
                self.wizard_data['mod_type'] = self.mod_type_var.get()
            
            # Show next step
            if self.current_step == 1:
                self._show_step_2()
            elif self.current_step == 2:
                self._show_step_3()
            elif self.current_step == 3:
                self._show_step_4()
        else:
            # Complete step
            self._on_complete()
    
    def _validate_current_step(self) -> bool:
        """Validate the current step's data."""
        if self.current_step == 2:
            # Validate basic info
            if not self.name_var.get().strip():
                messagebox.showerror("Validation Error", "Mod name is required.")
                return False
            if not self.version_var.get().strip():
                messagebox.showerror("Validation Error", "Version is required.")
                return False
        
        return True
    
    def _on_complete(self):
        """Handle wizard completion."""
        try:
            # Generate final manifest
            self._generate_preview_manifest()
            
            # Validate manifest has required fields
            manifest = self.wizard_data['manifest']
            if not manifest.get('name'):
                messagebox.showerror("Error", "Mod name is required.")
                return
            
            if not manifest.get('files'):
                messagebox.showwarning("No Files", 
                                   "No files were detected for this mod.\n"
                                   "You'll need to configure the manifest manually after installation.")
            
            # Call completion callback
            if self.on_complete_callback:
                self.on_complete_callback(manifest)
            
            # Close wizard
            self.wizard_window.destroy()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to complete wizard: {e}")
    
    def _on_cancel(self):
        """Handle wizard cancellation."""
        if messagebox.askyesno("Cancel", "Are you sure you want to cancel the installation?"):
            self.wizard_window.destroy()
    
    def show(self):
        """Show the wizard."""
        self.wizard_window.mainloop()


def show_manual_install_wizard(parent, mod_source_path: Path, 
                           on_complete_callback) -> Optional[Dict]:
    """
    Show the manual installation wizard.
    
    Args:
        parent: Parent tkinter window
        mod_source_path: Path to mod source
        on_complete_callback: Callback function for completion
        
    Returns:
        Generated manifest dictionary or None if cancelled
    """
    result = []
    
    def callback(manifest):
        result.append(manifest)
    
    wizard = ManualInstallWizard(parent, mod_source_path, callback)
    wizard.show()
    
    return result[0] if result else None


def install_mod_without_manifest(mod_source_path: Path, parent_window=None) -> bool:
    """
    Install a mod that doesn't have a manifest using the wizard.
    
    Args:
        mod_source_path: Path to mod source
        parent_window: Parent window for dialogs
        
    Returns:
        True if installation succeeded, False otherwise
    """
    try:
        if not parent_window:
            # Create a dummy parent if none provided
            parent_window = tk.Tk()
            parent_window.withdraw()
        
        # Show wizard
        manifest = show_manual_install_wizard(parent_window, mod_source_path, None)
        
        if manifest:
            # Installation would continue here with the generated manifest
            messagebox.showinfo("Success", 
                             "Manifest generated successfully!\n\n"
                             "The mod can now be installed with the generated manifest.")
            return True
        
        return False
        
    except Exception as e:
        messagebox.showerror("Error", f"Manual installation failed: {e}")
        return False
