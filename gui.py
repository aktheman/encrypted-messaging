"""
Graphical User Interface (GUI) for the Encrypted Messaging App.
Built with CustomTkinter for a modern, cross-platform desktop experience.
"""

import sys
import os
import asyncio
import threading
import time
import tkinter as tk
from tkinter import messagebox, filedialog
from typing import Optional, Dict, List, Any, Callable
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from messaging import SecureMessenger

# Configure CustomTkinter appearance
ctk.set_appearance_mode("system")  # "light", "dark", or "system"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


class ContactListPanel(ctk.CTkScrollableFrame):
    """Left sidebar panel showing contacts and groups."""

    def __init__(self, master, messenger: SecureMessenger, on_contact_select: Callable, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger = messenger
        self.on_contact_select = on_contact_select
        self.selected_contact: Optional[str] = None
        self.selected_is_group: bool = False
        self.contact_buttons: Dict[str, ctk.CTkButton] = {}
        self.group_buttons: Dict[str, ctk.CTkButton] = {}
        self.all_contacts: Dict[str, Dict] = {}
        self.all_groups: Dict[str, Dict] = {}
        self.search_callback: Optional[Callable] = None

        self.grid_columnconfigure(0, weight=1)

        # Section labels
        self.contacts_label = ctk.CTkLabel(self, text="📇 CONTACTS", font=ctk.CTkFont(weight="bold", size=14))
        self.contacts_label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")

        self.contacts_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.contacts_frame.grid(row=1, column=0, padx=5, pady=(0, 10), sticky="ew")
        self.contacts_frame.grid_columnconfigure(0, weight=1)

        self.groups_label = ctk.CTkLabel(self, text="👥 GROUPS", font=ctk.CTkFont(weight="bold", size=14))
        self.groups_label.grid(row=2, column=0, padx=10, pady=(10, 5), sticky="w")

        self.groups_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.groups_frame.grid(row=3, column=0, padx=5, pady=(0, 10), sticky="ew")
        self.groups_frame.grid_columnconfigure(0, weight=1)

        # Initial load
        self.refresh_contacts()

        # Auto-refresh timer
        self._schedule_refresh()

    def set_search_callback(self, callback: Callable):
        """Set the search callback function."""
        self.search_callback = callback

    def _schedule_refresh(self):
        """Schedule periodic contact refresh."""
        self.after(2000, self._auto_refresh)

    def _auto_refresh(self):
        """Auto-refresh contacts and reschedule."""
        self.refresh_contacts()
        self._schedule_refresh()

    def _get_avatar(self, name: str) -> str:
        """Generate avatar initials from name."""
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1:
            return parts[0][:2].upper()
        return "?"

    def refresh_contacts(self):
        """Refresh the contact and group lists."""
        try:
            # Get contacts
            contacts = self.messenger.list_contacts()
            self.all_contacts = contacts

            # Get groups
            groups = self.messenger.list_groups()
            self.all_groups = groups

            self._render_contacts(contacts)
            self._render_groups(groups)

        except Exception as e:
            print(f"Error refreshing contacts: {e}")

    def _render_contacts(self, contacts: Dict):
        """Render contact buttons with optional filtering."""
        # Clear existing contact buttons
        for btn in self.contact_buttons.values():
            btn.destroy()
        self.contact_buttons.clear()

        # Recreate contact buttons
        row = 0
        for name, info in contacts.items():
            avatar = self._get_avatar(name)
            trust_level = self.messenger.contact_manager.get_contact_trust_level(name)
            if trust_level == 2:  # blocked
                trust_icon = "🔴 "
                fg_color = ("#ff4444", "#cc0000")
            elif trust_level == 1:  # trusted
                trust_icon = "🟢 "
                fg_color = ("#44aa44", "#00aa00")
            else:  # unknown
                trust_icon = "🟡 "
                fg_color = ("#ffaa00", "#ff8800")

            # Highlight if selected
            is_selected = (name == self.selected_contact and not self.selected_is_group)
            btn_fg = fg_color if is_selected else None

            # Create frame for avatar + name
            contact_frame = ctk.CTkFrame(self.contacts_frame, fg_color="transparent")
            contact_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")
            contact_frame.grid_columnconfigure(1, weight=1)

            # Avatar
            avatar_label = ctk.CTkLabel(
                contact_frame,
                text=avatar,
                width=28,
                height=28,
                font=ctk.CTkFont(size=11, weight="bold"),
                fg_color=("gray70", "gray30"),
                corner_radius=14
            )
            avatar_label.grid(row=0, column=0, padx=(5, 10), pady=2)

            # Name button
            btn = ctk.CTkButton(
                contact_frame,
                text=f"{trust_icon}{name}",
                anchor="w",
                height=32,
                font=ctk.CTkFont(size=12),
                fg_color=btn_fg,
                command=lambda n=name: self._on_contact_click(n, False)
            )
            btn.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
            self.contact_buttons[name] = btn

            # Right-click context menu
            btn.bind("<Button-3>", lambda e, n=name: self._show_contact_context_menu(e, n))

            row += 1

        # Handle empty state
        if not contacts:
            lbl = ctk.CTkLabel(self.contacts_frame, text="  (no contacts)", text_color="gray")
            lbl.grid(row=0, column=0, padx=10, pady=5, sticky="w")
            self.contact_buttons["_empty"] = lbl

    def _render_groups(self, groups: Dict):
        """Render group buttons with optional filtering."""
        # Clear existing group buttons
        for btn in self.group_buttons.values():
            btn.destroy()
        self.group_buttons.clear()

        # Recreate group buttons
        row = 0
        for name, info in groups.items():
            members = info.get("members", [])
            member_count = len(members)

            is_selected = (name == self.selected_contact and self.selected_is_group)
            btn_fg = ("#1f6aa5", "#144870") if is_selected else None

            # Create frame for group
            group_frame = ctk.CTkFrame(self.groups_frame, fg_color="transparent")
            group_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")
            group_frame.grid_columnconfigure(1, weight=1)

            # Group icon
            icon_label = ctk.CTkLabel(
                group_frame,
                text="👥",
                width=28,
                height=28,
                font=ctk.CTkFont(size=14),
            )
            icon_label.grid(row=0, column=0, padx=(5, 10), pady=2)

            # Name button
            btn = ctk.CTkButton(
                group_frame,
                text=f"{name} ({member_count} members)",
                anchor="w",
                height=32,
                font=ctk.CTkFont(size=12),
                fg_color=btn_fg,
                command=lambda n=name: self._on_contact_click(n, True)
            )
            btn.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
            self.group_buttons[name] = btn

            # Right-click context menu
            btn.bind("<Button-3>", lambda e, n=name: self._show_group_context_menu(e, n))

            row += 1

        # Handle empty state
        if not groups:
            lbl = ctk.CTkLabel(self.groups_frame, text="  (no groups)", text_color="gray")
            lbl.grid(row=0, column=0, padx=10, pady=5, sticky="w")
            self.group_buttons["_empty"] = lbl

    def filter_contacts(self, query: str):
        """Filter contacts and groups by search query."""
        if not query:
            # Show all
            self._render_contacts(self.all_contacts)
            self._render_groups(self.all_groups)
            return

        query = query.lower()
        filtered_contacts = {k: v for k, v in self.all_contacts.items() if query in k.lower()}
        filtered_groups = {k: v for k, v in self.all_groups.items() if query in k.lower()}
        self._render_contacts(filtered_contacts)
        self._render_groups(filtered_groups)

    def _on_contact_click(self, name: str, is_group: bool):
        """Handle contact/group selection."""
        self.selected_contact = name
        self.selected_is_group = is_group
        self.refresh_contacts()  # Re-render with selection highlight
        if self.on_contact_select:
            self.on_contact_select(name, is_group)

    def _show_contact_context_menu(self, event, name: str):
        """Show context menu for contact."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Trust", command=lambda: self._trust_contact(name))
        menu.add_command(label="Block", command=lambda: self._block_contact(name))
        menu.add_separator()
        menu.add_command(label="Remove", command=lambda: self._remove_contact(name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _show_group_context_menu(self, event, name: str):
        """Show context menu for group."""
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Add Member", command=lambda: self._add_group_member(name))
        menu.add_command(label="Remove Member", command=lambda: self._remove_group_member(name))
        menu.add_separator()
        menu.add_command(label="Manage Group", command=lambda: self._manage_group(name))
        menu.add_separator()
        menu.add_command(label="Delete Group", command=lambda: self._delete_group(name))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _trust_contact(self, name: str):
        """Trust a contact."""
        success = self.messenger.trust_contact(name)
        if success:
            self.refresh_contacts()
            messagebox.showinfo("Success", f"Contact '{name}' is now trusted")
        else:
            messagebox.showerror("Error", f"Failed to trust contact '{name}'")

    def _block_contact(self, name: str):
        """Block a contact."""
        success = self.messenger.block_contact(name)
        if success:
            self.refresh_contacts()
            messagebox.showinfo("Success", f"Contact '{name}' is now blocked")
        else:
            messagebox.showerror("Error", f"Failed to block contact '{name}'")

    def _remove_contact(self, name: str):
        """Remove a contact."""
        if messagebox.askyesno("Confirm", f"Remove contact '{name}'?"):
            success = self.messenger.remove_contact(name)
            if success:
                self.refresh_contacts()
                messagebox.showinfo("Success", f"Contact '{name}' removed")
            else:
                messagebox.showerror("Error", f"Failed to remove contact '{name}'")

    def _add_group_member(self, group_name: str):
        """Add member to group - opens dialog."""
        if hasattr(self.master, 'master') and hasattr(self.master.master, 'show_add_group_member_dialog'):
            self.master.master.show_add_group_member_dialog(group_name)

    def _remove_group_member(self, group_name: str):
        """Remove member from group - opens dialog."""
        if hasattr(self.master, 'master') and hasattr(self.master.master, 'show_remove_group_member_dialog'):
            self.master.master.show_remove_group_member_dialog(group_name)

    def _manage_group(self, group_name: str):
        """Manage group - opens dialog."""
        if hasattr(self.master, 'master') and hasattr(self.master.master, '_show_manage_group_dialog'):
            self.master.master._show_manage_group_dialog(group_name)

    def _delete_group(self, group_name: str):
        """Delete a group."""
        if messagebox.askyesno("Confirm", f"Delete group '{group_name}'?"):
            success = self.messenger.delete_group(group_name)
            if success:
                self.refresh_contacts()
                messagebox.showinfo("Success", f"Group '{group_name}' deleted")
            else:
                messagebox.showerror("Error", f"Failed to delete group '{group_name}'")


class MessageViewPanel(ctk.CTkTextbox):
    """Center panel displaying conversation messages."""

    def __init__(self, master, on_edit_message: Optional[Callable] = None,
                 on_delete_message: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger: Optional[SecureMessenger] = None
        self.current_contact: Optional[str] = None
        self.current_is_group: bool = False
        self.on_edit_message = on_edit_message
        self.on_delete_message = on_delete_message

        # Configure text tags for styling (no font option due to CustomTkinter scaling)
        self.tag_config("sent", foreground="#4a9eff", justify="right")
        self.tag_config("received", foreground="#4ade80", justify="left")
        self.tag_config("timestamp", foreground="gray")
        self.tag_config("encrypted", foreground="gray")
        self.tag_config("edited", foreground="#ffaa00")
        self.tag_config("deleted", foreground="#ff4444", overstrike=True)
        self.tag_config("system", foreground="gray")
        self.tag_config("ephemeral", foreground="#ffaa00")  # For TTL countdown

        # Make read-only
        self.configure(state="disabled", wrap="word")

        # Bind right-click for context menu
        self.bind("<Button-3>", self._show_message_context_menu)
        self.bind("<Control-e>", lambda e: self._on_edit_shortcut())
        self.bind("<Delete>", lambda e: self._on_delete_shortcut())

    def set_messenger(self, messenger: SecureMessenger):
        """Set the messenger instance."""
        self.messenger = messenger

    def set_conversation(self, contact_name: str, is_group: bool = False):
        """Set the current conversation to display."""
        self.current_contact = contact_name
        self.current_is_group = is_group
        self.clear()
        self.load_history()

    def clear(self):
        """Clear the message view."""
        self.configure(state="normal")
        self.delete("1.0", "end")
        self.configure(state="disabled")

    def load_history(self):
        """Load and display conversation history."""
        if not self.messenger or not self.current_contact:
            return

        try:
            history = self.messenger.get_conversation_history(self.current_contact, limit=100)
            if not history:
                self._append_system_message("No messages yet. Start the conversation!")
                return

            for msg in history:
                self.display_message(msg)

            # Scroll to bottom
            self.see("end")

        except Exception as e:
            self._append_system_message(f"Error loading history: {e}")

    def display_message(self, msg: Dict):
        """Display a single message."""
        direction = msg.get('direction', 'received')
        text = msg.get('text', '')
        timestamp = msg.get('timestamp', 0)
        is_group = msg.get('is_group', False)
        msg_id = msg.get('msg_id', '')
        ttl = msg.get('ttl', None)
        edited = msg.get('edited', False)
        deleted = msg.get('deleted', False)

        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))

        self.configure(state="normal")

        if direction == 'sent':
            # Sent message - right aligned, blue
            self.insert("end", f"[{time_str}] ", "timestamp")
            self.insert("end", "▶ You: ", "sent")
        else:
            # Received message - left aligned, green
            sender = self.current_contact if is_group else "Unknown"
            self.insert("end", f"[{time_str}] ", "timestamp")
            self.insert("end", f"◀ {sender}: ", "received")

        # Add TTL countdown for ephemeral messages
        if ttl and ttl > 0:
            remaining = ttl - (time.time() - timestamp)
            if remaining > 0:
                self.insert("end", f"⏳ {int(remaining)}s ", "ephemeral")
            else:
                self.insert("end", "💀 EXPIRED ", "ephemeral")

        # Check for special message types
        if deleted or text.startswith("[DELETED]"):
            self.insert("end", "[This message was deleted]\n", "deleted")
        elif edited or text.startswith("[EDITED]"):
            self.insert("end", text + " ✏️\n", "edited")
        elif text.startswith("[Message encrypted"):
            self.insert("end", text + "\n", "encrypted")
        elif text.startswith("[FILE]"):
            # File attachment - show with download option
            self.insert("end", text + " 📁\n", "encrypted")
        else:
            self.insert("end", text + "\n")

        # Store msg_id in the text widget for context menu
        # We'll use a custom approach: store in a dict mapping line to msg_id
        if not hasattr(self, '_msg_id_map'):
            self._msg_id_map = {}
        # Get the line number of the message we just inserted
        line_start = self.index("end-1c linestart")
        line_num = int(line_start.split(".")[0])
        self._msg_id_map[line_num] = msg_id

        self.configure(state="disabled")
        self.see("end")

    def add_message(self, sender: str, text: str, is_sent: bool = False):
        """Add a new message to the view."""
        time_str = time.strftime("%H:%M:%S")

        self.configure(state="normal")

        if is_sent:
            self.insert("end", f"[{time_str}] ", "timestamp")
            self.insert("end", "▶ You: ", "sent")
        else:
            self.insert("end", f"[{time_str}] ", "timestamp")
            self.insert("end", f"◀ {sender}: ", "received")

        self.insert("end", text + "\n")

        self.configure(state="disabled")
        self.see("end")

    def _append_system_message(self, text: str):
        """Append a system message."""
        self.configure(state="normal")
        self.insert("end", text + "\n", "system")
        self.configure(state="disabled")
        self.see("end")

    def update_ephemeral_timers(self):
        """Update TTL countdowns for ephemeral messages in current view."""
        if not self.messenger or not self.current_contact:
            return

        # Reload history to get updated TTL values
        self.clear()
        self.load_history()

    def _show_message_context_menu(self, event):
        """Show context menu for message at cursor position."""
        if not self.messenger or not self.current_contact:
            return

        # Get the line at cursor position
        index = self.index(f"@{event.x},{event.y}")
        line_num = int(index.split(".")[0])

        # Check if this line has a message ID
        if hasattr(self, '_msg_id_map') and line_num in self._msg_id_map:
            msg_id = self._msg_id_map[line_num]

            # Get message details
            history = self.messenger.get_conversation_history(self.current_contact, limit=100)
            msg_data = None
            for msg in history:
                if msg.get('msg_id', '') == msg_id:
                    msg_data = msg
                    break

            if not msg_data:
                return

            text = msg_data.get('text', '')
            is_sent = msg_data.get('direction') == 'sent'
            is_deleted = msg_data.get('deleted', False)
            is_file = text.startswith("[FILE]")

            menu = tk.Menu(self, tearoff=0)

            # For sent messages (not deleted): Edit and Delete
            if is_sent and not is_deleted:
                menu.add_command(label="Edit ✏️", command=lambda: self._edit_message(msg_id, text))
                menu.add_command(label="Delete 🗑️", command=lambda: self._delete_message(msg_id, text))

            # For file attachments: Save File
            if is_file:
                if is_sent:
                    menu.add_separator()
                menu.add_command(label="Save File 📁", command=lambda: self._save_file(msg_id, text))

            if menu.index("end") is not None:  # Menu has items
                try:
                    menu.tk_popup(event.x_root, event.y_root)
                finally:
                    menu.grab_release()

    def _save_file(self, msg_id: str, text: str):
        """Save attached file from message."""
        try:
            # Parse file info from message
            # Format: "[FILE] filename (size bytes)\nbase64data"
            lines = text.split('\n', 1)
            if len(lines) < 2:
                messagebox.showerror("Error", "Invalid file attachment format")
                return

            header = lines[0]  # "[FILE] filename (size bytes)"
            file_b64 = lines[1] if len(lines) > 1 else ""

            # Extract filename
            import re
            match = re.match(r'\[FILE\] (.+) \(\d+ bytes\)', header)
            if not match:
                messagebox.showerror("Error", "Could not parse filename")
                return
            filename = match.group(1)

            # Ask for save location
            save_path = filedialog.asksaveasfilename(
                title="Save File",
                initialfile=filename,
                defaultextension=""
            )
            if not save_path:
                return

            # Decode and save
            import base64
            file_data = base64.b64decode(file_b64)
            with open(save_path, "wb") as f:
                f.write(file_data)

            messagebox.showinfo("Success", f"File saved to: {save_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")

    def _edit_message(self, msg_id: str, current_text: str):
        """Open edit dialog for a message."""
        if self.on_edit_message:
            self.on_edit_message(msg_id, current_text)

    def _delete_message(self, msg_id: str, preview: str):
        """Open delete confirmation for a message."""
        if self.on_delete_message:
            self.on_delete_message(msg_id, preview)

    def _on_edit_shortcut(self):
        """Handle Ctrl+E shortcut to edit last message."""
        if not self.messenger or not self.current_contact:
            return
        history = self.messenger.get_conversation_history(self.current_contact, limit=10)
        for msg in reversed(history):
            if msg.get('direction') == 'sent' and not msg.get('deleted', False):
                self._edit_message(msg.get('msg_id', ''), msg.get('text', ''))
                break

    def _on_delete_shortcut(self):
        """Handle Delete key to delete last message."""
        if not self.messenger or not self.current_contact:
            return
        history = self.messenger.get_conversation_history(self.current_contact, limit=10)
        for msg in reversed(history):
            if msg.get('direction') == 'sent' and not msg.get('deleted', False):
                self._delete_message(msg.get('msg_id', ''), msg.get('text', ''))
                break


class InputAreaPanel(ctk.CTkFrame):
    """Bottom panel for message input and sending."""

    def __init__(self, master, on_send: Callable[[str], None],
                 on_send_ephemeral: Optional[Callable[[str, int], None]] = None,
                 on_attach_file: Optional[Callable] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.on_send = on_send
        self.on_send_ephemeral = on_send_ephemeral
        self.on_attach_file = on_attach_file

        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_columnconfigure(2, weight=0)
        self.grid_columnconfigure(3, weight=0)

        # Message input entry
        self.message_entry = ctk.CTkEntry(
            self,
            placeholder_text="Type a message...",
            height=40,
            font=ctk.CTkFont(size=13)
        )
        self.message_entry.grid(row=0, column=0, padx=(10, 5), pady=10, sticky="ew")
        self.message_entry.bind("<Return>", self._on_enter)

        # Send button
        self.send_btn = ctk.CTkButton(
            self,
            text="Send",
            width=80,
            height=40,
            font=ctk.CTkFont(weight="bold", size=13),
            command=self._on_send_click
        )
        self.send_btn.grid(row=0, column=1, padx=5, pady=10)

        # Ephemeral message button
        self.ephemeral_btn = ctk.CTkButton(
            self,
            text="⏳",
            width=45,
            height=40,
            font=ctk.CTkFont(size=16),
            command=self._on_ephemeral_click,
            fg_color=("#ffaa00", "#cc8800"),
            hover_color=("#cc8800", "#aa6600")
        )
        self.ephemeral_btn.grid(row=0, column=2, padx=5, pady=10)

        # Attach button
        self.attach_btn = ctk.CTkButton(
            self,
            text="📎",
            width=45,
            height=40,
            font=ctk.CTkFont(size=16),
            command=self._on_attach_click
        )
        self.attach_btn.grid(row=0, column=3, padx=(5, 10), pady=10)

    def _on_enter(self, event):
        """Handle Enter key press."""
        self._on_send_click()

    def _on_send_click(self):
        """Handle send button click."""
        message = self.message_entry.get().strip()
        if message:
            self.on_send(message)
            self.message_entry.delete(0, "end")

    def _on_ephemeral_click(self):
        """Handle ephemeral message button click."""
        message = self.message_entry.get().strip()
        if not message:
            messagebox.showwarning("Empty Message", "Please enter a message first")
            return

        # Ask for TTL
        ttl_dialog = ctk.CTkInputDialog(
            text="Enter time-to-live in seconds (default: 30):",
            title="Ephemeral Message TTL"
        )
        ttl_str = ttl_dialog.get_input()
        try:
            ttl = int(ttl_str) if ttl_str else 30
        except (ValueError, TypeError):
            ttl = 30

        if self.on_send_ephemeral:
            self.on_send_ephemeral(message, ttl)
            self.message_entry.delete(0, "end")

    def _on_attach_click(self):
        """Handle attach button click - file attachment."""
        if self.on_attach_file:
            self.on_attach_file()


class ContactDialog(ctk.CTkToplevel):
    """Modal dialog for contact actions."""

    def __init__(self, master, action: str, messenger: SecureMessenger, contact_name: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self.action = action
        self.messenger = messenger
        self.contact_name = contact_name
        self.result = False

        self.title(f"{action.title()} Contact")
        self.geometry("450x350")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(self, text=f"{self.action.title()} Contact", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Contact name
        ctk.CTkLabel(self, text="Contact Name:").pack(anchor="w", padx=20)
        self.name_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter contact name")
        self.name_entry.pack(padx=20, pady=(0, 10), fill="x")
        if self.contact_name:
            self.name_entry.insert(0, self.contact_name)
            if self.action in ["trust", "block", "remove"]:
                self.name_entry.configure(state="readonly")

        # Public key (for add action)
        if self.action == "add":
            ctk.CTkLabel(self, text="Public Key (hex):").pack(anchor="w", padx=20)
            self.pubkey_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter X25519 public key in hex")
            self.pubkey_entry.pack(padx=20, pady=(0, 10), fill="x")

            ctk.CTkLabel(self, text="Signing Key (hex, optional):").pack(anchor="w", padx=20)
            self.signkey_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter Ed25519 signing key in hex")
            self.signkey_entry.pack(padx=20, pady=(0, 10), fill="x")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=20)

        confirm_btn = ctk.CTkButton(btn_frame, text="Confirm", command=self._on_confirm)
        confirm_btn.pack(side="left", padx=5, expand=True, fill="x")

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, fg_color="gray")
        cancel_btn.pack(side="left", padx=5, expand=True, fill="x")

        # Focus on name entry
        self.name_entry.focus()

    def _on_confirm(self):
        """Handle confirm button."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Contact name is required", parent=self)
            return

        try:
            if self.action == "add":
                pubkey = self.pubkey_entry.get().strip()
                signkey = self.signkey_entry.get().strip() or None
                if not pubkey:
                    messagebox.showerror("Error", "Public key is required", parent=self)
                    return
                self.messenger.add_contact(name, pubkey, signkey)
                messagebox.showinfo("Success", f"Contact '{name}' added successfully", parent=self)
            elif self.action == "trust":
                success = self.messenger.trust_contact(name)
                if success:
                    messagebox.showinfo("Success", f"Contact '{name}' is now trusted", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to trust contact '{name}'", parent=self)
                    return
            elif self.action == "block":
                success = self.messenger.block_contact(name)
                if success:
                    messagebox.showinfo("Success", f"Contact '{name}' is now blocked", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to block contact '{name}'", parent=self)
                    return
            elif self.action == "remove":
                success = self.messenger.remove_contact(name)
                if success:
                    messagebox.showinfo("Success", f"Contact '{name}' removed", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to remove contact '{name}'", parent=self)
                    return

            self.result = True
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_cancel(self):
        """Handle cancel button."""
        self.result = False
        self.destroy()


class GroupDialog(ctk.CTkToplevel):
    """Modal dialog for group actions."""

    def __init__(self, master, action: str, messenger: SecureMessenger, group_name: str = "", **kwargs):
        super().__init__(master, **kwargs)
        self.action = action
        self.messenger = messenger
        self.group_name = group_name
        self.result = False

        self.title(f"{action.title()} Group")
        self.geometry("450x300")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(self, text=f"{self.action.title()} Group", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Group name
        ctk.CTkLabel(self, text="Group Name:").pack(anchor="w", padx=20)
        self.name_entry = ctk.CTkEntry(self, width=400, placeholder_text="Enter group name")
        self.name_entry.pack(padx=20, pady=(0, 10), fill="x")
        if self.group_name:
            self.name_entry.insert(0, self.group_name)
            if self.action in ["add-member", "remove-member", "delete"]:
                self.name_entry.configure(state="readonly")

        # Members (for create and add-member)
        if self.action in ["create", "add-member"]:
            ctk.CTkLabel(self, text="Member Names (comma-separated):").pack(anchor="w", padx=20)
            self.members_entry = ctk.CTkEntry(self, width=400, placeholder_text="Alice, Bob, Charlie")
            self.members_entry.pack(padx=20, pady=(0, 10), fill="x")

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=20)

        confirm_btn = ctk.CTkButton(btn_frame, text="Confirm", command=self._on_confirm)
        confirm_btn.pack(side="left", padx=5, expand=True, fill="x")

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, fg_color="gray")
        cancel_btn.pack(side="left", padx=5, expand=True, fill="x")

        self.name_entry.focus()

    def _on_confirm(self):
        """Handle confirm button."""
        name = self.name_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Group name is required", parent=self)
            return

        try:
            if self.action == "create":
                members_input = self.members_entry.get().strip()
                members = [m.strip() for m in members_input.split(",") if m.strip()]
                if not members:
                    messagebox.showerror("Error", "At least one member is required", parent=self)
                    return
                success = self.messenger.create_group(name, members)
                if success:
                    messagebox.showinfo("Success", f"Group '{name}' created successfully", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to create group '{name}'", parent=self)
                    return
            elif self.action == "add-member":
                member = self.members_entry.get().strip()
                if not member:
                    messagebox.showerror("Error", "Member name is required", parent=self)
                    return
                success = self.messenger.add_group_member(name, member)
                if success:
                    messagebox.showinfo("Success", f"Member '{member}' added to group '{name}'", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to add member", parent=self)
                    return
            elif self.action == "remove-member":
                member = self.members_entry.get().strip()
                if not member:
                    messagebox.showerror("Error", "Member name is required", parent=self)
                    return
                success = self.messenger.remove_group_member(name, member)
                if success:
                    messagebox.showinfo("Success", f"Member '{member}' removed from group '{name}'", parent=self)
                else:
                    messagebox.showerror("Error", f"Failed to remove member", parent=self)
                    return
            elif self.action == "delete":
                if messagebox.askyesno("Confirm", f"Delete group '{name}'?", parent=self):
                    success = self.messenger.delete_group(name)
                    if success:
                        messagebox.showinfo("Success", f"Group '{name}' deleted", parent=self)
                    else:
                        messagebox.showerror("Error", f"Failed to delete group '{name}'", parent=self)
                        return

            self.result = True
            self.destroy()

        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_cancel(self):
        """Handle cancel button."""
        self.result = False
        self.destroy()


class SettingsDialog(ctk.CTkToplevel):
    """Modal dialog showing settings."""

    def __init__(self, master, messenger: SecureMessenger, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger = messenger

        self.title("Settings")
        self.geometry("500x500")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        """Build the settings UI."""
        # Scrollable frame for settings
        scroll = ctk.CTkScrollableFrame(self)
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        # Title
        ctk.CTkLabel(scroll, text="Settings", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(0, 20))

        # User info
        ctk.CTkLabel(scroll, text=f"Username: {self.messenger.username}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)
        ctk.CTkLabel(scroll, text=f"Data Directory: {self.messenger.data_dir}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)
        ctk.CTkLabel(scroll, text=f"Queue Directory: {self.messenger.queue_dir}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)

        # Networking
        net_status = "Enabled" if self.messenger.use_networking else "Disabled"
        ctk.CTkLabel(scroll, text=f"Networking: {net_status}", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=(10, 2))
        if self.messenger.use_networking:
            ctk.CTkLabel(scroll, text=f"Host: {self.messenger.host}:{self.messenger.port}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)
            ctk.CTkLabel(scroll, text=f"Server Mode: {'Yes' if self.messenger.is_server else 'No'}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)
            ctk.CTkLabel(scroll, text=f"Secure (WSS): {'Yes' if self.messenger.secure else 'No'}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)
            ctk.CTkLabel(scroll, text=f"Auth Method: {self.messenger.auth_method.upper()}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)

        # Keys
        pubkey = self.messenger.identity_manager.get_public_key_hex()
        ctk.CTkLabel(scroll, text=f"Your Public Key: {pubkey}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=(10, 2))

        signing_key = self.messenger.identity_manager.get_signing_public_key_hex()
        if signing_key:
            ctk.CTkLabel(scroll, text=f"Your Signing Key: {signing_key}", font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)

        # Close button
        close_btn = ctk.CTkButton(self, text="Close", command=self.destroy, width=100)
        close_btn.pack(pady=20)


class EditMessageDialog(ctk.CTkToplevel):
    """Modal dialog for editing a message."""

    def __init__(self, master, messenger: SecureMessenger, msg_id: str, current_text: str, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger = messenger
        self.msg_id = msg_id
        self.current_text = current_text
        self.result = False

        self.title("Edit Message")
        self.geometry("500x300")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(self, text="Edit Message", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Message ID
        ctk.CTkLabel(self, text=f"Message ID: {self.msg_id[:16]}...", font=ctk.CTkFont(size=11)).pack(pady=(0, 10))

        # Message text
        ctk.CTkLabel(self, text="New message text:").pack(anchor="w", padx=20)
        self.text_entry = ctk.CTkEntry(self, width=450, placeholder_text="Enter new message text")
        self.text_entry.pack(padx=20, pady=(0, 10), fill="x")
        self.text_entry.insert(0, self.current_text)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=20)

        confirm_btn = ctk.CTkButton(btn_frame, text="Save", command=self._on_confirm)
        confirm_btn.pack(side="left", padx=5, expand=True, fill="x")

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, fg_color="gray")
        cancel_btn.pack(side="left", padx=5, expand=True, fill="x")

        self.text_entry.focus()

    def _on_confirm(self):
        """Handle confirm button."""
        new_text = self.text_entry.get().strip()
        if not new_text:
            messagebox.showerror("Error", "Message cannot be empty", parent=self)
            return

        try:
            success = self.messenger.edit_message(self.msg_id, new_text)
            if success:
                messagebox.showinfo("Success", "Message edited successfully", parent=self)
                self.result = True
                self.destroy()
            else:
                messagebox.showerror("Error", "Failed to edit message (not your message or too old)", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_cancel(self):
        """Handle cancel button."""
        self.result = False
        self.destroy()


class DeleteMessageDialog(ctk.CTkToplevel):
    """Modal dialog for confirming message deletion."""

    def __init__(self, master, messenger: SecureMessenger, msg_id: str, preview: str, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger = messenger
        self.msg_id = msg_id
        self.preview = preview[:100] + ("..." if len(preview) > 100 else "")

        self.title("Delete Message")
        self.geometry("450x250")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(self, text="Delete Message", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Message ID
        ctk.CTkLabel(self, text=f"Message ID: {self.msg_id[:16]}...", font=ctk.CTkFont(size=11)).pack(pady=(0, 10))

        # Preview
        ctk.CTkLabel(self, text=f"Preview: {self.preview}", font=ctk.CTkFont(size=12)).pack(pady=5)

        # Warning
        ctk.CTkLabel(self, text="This will mark the message as deleted for all participants.",
                     font=ctk.CTkFont(size=12), text_color="yellow").pack(pady=5)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=20)

        delete_btn = ctk.CTkButton(btn_frame, text="Delete", command=self._on_delete,
                                   fg_color="#ff4444", hover_color="#cc0000")
        delete_btn.pack(side="left", padx=5, expand=True, fill="x")

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self._on_cancel, fg_color="gray")
        cancel_btn.pack(side="left", padx=5, expand=True, fill="x")

    def _on_delete(self):
        """Handle delete button."""
        try:
            success = self.messenger.delete_message(self.msg_id)
            if success:
                messagebox.showinfo("Success", "Message deleted successfully", parent=self)
                self.destroy()
            else:
                messagebox.showerror("Error", "Failed to delete message (not your message)", parent=self)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self)

    def _on_cancel(self):
        """Handle cancel button."""
        self.destroy()


class GroupManagementDialog(ctk.CTkToplevel):
    """Modal dialog for viewing and managing group members."""

    def __init__(self, master, messenger: SecureMessenger, group_name: str, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger = messenger
        self.group_name = group_name
        self.is_admin = False

        self.title(f"Group Management: {group_name}")
        self.geometry("500x400")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()
        self.refresh_members()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(self, text=f"Group: {self.group_name}", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Scrollable member list
        self.members_frame = ctk.CTkScrollableFrame(self, width=450, height=250)
        self.members_frame.pack(padx=20, pady=10, fill="both", expand=True)

        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=10, fill="x", padx=20)

        refresh_btn = ctk.CTkButton(btn_frame, text="Refresh", command=self.refresh_members)
        refresh_btn.pack(side="left", padx=5, expand=True, fill="x")

        close_btn = ctk.CTkButton(btn_frame, text="Close", command=self.destroy)
        close_btn.pack(side="left", padx=5, expand=True, fill="x")

    def refresh_members(self):
        """Refresh the member list."""
        # Clear existing
        for widget in self.members_frame.winfo_children():
            widget.destroy()

        try:
            members = self.messenger.contact_manager.get_group_members(self.group_name)
            groups = self.messenger.list_groups()
            group_info = groups.get(self.group_name, {})
            admins = group_info.get("admins", [])
            creator = group_info.get("creator", "")

            self.is_admin = self.messenger.username in admins or self.messenger.username == creator

            # Creator
            ctk.CTkLabel(self.members_frame, text=f"Creator: {creator}",
                         font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=2)
            # Admins
            ctk.CTkLabel(self.members_frame, text=f"Admins: {', '.join(admins) if admins else 'None'}",
                         font=ctk.CTkFont(size=13)).pack(anchor="w", pady=2)
            ctk.CTkLabel(self.members_frame, text="").pack()

            # Members
            ctk.CTkLabel(self.members_frame, text="Members:", font=ctk.CTkFont(size=13, weight="bold")).pack(anchor="w", pady=2)

            for member in members:
                badges = []
                if member in admins:
                    badges.append("👑")
                if member == creator:
                    badges.append("⭐")
                if member == self.messenger.username:
                    badges.append("(you)")
                badge_str = " ".join(badges)
                ctk.CTkLabel(self.members_frame, text=f"  • {member} {badge_str}").pack(anchor="w", pady=1)

            if not self.is_admin:
                ctk.CTkLabel(self.members_frame, text="").pack()
                ctk.CTkLabel(self.members_frame, text="You are not an admin of this group.",
                             font=ctk.CTkFont(size=12), text_color="gray").pack(anchor="w", pady=5)

        except Exception as e:
            ctk.CTkLabel(self.members_frame, text=f"Error loading members: {e}",
                         text_color="red").pack(anchor="w", pady=10)


class FileAttachmentDialog(ctk.CTkToplevel):
    """Modal dialog for file attachment."""

    def __init__(self, master, messenger: SecureMessenger, contact: str, is_group: bool, **kwargs):
        super().__init__(master, **kwargs)
        self.messenger = messenger
        self.contact = contact
        self.is_group = is_group
        self.selected_file = None

        self.title("Attach File")
        self.geometry("500x250")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        # Center on parent
        self.update_idletasks()
        x = master.winfo_x() + (master.winfo_width() // 2) - (self.winfo_width() // 2)
        y = master.winfo_y() + (master.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        self._build_ui()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ctk.CTkLabel(self, text="Attach File", font=ctk.CTkFont(size=18, weight="bold"))
        title_label.pack(pady=(20, 10))

        # Target
        target_type = "Group" if self.is_group else "Contact"
        ctk.CTkLabel(self, text=f"Send to {target_type}: {self.contact}").pack(pady=5)

        # File selection
        file_frame = ctk.CTkFrame(self, fg_color="transparent")
        file_frame.pack(padx=20, pady=10, fill="x")

        self.file_label = ctk.CTkLabel(file_frame, text="No file selected", text_color="gray")
        self.file_label.pack(side="left", padx=5)

        browse_btn = ctk.CTkButton(file_frame, text="Browse...", command=self._browse_file, width=100)
        browse_btn.pack(side="left", padx=5)

        # Send button
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(pady=20, fill="x", padx=20)

        send_btn = ctk.CTkButton(btn_frame, text="Send File", command=self._send_file,
                                 state="disabled", width=120)
        send_btn.pack(side="left", padx=5, expand=True, fill="x")
        self.send_btn = send_btn

        cancel_btn = ctk.CTkButton(btn_frame, text="Cancel", command=self.destroy, fg_color="gray")
        cancel_btn.pack(side="left", padx=5, expand=True, fill="x")

    def _browse_file(self):
        """Browse for a file to attach."""
        file_path = filedialog.askopenfilename(
            title="Select file to attach",
            filetypes=[("All files", "*.*"), ("Text files", "*.txt"), ("Images", "*.png *.jpg *.jpeg *.gif")]
        )
        if file_path:
            self.selected_file = file_path
            self.file_label.configure(text=os.path.basename(file_path), text_color="white")
            self.send_btn.configure(state="normal")

    def _send_file(self):
        """Send the selected file."""
        if not self.selected_file:
            return

        try:
            # Read file and encode as base64
            import base64
            with open(self.selected_file, "rb") as f:
                file_data = f.read()

            file_b64 = base64.b64encode(file_data).decode()
            file_name = os.path.basename(self.selected_file)
            file_size = len(file_data)

            # Create a message with file attachment indicator
            message = f"[FILE] {file_name} ({file_size} bytes)\n{file_b64}"

            success = self.messenger.send_message(self.contact, message)
            if success:
                messagebox.showinfo("Success", f"File '{file_name}' sent successfully", parent=self)
                self.destroy()
            else:
                messagebox.showerror("Error", "Failed to send file", parent=self)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to send file: {e}", parent=self)


class EncryptedMessagingGUI(ctk.CTk):
    """Main GUI Application for Encrypted Messaging."""

    def __init__(self, username: str, data_dir: str = "./data", queue_dir: str = "./queue",
                 use_networking: bool = False, host: str = "localhost", port: int = 8765,
                 is_server: bool = False, auth_method: str = "tofu", secure: bool = False):
        super().__init__()

        # Store parameters
        self.username = username
        self.data_dir = data_dir
        self.queue_dir = queue_dir
        self.use_networking = use_networking
        self.host = host
        self.port = port
        self.is_server = is_server
        self.auth_method = auth_method
        self.secure = secure

        self.messenger: Optional[SecureMessenger] = None
        self.polling = True
        self._asyncio_loop: Optional[asyncio.AbstractEventLoop] = None
        self._asyncio_thread: Optional[threading.Thread] = None

        # Theme state
        self.current_theme = "system"  # "light", "dark", "system"

        # Window setup
        self.title(f"Encrypted Messaging - {self.username}")
        self.geometry("1200x800")
        self.minsize(1000, 700)

        # Network status for subtitle
        net_status = "🔐 Secure" if self.use_networking else "📁 File-based"
        self.subtitle = f"{net_status} | {self.auth_method.upper()}"

        # Build UI
        self._build_ui()

        # Initialize messenger after UI is ready
        self.after(100, self._init_messenger)

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_ui(self):
        """Build the main UI layout."""
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Menu bar (top)
        self._build_menu_bar()

        # Left sidebar - Contact List (with search)
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=("gray90", "gray15"))
        self.sidebar_frame.grid(row=1, column=0, rowspan=2, sticky="nsew", padx=(0, 1))
        self.sidebar_frame.grid_rowconfigure(1, weight=1)
        self.sidebar_frame.grid_columnconfigure(0, weight=1)

        # Search bar in sidebar
        self.search_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent")
        self.search_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        self.search_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            self.search_frame,
            placeholder_text="🔍 Search contacts...",
            height=35,
            font=ctk.CTkFont(size=12)
        )
        self.search_entry.grid(row=0, column=0, padx=(5, 0), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._on_search)

        # Contact panel inside sidebar
        self.contact_panel = ContactListPanel(
            self.sidebar_frame,
            messenger=None,  # Will be set after messenger init
            on_contact_select=self._on_contact_select,
            fg_color="transparent"
        )
        self.contact_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))

        # Center - Message View
        self.message_view = MessageViewPanel(
            self,
            on_edit_message=self._on_edit_message,
            on_delete_message=self._on_delete_message,
            fg_color=("gray95", "gray10"),
            font=ctk.CTkFont(size=13),
            corner_radius=0
        )
        self.message_view.grid(row=1, column=1, sticky="nsew", padx=1, pady=1)

        # Bottom - Input Area
        self.input_area = InputAreaPanel(
            self,
            on_send=self._on_send_message,
            on_send_ephemeral=self._on_send_ephemeral,
            on_attach_file=self._on_attach_file,
            height=60,
            fg_color=("gray90", "gray15"),
            corner_radius=0
        )
        self.input_area.grid(row=2, column=1, sticky="ew", padx=1, pady=(0, 1))

        # Status bar (bottom)
        self.status_var = ctk.StringVar(value="Initializing...")
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w", height=25)
        self.status_bar.grid(row=3, column=0, columnspan=2, sticky="ew", padx=10, pady=(0, 5))

    def _build_menu_bar(self):
        """Build the menu bar."""
        # Create a frame to act as menu bar
        self.menu_frame = ctk.CTkFrame(self, height=35, corner_radius=0)
        self.menu_frame.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.menu_frame.grid_columnconfigure(0, weight=1)

        # Use standard tkinter Menu for proper menu bar
        self.tk_menu = tk.Menu(self)
        self.config(menu=self.tk_menu)

        # File menu
        file_menu = tk.Menu(self.tk_menu, tearoff=0)
        self.tk_menu.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Quit", command=self._on_closing, accelerator="Ctrl+Q")

        # Contacts menu
        contacts_menu = tk.Menu(self.tk_menu, tearoff=0)
        self.tk_menu.add_cascade(label="Contacts", menu=contacts_menu)
        contacts_menu.add_command(label="Add Contact...", command=self._show_add_contact_dialog, accelerator="Ctrl+N")
        contacts_menu.add_command(label="Trust Contact", command=self._show_trust_contact_dialog, accelerator="Ctrl+T")
        contacts_menu.add_command(label="Block Contact", command=self._show_block_contact_dialog, accelerator="Ctrl+B")
        contacts_menu.add_command(label="Remove Contact", command=self._show_remove_contact_dialog, accelerator="Ctrl+R")
        contacts_menu.add_separator()
        contacts_menu.add_command(label="Refresh", command=self._refresh_all, accelerator="Ctrl+Shift+R")

        # Groups menu
        groups_menu = tk.Menu(self.tk_menu, tearoff=0)
        self.tk_menu.add_cascade(label="Groups", menu=groups_menu)
        groups_menu.add_command(label="Create Group...", command=self._show_create_group_dialog, accelerator="Ctrl+G")
        groups_menu.add_command(label="Add Member...", command=self._show_add_group_member_dialog, accelerator="Ctrl+A")
        groups_menu.add_command(label="Remove Member...", command=self._show_remove_group_member_dialog, accelerator="Ctrl+Shift+A")
        groups_menu.add_separator()
        groups_menu.add_command(label="Manage Group...", command=self._show_manage_group_dialog, accelerator="Ctrl+M")
        groups_menu.add_separator()
        groups_menu.add_command(label="Delete Group...", command=self._show_delete_group_dialog, accelerator="Ctrl+D")

        # View menu
        view_menu = tk.Menu(self.tk_menu, tearoff=0)
        self.tk_menu.add_cascade(label="View", menu=view_menu)
        view_menu.add_command(label="Toggle Theme", command=self._toggle_theme, accelerator="Ctrl+Shift+T")
        view_menu.add_separator()
        view_menu.add_command(label="Clear Chat", command=self._clear_chat, accelerator="Ctrl+L")

        # Settings menu
        settings_menu = tk.Menu(self.tk_menu, tearoff=0)
        self.tk_menu.add_cascade(label="Settings", menu=settings_menu)
        settings_menu.add_command(label="Settings...", command=self._show_settings_dialog, accelerator="Ctrl+S")

        # Help menu
        help_menu = tk.Menu(self.tk_menu, tearoff=0)
        self.tk_menu.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

        # Bind keyboard shortcuts
        self.bind_all("<Control-q>", lambda e: self._on_closing())
        self.bind_all("<Control-n>", lambda e: self._show_add_contact_dialog())
        self.bind_all("<Control-t>", lambda e: self._show_trust_contact_dialog())
        self.bind_all("<Control-b>", lambda e: self._show_block_contact_dialog())
        self.bind_all("<Control-r>", lambda e: self._show_remove_contact_dialog())
        self.bind_all("<Control-g>", lambda e: self._show_create_group_dialog())
        self.bind_all("<Control-a>", lambda e: self._show_add_group_member_dialog())
        self.bind_all("<Control-A>", lambda e: self._show_remove_group_member_dialog())  # Shift+A
        self.bind_all("<Control-d>", lambda e: self._show_delete_group_dialog())
        self.bind_all("<Control-s>", lambda e: self._show_settings_dialog())
        self.bind_all("<Control-Shift-R>", lambda e: self._refresh_all())
        self.bind_all("<Control-Shift-T>", lambda e: self._toggle_theme())
        self.bind_all("<Control-l>", lambda e: self._clear_chat())
        self.bind_all("<Control-m>", lambda e: self._show_manage_group_dialog())

    def _init_messenger(self):
        """Initialize the SecureMessenger."""
        try:
            self.messenger = SecureMessenger(
                username=self.username,
                data_dir=self.data_dir,
                queue_dir=self.queue_dir,
                use_networking=self.use_networking,
                host=self.host,
                port=self.port,
                is_server=self.is_server,
                auth_method=self.auth_method,
                secure=self.secure,
                new_contact_callback=self._on_new_contact
            )

            # Set messenger on panels
            self.contact_panel.messenger = self.messenger
            self.message_view.set_messenger(self.messenger)

            # Set search callback on contact panel
            self.contact_panel.set_search_callback(self._filter_contacts)

            # Start message polling
            self._start_message_polling()

            # Update status
            net_status = "🔐 Connected" if self.use_networking else "📁 Ready"
            self.status_var.set(f"{net_status} as {self.username} | {self.subtitle}")

            # Show welcome notification
            self.after(500, lambda: self._show_toast("Connected", f"Connected as {self.username}"))

        except Exception as e:
            messagebox.showerror("Initialization Error", f"Failed to initialize: {e}")
            self.destroy()

    def _start_message_polling(self):
        """Start periodic message polling."""
        self._poll_messages()

    def _poll_messages(self):
        """Poll for new messages."""
        if not self.messenger or not self.polling:
            return

        try:
            messages = self.messenger.receive_and_process_messages()
            if messages:
                for sender, text in messages:
                    # Only show if it's for the current conversation
                    current_contact = self.message_view.current_contact
                    current_is_group = self.message_view.current_is_group

                    if current_contact:
                        if current_is_group:
                            group_members = self.messenger.contact_manager.get_group_members(current_contact)
                            if sender in group_members:
                                self.message_view.add_message(sender, text)
                        else:
                            if sender == current_contact:
                                self.message_view.add_message(sender, text)
                    else:
                        # No conversation selected, show toast notification
                        self.after(0, lambda s=sender, t=text: self._show_toast(
                            "New Message", f"From {s}: {t[:50]}..."))

                # Refresh contacts to update trust levels
                self.contact_panel.refresh_contacts()

            # Update ephemeral message timers for current conversation
            if self.message_view.current_contact:
                self.message_view.update_ephemeral_timers()

        except Exception as e:
            # Silently ignore polling errors
            pass

        # Schedule next poll
        if self.polling:
            self.after(1000, self._poll_messages)

    def _show_toast(self, title: str, message: str):
        """Show a toast notification (non-blocking)."""
        # Create a temporary toplevel for toast
        toast = ctk.CTkToplevel(self)
        toast.title(title)
        toast.geometry("300x100")
        toast.resizable(False, False)
        toast.transient(self)
        toast.attributes('-topmost', True)

        # Position near bottom-right of main window
        self.update_idletasks()
        x = self.winfo_x() + self.winfo_width() - 320
        y = self.winfo_y() + self.winfo_height() - 150
        toast.geometry(f"+{x}+{y}")

        ctk.CTkLabel(toast, text=title, font=ctk.CTkFont(weight="bold", size=14)).pack(pady=(10, 2))
        ctk.CTkLabel(toast, text=message, wraplength=280).pack(pady=2, padx=10)

        # Auto-close after 5 seconds
        toast.after(5000, toast.destroy)

    def _on_new_contact(self, name: str, public_key: bytes):
        """Callback for new contact (TOFU)."""
        self.after(0, lambda: messagebox.showwarning(
            "New Contact Request",
            f"New contact request from {name}\n\n"
            f"Public Key: {public_key.hex()}\n\n"
            f"Use 'Contacts > Add Contact' to add them.",
            parent=self
        ))

    def _on_contact_select(self, contact_name: str, is_group: bool):
        """Handle contact selection from sidebar."""
        self.message_view.set_conversation(contact_name, is_group)
        group_suffix = " (Group)" if is_group else ""
        self.status_var.set(f"Chatting with {contact_name}{group_suffix} | {self.subtitle}")

    def _on_search(self, event=None):
        """Handle search entry changes."""
        query = self.search_entry.get().strip().lower()
        self._filter_contacts(query)

    def _filter_contacts(self, query: str):
        """Filter contacts based on search query."""
        if hasattr(self.contact_panel, 'filter_contacts'):
            self.contact_panel.filter_contacts(query)

    def _on_send_message(self, message: str):
        """Handle sending a message."""
        if not self.messenger:
            return

        current_contact = self.message_view.current_contact
        is_group = self.message_view.current_is_group

        if not current_contact:
            messagebox.showwarning("No Contact", "Please select a contact or group first")
            return

        try:
            success = self.messenger.send_message(current_contact, message)
            if success:
                self.message_view.add_message("You", message, is_sent=True)
                self.status_var.set("Message sent")
                self.after(2000, lambda: self.status_var.set(f"Chatting with {current_contact} | {self.subtitle}"))
            else:
                messagebox.showerror("Error", "Failed to send message")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending message: {e}")

    # Dialog methods
    def _show_add_contact_dialog(self):
        """Show add contact dialog."""
        if not self.messenger:
            return
        dialog = ContactDialog(self, "add", self.messenger)
        self.wait_window(dialog)
        if dialog.result:
            self.contact_panel.refresh_contacts()

    def _show_trust_contact_dialog(self):
        """Show trust contact dialog."""
        if not self.messenger:
            return
        contact = self.contact_panel.selected_contact
        if contact and not self.contact_panel.selected_is_group:
            dialog = ContactDialog(self, "trust", self.messenger, contact_name=contact)
            self.wait_window(dialog)
            if dialog.result:
                self.contact_panel.refresh_contacts()
        else:
            messagebox.showwarning("No Contact", "Please select a contact first")

    def _show_block_contact_dialog(self):
        """Show block contact dialog."""
        if not self.messenger:
            return
        contact = self.contact_panel.selected_contact
        if contact and not self.contact_panel.selected_is_group:
            dialog = ContactDialog(self, "block", self.messenger, contact_name=contact)
            self.wait_window(dialog)
            if dialog.result:
                self.contact_panel.refresh_contacts()
        else:
            messagebox.showwarning("No Contact", "Please select a contact first")

    def _show_remove_contact_dialog(self):
        """Show remove contact dialog."""
        if not self.messenger:
            return
        contact = self.contact_panel.selected_contact
        if contact and not self.contact_panel.selected_is_group:
            dialog = ContactDialog(self, "remove", self.messenger, contact_name=contact)
            self.wait_window(dialog)
            if dialog.result:
                self.contact_panel.refresh_contacts()
        else:
            messagebox.showwarning("No Contact", "Please select a contact first")

    def _show_create_group_dialog(self):
        """Show create group dialog."""
        if not self.messenger:
            return
        dialog = GroupDialog(self, "create", self.messenger)
        self.wait_window(dialog)
        if dialog.result:
            self.contact_panel.refresh_contacts()

    def _show_add_group_member_dialog(self, group_name: str = None):
        """Show add group member dialog."""
        if not self.messenger:
            return
        if group_name is None:
            group_name = self.contact_panel.selected_contact
        if group_name and self.contact_panel.selected_is_group:
            dialog = GroupDialog(self, "add-member", self.messenger, group_name=group_name)
            self.wait_window(dialog)
            if dialog.result:
                self.contact_panel.refresh_contacts()
        else:
            messagebox.showwarning("No Group", "Please select a group first")

    def show_add_group_member_dialog(self, group_name: str):
        """Public method for context menu to call."""
        self._show_add_group_member_dialog(group_name)

    def _show_remove_group_member_dialog(self, group_name: str = None):
        """Show remove group member dialog."""
        if not self.messenger:
            return
        if group_name is None:
            group_name = self.contact_panel.selected_contact
        if group_name and self.contact_panel.selected_is_group:
            dialog = GroupDialog(self, "remove-member", self.messenger, group_name=group_name)
            self.wait_window(dialog)
            if dialog.result:
                self.contact_panel.refresh_contacts()
        else:
            messagebox.showwarning("No Group", "Please select a group first")

    def show_remove_group_member_dialog(self, group_name: str):
        """Public method for context menu to call."""
        self._show_remove_group_member_dialog(group_name)

    def _show_delete_group_dialog(self):
        """Show delete group dialog."""
        if not self.messenger:
            return
        group_name = self.contact_panel.selected_contact
        if group_name and self.contact_panel.selected_is_group:
            dialog = GroupDialog(self, "delete", self.messenger, group_name=group_name)
            self.wait_window(dialog)
            if dialog.result:
                self.contact_panel.refresh_contacts()
                # Clear message view if it was showing this group
                if self.message_view.current_contact == group_name:
                    self.message_view.clear()
                    self.message_view.current_contact = None
        else:
            messagebox.showwarning("No Group", "Please select a group first")

    def _show_settings_dialog(self):
        """Show settings dialog."""
        if not self.messenger:
            return
        SettingsDialog(self, self.messenger)

    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About",
            "Encrypted Messaging GUI\n\n"
            "End-to-end encrypted messaging with:\n"
            "• X25519 + AES-256-GCM encryption\n"
            "• Ed25519 message signatures\n"
            "• Forward secrecy (ephemeral keys)\n"
            "• Trust on First Use (TOFU)\n"
            "• X.509 Certificate authentication\n"
            "• Group chats (pairwise encryption)\n"
            "• Offline message delivery\n"
            "• File-based & WebSocket transport\n\n"
            "Built with Python + CustomTkinter"
        )

    def _refresh_all(self):
        """Refresh contacts and message view."""
        self.contact_panel.refresh_contacts()
        if self.message_view.current_contact:
            self.message_view.load_history()
        self.status_var.set("Refreshed")
        self.after(2000, lambda: self.status_var.set(f"Chatting with {self.message_view.current_contact} | {self.subtitle}"))

    # New handler methods for enhancements
    def _on_edit_message(self, msg_id: str, current_text: str):
        """Handle edit message request."""
        if not self.messenger:
            return
        dialog = EditMessageDialog(self, self.messenger, msg_id, current_text)
        self.wait_window(dialog)
        if dialog.result:
            self.message_view.load_history()

    def _on_delete_message(self, msg_id: str, preview: str):
        """Handle delete message request."""
        if not self.messenger:
            return
        dialog = DeleteMessageDialog(self, self.messenger, msg_id, preview)
        self.wait_window(dialog)
        if not hasattr(dialog, 'result') or dialog.result is not False:
            # Dialog doesn't have result attr, check if it was closed via delete
            self.message_view.load_history()

    def _on_send_ephemeral(self, message: str, ttl: int):
        """Handle sending an ephemeral message."""
        if not self.messenger:
            return

        current_contact = self.message_view.current_contact
        is_group = self.message_view.current_is_group

        if not current_contact:
            messagebox.showwarning("No Contact", "Please select a contact or group first")
            return

        try:
            success = self.messenger.send_message(current_contact, message, ttl=ttl)
            if success:
                self.message_view.add_message("You", message + f" ⏳{ttl}s", is_sent=True)
                self.status_var.set(f"Ephemeral message sent (TTL: {ttl}s)")
                self.after(2000, lambda: self.status_var.set(f"Chatting with {current_contact} | {self.subtitle}"))
            else:
                messagebox.showerror("Error", "Failed to send ephemeral message")
        except Exception as e:
            messagebox.showerror("Error", f"Error sending ephemeral message: {e}")

    def _on_attach_file(self):
        """Handle file attachment."""
        if not self.messenger:
            return

        current_contact = self.message_view.current_contact
        is_group = self.message_view.current_is_group

        if not current_contact:
            messagebox.showwarning("No Contact", "Please select a contact or group first")
            return

        dialog = FileAttachmentDialog(self, self.messenger, current_contact, is_group)
        self.wait_window(dialog)
        # Message view will be updated via polling

    def _show_manage_group_dialog(self):
        """Show group management dialog."""
        if not self.messenger:
            return
        group_name = self.contact_panel.selected_contact
        if group_name and self.contact_panel.selected_is_group:
            dialog = GroupManagementDialog(self, self.messenger, group_name)
            self.wait_window(dialog)
        else:
            messagebox.showwarning("No Group", "Please select a group first")

    def _toggle_theme(self):
        """Toggle between light, dark, and system themes."""
        themes = ["system", "dark", "light"]
        current_idx = themes.index(self.current_theme)
        next_idx = (current_idx + 1) % len(themes)
        self.current_theme = themes[next_idx]
        ctk.set_appearance_mode(self.current_theme)
        self._show_toast("Theme Changed", f"Theme set to: {self.current_theme.capitalize()}")

    def _clear_chat(self):
        """Clear the current chat view."""
        self.message_view.clear()
        if self.message_view.current_contact:
            self.message_view.load_history()
        self._show_toast("Chat Cleared", "Chat view cleared and reloaded")

    def _on_closing(self):
        """Handle window close."""
        self.polling = False
        if self.messenger:
            try:
                self.messenger.message_queue.stop()
            except Exception:
                pass
        self.destroy()


def run_gui(username: str, data_dir: str = "./data", queue_dir: str = "./queue",
            use_networking: bool = False, host: str = "localhost", port: int = 8765,
            is_server: bool = False, auth_method: str = "tofu", secure: bool = False):
    """Run the GUI application."""
    app = EncryptedMessagingGUI(
        username=username,
        data_dir=data_dir,
        queue_dir=queue_dir,
        use_networking=use_networking,
        host=host,
        port=port,
        is_server=is_server,
        auth_method=auth_method,
        secure=secure
    )
    app.mainloop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Encrypted Messaging GUI")
    parser.add_argument("--username", "-u", required=True, help="Your username")
    parser.add_argument("--data-dir", default="./data", help="Data directory")
    parser.add_argument("--queue-dir", default="./queue", help="Queue directory")
    parser.add_argument("--networking", "-n", action="store_true", help="Use WebSocket networking")
    parser.add_argument("--host", default="localhost", help="WebSocket host")
    parser.add_argument("--port", "-p", type=int, default=8765, help="WebSocket port")
    parser.add_argument("--server", "-s", action="store_true", help="Run as server")
    parser.add_argument("--secure", action="store_true", help="Use secure WebSocket (WSS)")
    parser.add_argument("--auth-method", choices=["tofu", "cert"], default="tofu", help="Auth method")

    args = parser.parse_args()

    run_gui(
        username=args.username,
        data_dir=args.data_dir,
        queue_dir=args.queue_dir,
        use_networking=args.networking,
        host=args.host,
        port=args.port,
        is_server=args.server,
        auth_method=args.auth_method,
        secure=args.secure
    )