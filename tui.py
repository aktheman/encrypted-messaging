"""
Terminal User Interface (TUI) for the Encrypted Messaging App.
Built with Textual framework.
"""

import asyncio
import time
import sys
import os
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Header, Footer, Static, Input, Button, ListView, ListItem, Label,
    RichLog, Select, TabbedContent, TabPane, Tree, DataTable, Tabs,
    Collapsible, Markdown
)
from textual.screen import ModalScreen
from textual.message import Message
from textual.binding import Binding
from textual.reactive import reactive
from textual import work
from textual.timer import Timer
from rich.text import Text
from rich.panel import Panel
from rich.table import Table

from messaging import SecureMessenger, MessageQueue


class ContactList(Static):
    """Widget for displaying contacts and groups."""

    def __init__(self, messenger: SecureMessenger, **kwargs):
        super().__init__(**kwargs)
        self.messenger = messenger
        self.selected_contact: Optional[str] = None
        self.selected_is_group: bool = False
        self.contacts_data: Dict[str, Dict] = {}
        self.groups_data: Dict[str, Dict] = {}

    def compose(self) -> ComposeResult:
        yield Label("Contacts & Groups", classes="section-title")
        with VerticalScroll(id="contact-list"):
            yield Static("Loading...", id="contact-content")

    def on_mount(self) -> None:
        self.refresh_contacts()
        # Set up auto-refresh timer
        self.set_timer(2.0, self.auto_refresh)

    def auto_refresh(self) -> None:
        """Auto-refresh contacts and check for new messages."""
        self.refresh_contacts()
        self.set_timer(2.0, self.auto_refresh)

    def refresh_contacts(self) -> None:
        """Refresh the contact and group lists."""
        try:
            # Get contacts
            contacts = self.messenger.list_contacts()
            self.contacts_data = contacts

            # Get groups
            groups = self.messenger.list_groups()
            self.groups_data = groups

            # Build the display
            content = self.query_one("#contact-content", Static)
            lines = []

            # Contacts section
            lines.append(Text("📇 CONTACTS", style="bold cyan"))
            if contacts:
                for name, info in contacts.items():
                    trust_level = self.messenger.contact_manager.get_contact_trust_level(name)
                    if trust_level == 2:  # blocked
                        trust_icon = "🔴 "
                        style = "red"
                    elif trust_level == 1:  # trusted
                        trust_icon = "🟢 "
                        style = "green"
                    else:  # unknown
                        trust_icon = "🟡 "
                        style = "yellow"

                    # Check if this is selected
                    prefix = "▶ " if name == self.selected_contact and not self.selected_is_group else "  "
                    lines.append(Text(f"{prefix}{trust_icon}{name}", style=style))
            else:
                lines.append(Text("  (no contacts)", style="dim"))

            lines.append(Text(""))

            # Groups section
            lines.append(Text("👥 GROUPS", style="bold cyan"))
            if groups:
                for name, info in groups.items():
                    members = info.get("members", [])
                    member_count = len(members)
                    prefix = "▶ " if name == self.selected_contact and self.selected_is_group else "  "
                    lines.append(Text(f"{prefix}👥 {name} ({member_count} members)"))
            else:
                lines.append(Text("  (no groups)", style="dim"))

            content.update("\n".join(str(line) for line in lines))

        except Exception as e:
            content = self.query_one("#contact-content", Static)
            content.update(f"[red]Error loading contacts: {e}[/red]")

    def select_contact(self, name: str, is_group: bool = False) -> None:
        """Select a contact or group."""
        self.selected_contact = name
        self.selected_is_group = is_group
        self.refresh_contacts()
        # Notify app of selection
        self.post_message(ContactSelected(name, is_group))


class ContactSelected(Message):
    """Message sent when a contact is selected."""
    def __init__(self, contact_name: str, is_group: bool):
        self.contact_name = contact_name
        self.is_group = is_group
        super().__init__()


class MessageView(RichLog):
    """Widget for displaying conversation messages."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.messenger: Optional[SecureMessenger] = None
        self.current_contact: Optional[str] = None
        self.current_is_group: bool = False
        self.auto_scroll = True
        self.message_widgets: List[Tuple[int, str, Dict]] = []  # (line_num, msg_id, msg_data)
        self._line_counter = 0

    def set_messenger(self, messenger: SecureMessenger) -> None:
        self.messenger = messenger

    def set_conversation(self, contact_name: str, is_group: bool = False) -> None:
        """Set the current conversation to display."""
        self.current_contact = contact_name
        self.current_is_group = is_group
        self.clear()
        self.message_widgets.clear()
        self._line_counter = 0
        self.load_history()

    def load_history(self) -> None:
        """Load and display conversation history."""
        if not self.messenger or not self.current_contact:
            return

        try:
            history = self.messenger.get_conversation_history(self.current_contact, limit=100)
            if not history:
                self.write(Text("No messages yet. Start the conversation!", style="dim italic"))
                return

            for msg in history:
                self.display_message(msg)

        except Exception as e:
            self.write(Text(f"Error loading history: {e}", style="red"))

    def display_message(self, msg: Dict) -> None:
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

        if direction == 'sent':
            # Sent message - right aligned, blue
            prefix = "▶ You"
            style = "bold blue"
        else:
            # Received message - left aligned, green
            sender = self.current_contact if is_group else "Unknown"
            prefix = f"◀ {sender}"
            style = "bold green"

        # Build message parts
        parts = []
        parts.append(Text(f"[{time_str}] ", style="dim"))

        # Add TTL countdown for ephemeral messages
        if ttl and ttl > 0:
            remaining = ttl - (time.time() - timestamp)
            if remaining > 0:
                parts.append(Text(f"⏳ {int(remaining)}s ", style="bold yellow"))
            else:
                parts.append(Text("💀 EXPIRED ", style="bold red"))

        parts.append(Text(f"{prefix}: ", style=style))

        # Check for special message types
        if deleted or text.startswith("[DELETED]"):
            parts.append(Text("[This message was deleted]", style="red strikethrough"))
        elif edited or text.startswith("[EDITED]"):
            parts.append(Text(text + " ✏️", style="yellow"))
        elif text.startswith("[Message encrypted"):
            parts.append(Text(text, style="dim italic"))
        else:
            parts.append(Text(text))

        self.write(Text.assemble(*parts))
        self._line_counter += 1
        self.message_widgets.append((self._line_counter, msg_id, msg))

    def add_message(self, sender: str, text: str, is_sent: bool = False) -> None:
        """Add a new message to the view."""
        time_str = time.strftime("%H:%M:%S")
        if is_sent:
            self.write(Text(f"[{time_str}] ▶ You: ", style="bold blue") + Text(text))
        else:
            self.write(Text(f"[{time_str}] ◀ {sender}: ", style="bold green") + Text(text))

        if self.auto_scroll:
            self.scroll_end()

    def update_ephemeral_timers(self) -> None:
        """Update TTL countdowns for ephemeral messages."""
        if not self.current_contact or not self.messenger:
            return

        # Reload history to get updated TTL values
        self.clear()
        self.message_widgets.clear()
        self._line_counter = 0
        self.load_history()


class InputArea(Static):
    """Widget for message input and sending."""

    def compose(self) -> ComposeResult:
        with Horizontal(id="input-container"):
            yield Input(placeholder="Type a message...", id="message-input")
            yield Button("Send", id="send-btn", variant="primary")
            yield Button("📎", id="attach-btn", variant="default")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send-btn":
            input_widget = self.query_one("#message-input", Input)
            message = input_widget.value.strip()
            if message:
                self.post_message(MessageSent(message))
                input_widget.value = ""

    def on_input_submitted(self, event: Input.Submitted) -> None:
        message = event.value.strip()
        if message:
            self.post_message(MessageSent(message))
            event.input.value = ""


class MessageSent(Message):
    """Message sent from input area."""
    def __init__(self, text: str):
        self.text = text
        super().__init__()


class ContactActionScreen(ModalScreen):
    """Modal screen for contact actions (add, trust, block, etc.)."""

    def __init__(self, action: str, messenger: SecureMessenger, **kwargs):
        super().__init__(**kwargs)
        self.action = action
        self.messenger = messenger

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label(f"{self.action.title()} Contact", id="modal-title")
            yield Input(placeholder="Contact name", id="contact-name")
            if self.action == "add":
                yield Input(placeholder="Public key (hex)", id="public-key")
                yield Input(placeholder="Signing key (hex, optional)", id="signing-key")
            yield Horizontal(
                Button("Confirm", id="confirm-btn", variant="primary"),
                Button("Cancel", id="cancel-btn", variant="default"),
                id="modal-buttons"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            name = self.query_one("#contact-name", Input).value.strip()
            if not name:
                self.notify("Contact name is required", severity="error")
                return

            if self.action == "add":
                pubkey = self.query_one("#public-key", Input).value.strip()
                signkey = self.query_one("#signing-key", Input).value.strip() or None
                if not pubkey:
                    self.notify("Public key is required", severity="error")
                    return
                try:
                    self.messenger.add_contact(name, pubkey, signkey)
                    self.notify(f"Contact '{name}' added successfully")
                    self.dismiss(True)
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")
            elif self.action == "trust":
                try:
                    success = self.messenger.trust_contact(name)
                    if success:
                        self.notify(f"Contact '{name}' is now trusted")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to trust contact '{name}'", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")
            elif self.action == "block":
                try:
                    success = self.messenger.block_contact(name)
                    if success:
                        self.notify(f"Contact '{name}' is now blocked")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to block contact '{name}'", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")
            elif self.action == "remove":
                try:
                    success = self.messenger.remove_contact(name)
                    if success:
                        self.notify(f"Contact '{name}' removed")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to remove contact '{name}'", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")

        elif event.button.id == "cancel-btn":
            self.dismiss(False)


class EditMessageScreen(ModalScreen):
    """Modal screen for editing a message."""

    def __init__(self, messenger: SecureMessenger, msg_id: str, current_text: str, **kwargs):
        super().__init__(**kwargs)
        self.messenger = messenger
        self.msg_id = msg_id
        self.current_text = current_text

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Edit Message", id="modal-title")
            yield Static(f"Message ID: {self.msg_id[:16]}...", id="msg-id-display")
            yield Input(value=self.current_text, placeholder="New message text", id="edit-input")
            yield Horizontal(
                Button("Save", id="save-btn", variant="primary"),
                Button("Cancel", id="cancel-btn", variant="default"),
                id="modal-buttons"
            )

    def on_mount(self) -> None:
        self.query_one("#edit-input", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-btn":
            new_text = self.query_one("#edit-input", Input).value.strip()
            if not new_text:
                self.notify("Message cannot be empty", severity="error")
                return
            try:
                success = self.messenger.edit_message(self.msg_id, new_text)
                if success:
                    self.notify("Message edited successfully")
                    self.dismiss(True)
                else:
                    self.notify("Failed to edit message (not your message or too old)", severity="error")
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")
        elif event.button.id == "cancel-btn":
            self.dismiss(False)


class DeleteMessageScreen(ModalScreen):
    """Modal screen for confirming message deletion."""

    def __init__(self, messenger: SecureMessenger, msg_id: str, preview: str, **kwargs):
        super().__init__(**kwargs)
        self.messenger = messenger
        self.msg_id = msg_id
        self.preview = preview[:100] + ("..." if len(preview) > 100 else "")

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Delete Message", id="modal-title")
            yield Static(f"Message ID: {self.msg_id[:16]}...", id="msg-id-display")
            yield Static(f"Preview: {self.preview}", id="msg-preview")
            yield Label("This will mark the message as deleted for all participants.", style="yellow")
            yield Horizontal(
                Button("Delete", id="delete-btn", variant="error"),
                Button("Cancel", id="cancel-btn", variant="default"),
                id="modal-buttons"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "delete-btn":
            try:
                success = self.messenger.delete_message(self.msg_id)
                if success:
                    self.notify("Message deleted successfully")
                    self.dismiss(True)
                else:
                    self.notify("Failed to delete message (not your message)", severity="error")
            except Exception as e:
                self.notify(f"Error: {e}", severity="error")
        elif event.button.id == "cancel-btn":
            self.dismiss(False)


class GroupActionScreen(ModalScreen):
    """Modal screen for group actions."""

    def __init__(self, action: str, messenger: SecureMessenger, **kwargs):
        super().__init__(**kwargs)
        self.action = action
        self.messenger = messenger

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label(f"{self.action.title()} Group", id="modal-title")
            yield Input(placeholder="Group name", id="group-name")
            if self.action in ["create", "add-member"]:
                yield Input(placeholder="Member names (comma-separated)", id="members")
            yield Horizontal(
                Button("Confirm", id="confirm-btn", variant="primary"),
                Button("Cancel", id="cancel-btn", variant="default"),
                id="modal-buttons"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-btn":
            name = self.query_one("#group-name", Input).value.strip()
            if not name:
                self.notify("Group name is required", severity="error")
                return

            if self.action == "create":
                members_input = self.query_one("#members", Input).value.strip()
                members = [m.strip() for m in members_input.split(",") if m.strip()]
                if not members:
                    self.notify("At least one member is required", severity="error")
                    return
                try:
                    success = self.messenger.create_group(name, members)
                    if success:
                        self.notify(f"Group '{name}' created successfully")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to create group '{name}'", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")
            elif self.action == "add-member":
                member = self.query_one("#members", Input).value.strip()
                if not member:
                    self.notify("Member name is required", severity="error")
                    return
                try:
                    success = self.messenger.add_group_member(name, member)
                    if success:
                        self.notify(f"Member '{member}' added to group '{name}'")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to add member", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")
            elif self.action == "remove-member":
                member = self.query_one("#members", Input).value.strip()
                if not member:
                    self.notify("Member name is required", severity="error")
                    return
                try:
                    success = self.messenger.remove_group_member(name, member)
                    if success:
                        self.notify(f"Member '{member}' removed from group '{name}'")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to remove member", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")
            elif self.action == "delete":
                try:
                    success = self.messenger.delete_group(name)
                    if success:
                        self.notify(f"Group '{name}' deleted")
                        self.dismiss(True)
                    else:
                        self.notify(f"Failed to delete group '{name}'", severity="error")
                except Exception as e:
                    self.notify(f"Error: {e}", severity="error")

        elif event.button.id == "cancel-btn":
            self.dismiss(False)


class GroupManagementScreen(ModalScreen):
    """Modal screen for viewing and managing group members."""

    def __init__(self, messenger: SecureMessenger, group_name: str, **kwargs):
        super().__init__(**kwargs)
        self.messenger = messenger
        self.group_name = group_name
        self.is_admin = False

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label(f"Group Management: {self.group_name}", id="modal-title")
            yield Static("Loading members...", id="members-display")
            yield Horizontal(
                Button("Refresh", id="refresh-btn", variant="default"),
                Button("Close", id="close-btn", variant="primary"),
                id="modal-buttons"
            )

    def on_mount(self) -> None:
        self.refresh_members()

    def refresh_members(self) -> None:
        """Refresh the member list."""
        try:
            members = self.messenger.contact_manager.get_group_members(self.group_name)
            groups = self.messenger.list_groups()
            group_info = groups.get(self.group_name, {})
            admins = group_info.get("admins", [])
            creator = group_info.get("creator", "")

            self.is_admin = self.messenger.username in admins or self.messenger.username == creator

            content = self.query_one("#members-display", Static)
            lines = []
            lines.append(Text(f"Creator: {creator}", style="bold cyan"))
            lines.append(Text(f"Admins: {', '.join(admins) if admins else 'None'}", style="cyan"))
            lines.append(Text(""))
            lines.append(Text("Members:", style="bold"))

            for member in members:
                admin_badge = " 👑" if member in admins else ""
                creator_badge = " ⭐" if member == creator else ""
                current_badge = " (you)" if member == self.messenger.username else ""
                lines.append(Text(f"  • {member}{admin_badge}{creator_badge}{current_badge}"))

            if not self.is_admin:
                lines.append(Text(""))
                lines.append(Text("You are not an admin of this group.", style="dim"))

            content.update("\n".join(str(line) for line in lines))

        except Exception as e:
            content = self.query_one("#members-display", Static)
            content.update(f"[red]Error loading members: {e}[/red]")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "refresh-btn":
            self.refresh_members()
        elif event.button.id == "close-btn":
            self.dismiss()


class SettingsScreen(ModalScreen):
    """Modal screen for settings."""

    def __init__(self, messenger: SecureMessenger, **kwargs):
        super().__init__(**kwargs)
        self.messenger = messenger

    def compose(self) -> ComposeResult:
        with Container(id="modal-container"):
            yield Label("Settings", id="modal-title")
            yield Label(f"Username: {self.messenger.username}", id="settings-username")
            yield Label(f"Data Directory: {self.messenger.data_dir}")
            yield Label(f"Queue Directory: {self.messenger.queue_dir}")
            yield Label(f"Networking: {'Enabled' if self.messenger.use_networking else 'Disabled'}")
            if self.messenger.use_networking:
                yield Label(f"Host: {self.messenger.host}:{self.messenger.port}")
                yield Label(f"Server Mode: {'Yes' if self.messenger.is_server else 'No'}")
                yield Label(f"Secure (WSS): {'Yes' if self.messenger.secure else 'No'}")
                yield Label(f"Auth Method: {self.messenger.auth_method.upper()}")
            yield Label(f"Your Public Key: {self.messenger.identity_manager.get_public_key_hex()}")
            signing_key = self.messenger.identity_manager.get_signing_public_key_hex()
            if signing_key:
                yield Label(f"Your Signing Key: {signing_key}")
            yield Horizontal(
                Button("Close", id="close-btn", variant="primary"),
                id="modal-buttons"
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-btn":
            self.dismiss()


class EncryptedMessagingApp(App):
    """Main TUI Application for Encrypted Messaging."""

    CSS = """
    Screen {
        background: $surface;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #sidebar {
        width: 35%;
        min-width: 40;
        max-width: 60;
        border-right: solid $primary;
        background: $surface-lighten-1;
        padding: 1;
    }

    #chat-area {
        width: 65%;
        min-width: 60;
        layout: vertical;
    }

    #message-view {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        background: $surface;
    }

    #input-area {
        height: auto;
        min-height: 3;
        border-top: solid $primary;
        padding: 1;
    }

    #input-container {
        layout: horizontal;
        height: 3;
    }

    #message-input {
        width: 1fr;
    }

    #send-btn {
        width: 10;
        margin-left: 1;
    }

    #attach-btn {
        width: 5;
        margin-left: 1;
    }

    .section-title {
        text-align: center;
        text-style: bold;
        color: $accent;
        margin-bottom: 1;
    }

    #contact-list {
        height: 1fr;
    }

    #contact-content {
        padding: 1;
    }

    #modal-container {
        width: 60;
        height: auto;
        max-height: 80%;
        border: thick $primary;
        background: $surface;
        padding: 2;
        align: center middle;
    }

    #modal-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    #modal-buttons {
        layout: horizontal;
        margin-top: 1;
        align: center middle;
    }

    #modal-buttons Button {
        margin: 0 1;
    }

    RichLog {
        background: $surface;
    }

    Input {
        border: solid $primary;
    }

    Button {
        border: solid $primary;
    }

    Button:hover {
        background: $primary;
        color: $surface;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("c", "add_contact", "Add Contact"),
        Binding("t", "trust_contact", "Trust Contact"),
        Binding("b", "block_contact", "Block Contact"),
        Binding("r", "remove_contact", "Remove Contact"),
        Binding("g", "create_group", "Create Group"),
        Binding("a", "add_group_member", "Add Member"),
        Binding("d", "delete_group", "Delete Group"),
        Binding("s", "settings", "Settings"),
        Binding("ctrl+r", "refresh", "Refresh"),
        Binding("ctrl+l", "clear_chat", "Clear Chat"),
        Binding("e", "edit_message", "Edit Message"),
        Binding("delete", "delete_message", "Delete Message"),
        Binding("m", "manage_group", "Manage Group"),
        Binding("ctrl+e", "send_ephemeral", "Ephemeral Msg"),
    ]

    def __init__(self, username: str, data_dir: str = "./data", queue_dir: str = "./queue",
                 use_networking: bool = False, host: str = "localhost", port: int = 8765,
                 is_server: bool = False, auth_method: str = "tofu", secure: bool = False):
        super().__init__()
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
        self.message_timer: Optional[Timer] = None
        self.polling = True

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="main-container"):
            with Vertical(id="sidebar"):
                yield ContactList(id="contact-list", messenger=None)
            with Vertical(id="chat-area"):
                yield MessageView(id="message-view", wrap=True, highlight=True, markup=True)
                yield InputArea(id="input-area")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize the app and messenger."""
        self.title = f"Encrypted Messaging - {self.username}"
        self.sub_title = f"{'🔐 Secure' if self.use_networking else '📁 File-based'} | {self.auth_method.upper()}"

        # Initialize messenger
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
                new_contact_callback=self.on_new_contact
            )

            # Set messenger on contact list
            contact_list = self.query_one("#contact-list", ContactList)
            contact_list.messenger = self.messenger

            # Set messenger on message view
            message_view = self.query_one("#message-view", MessageView)
            message_view.set_messenger(self.messenger)

            # Start message polling
            self.start_message_polling()

            self.notify(f"Connected as {self.username}")

        except Exception as e:
            self.notify(f"Failed to initialize: {e}", severity="error")
            self.exit()

    def on_new_contact(self, name: str, public_key: bytes) -> None:
        """Callback for new contact (TOFU)."""
        self.call_from_thread(self.notify, f"New contact request from {name}", severity="warning")

    def start_message_polling(self) -> None:
        """Start periodic message polling."""
        self.message_timer = self.set_interval(1.0, self.poll_messages)

    def poll_messages(self) -> None:
        """Poll for new messages."""
        if not self.messenger or not self.polling:
            return

        try:
            messages = self.messenger.receive_and_process_messages()
            if messages:
                message_view = self.query_one("#message-view", MessageView)
                for sender, text in messages:
                    # Only show if it's for the current conversation
                    current_contact = message_view.current_contact
                    current_is_group = message_view.current_is_group

                    if current_contact:
                        # Check if this message is for current conversation
                        if current_is_group:
                            # For groups, check if sender is in the group
                            group_members = self.messenger.contact_manager.get_group_members(current_contact)
                            if sender in group_members:
                                message_view.add_message(sender, text)
                        else:
                            if sender == current_contact:
                                message_view.add_message(sender, text)
                    else:
                        # No conversation selected, just notify
                        self.notify(f"New message from {sender}: {text[:50]}...", timeout=5)

                # Refresh contacts to update trust levels
                contact_list = self.query_one("#contact-list", ContactList)
                contact_list.refresh_contacts()

            # Update ephemeral message timers for current conversation
            message_view = self.query_one("#message-view", MessageView)
            if message_view.current_contact:
                message_view.update_ephemeral_timers()

        except Exception as e:
            # Silently ignore polling errors
            pass

    def on_contact_selected(self, event: ContactSelected) -> None:
        """Handle contact selection."""
        message_view = self.query_one("#message-view", MessageView)
        message_view.set_conversation(event.contact_name, event.is_group)
        self.sub_title = f"Chatting with {event.contact_name} {'(Group)' if event.is_group else ''}"

    def on_message_sent(self, event: MessageSent) -> None:
        """Handle sending a message."""
        if not self.messenger:
            return

        message_view = self.query_one("#message-view", MessageView)
        contact = message_view.current_contact
        is_group = message_view.current_is_group

        if not contact:
            self.notify("No contact selected", severity="warning")
            return

        try:
            success = self.messenger.send_message(contact, event.text)
            if success:
                message_view.add_message("You", event.text, is_sent=True)
                self.notify("Message sent")
            else:
                self.notify("Failed to send message", severity="error")
        except Exception as e:
            self.notify(f"Error sending: {e}", severity="error")

    def action_add_contact(self) -> None:
        """Show add contact dialog."""
        if not self.messenger:
            return
        self.push_screen(ContactActionScreen("add", self.messenger))

    def action_trust_contact(self) -> None:
        """Show trust contact dialog."""
        if not self.messenger:
            return
        contact_list = self.query_one("#contact-list", ContactList)
        if contact_list.selected_contact and not contact_list.selected_is_group:
            self.push_screen(ContactActionScreen("trust", self.messenger))
        else:
            self.notify("Select a contact first", severity="warning")

    def action_block_contact(self) -> None:
        """Show block contact dialog."""
        if not self.messenger:
            return
        contact_list = self.query_one("#contact-list", ContactList)
        if contact_list.selected_contact and not contact_list.selected_is_group:
            self.push_screen(ContactActionScreen("block", self.messenger))
        else:
            self.notify("Select a contact first", severity="warning")

    def action_remove_contact(self) -> None:
        """Show remove contact dialog."""
        if not self.messenger:
            return
        contact_list = self.query_one("#contact-list", ContactList)
        if contact_list.selected_contact and not contact_list.selected_is_group:
            self.push_screen(ContactActionScreen("remove", self.messenger))
        else:
            self.notify("Select a contact first", severity="warning")

    def action_create_group(self) -> None:
        """Show create group dialog."""
        if not self.messenger:
            return
        self.push_screen(GroupActionScreen("create", self.messenger))

    def action_add_group_member(self) -> None:
        """Show add group member dialog."""
        if not self.messenger:
            return
        contact_list = self.query_one("#contact-list", ContactList)
        if contact_list.selected_contact and contact_list.selected_is_group:
            self.push_screen(GroupActionScreen("add-member", self.messenger))
        else:
            self.notify("Select a group first", severity="warning")

    def action_delete_group(self) -> None:
        """Show delete group dialog."""
        if not self.messenger:
            return
        contact_list = self.query_one("#contact-list", ContactList)
        if contact_list.selected_contact and contact_list.selected_is_group:
            self.push_screen(GroupActionScreen("delete", self.messenger))
        else:
            self.notify("Select a group first", severity="warning")

    def action_settings(self) -> None:
        """Show settings dialog."""
        if not self.messenger:
            return
        self.push_screen(SettingsScreen(self.messenger))

    def action_refresh(self) -> None:
        """Refresh contacts and messages."""
        contact_list = self.query_one("#contact-list", ContactList)
        contact_list.refresh_contacts()

        message_view = self.query_one("#message-view", MessageView)
        if message_view.current_contact:
            message_view.load_history()
        self.notify("Refreshed")

    def action_clear_chat(self) -> None:
        """Clear the chat view."""
        message_view = self.query_one("#message-view", MessageView)
        message_view.clear()
        if message_view.current_contact:
            message_view.load_history()
        self.notify("Chat cleared")

    def action_edit_message(self) -> None:
        """Edit the last sent message."""
        if not self.messenger:
            return
        message_view = self.query_one("#message-view", MessageView)
        if not message_view.current_contact:
            self.notify("No conversation selected", severity="warning")
            return

        # Get the last sent message from history
        history = self.messenger.get_conversation_history(message_view.current_contact, limit=10)
        last_sent = None
        for msg in reversed(history):
            if msg.get('direction') == 'sent' and not msg.get('deleted', False):
                last_sent = msg
                break

        if not last_sent:
            self.notify("No editable message found", severity="warning")
            return

        msg_id = last_sent.get('msg_id', '')
        text = last_sent.get('text', '')
        self.push_screen(EditMessageScreen(self.messenger, msg_id, text))

    def action_delete_message(self) -> None:
        """Delete the last sent message."""
        if not self.messenger:
            return
        message_view = self.query_one("#message-view", MessageView)
        if not message_view.current_contact:
            self.notify("No conversation selected", severity="warning")
            return

        # Get the last sent message from history
        history = self.messenger.get_conversation_history(message_view.current_contact, limit=10)
        last_sent = None
        for msg in reversed(history):
            if msg.get('direction') == 'sent' and not msg.get('deleted', False):
                last_sent = msg
                break

        if not last_sent:
            self.notify("No deletable message found", severity="warning")
            return

        msg_id = last_sent.get('msg_id', '')
        text = last_sent.get('text', '')
        self.push_screen(DeleteMessageScreen(self.messenger, msg_id, text))

    def action_manage_group(self) -> None:
        """Show group management screen."""
        if not self.messenger:
            return
        contact_list = self.query_one("#contact-list", ContactList)
        if contact_list.selected_contact and contact_list.selected_is_group:
            self.push_screen(GroupManagementScreen(self.messenger, contact_list.selected_contact))
        else:
            self.notify("Select a group first", severity="warning")

    def action_send_ephemeral(self) -> None:
        """Send an ephemeral (self-destructing) message."""
        if not self.messenger:
            return
        message_view = self.query_one("#message-view", MessageView)
        contact = message_view.current_contact
        is_group = message_view.current_is_group

        if not contact:
            self.notify("No contact selected", severity="warning")
            return

        # Show input dialog for ephemeral message
        from textual.widgets import Input
        from textual.screen import ModalScreen
        from textual.containers import Container, Horizontal
        from textual.widgets import Button, Label

        class EphemeralInputScreen(ModalScreen):
            def __init__(self, messenger, contact, is_group, **kwargs):
                super().__init__(**kwargs)
                self.messenger = messenger
                self.contact = contact
                self.is_group = is_group

            def compose(self) -> ComposeResult:
                with Container(id="modal-container"):
                    yield Label("Send Ephemeral Message", id="modal-title")
                    yield Label("Message will self-destruct after specified seconds")
                    yield Input(placeholder="Message text", id="msg-input")
                    yield Input(placeholder="TTL in seconds (default: 30)", id="ttl-input", value="30")
                    yield Horizontal(
                        Button("Send", id="send-btn", variant="primary"),
                        Button("Cancel", id="cancel-btn", variant="default"),
                        id="modal-buttons"
                    )

            def on_mount(self) -> None:
                self.query_one("#msg-input", Input).focus()

            def on_button_pressed(self, event: Button.Pressed) -> None:
                if event.button.id == "send-btn":
                    text = self.query_one("#msg-input", Input).value.strip()
                    ttl_str = self.query_one("#ttl-input", Input).value.strip()
                    if not text:
                        self.notify("Message cannot be empty", severity="error")
                        return
                    try:
                        ttl = int(ttl_str) if ttl_str else 30
                    except ValueError:
                        ttl = 30
                    try:
                        success = self.messenger.send_message(self.contact, text, ttl=ttl)
                        if success:
                            self.notify(f"Ephemeral message sent (TTL: {ttl}s)")
                            self.dismiss(True)
                        else:
                            self.notify("Failed to send message", severity="error")
                    except Exception as e:
                        self.notify(f"Error: {e}", severity="error")
                elif event.button.id == "cancel-btn":
                    self.dismiss(False)

        self.push_screen(EphemeralInputScreen(self.messenger, contact, is_group))

    def on_unmount(self) -> None:
        """Cleanup on exit."""
        if self.message_timer:
            self.message_timer.stop()
        if self.messenger:
            self.messenger.message_queue.stop()


def run_tui(username: str, data_dir: str = "./data", queue_dir: str = "./queue",
            use_networking: bool = False, host: str = "localhost", port: int = 8765,
            is_server: bool = False, auth_method: str = "tofu", secure: bool = False):
    """Run the TUI application."""
    app = EncryptedMessagingApp(
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
    app.run()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Encrypted Messaging TUI")
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

    run_tui(
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