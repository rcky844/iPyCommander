import logging
import json
from typing import Callable, Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, ListItem, ListView, Static, TextArea
from pymobiledevice3.cli.cli_common import default_json_encoder, prompt_device_list
from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.installation_proxy import InstallationProxyService
from pymobiledevice3.usbmux import select_devices_by_connection_type

class SelectionDialog(ModalScreen):
    def __init__(self, title: str = "Selection dialog",
                 positive: str = "Positive", negative: str = "Negative",
                 callback: Optional[Callable[[Button.Pressed], None]] = None):
        super().__init__()
        self.title = title
        self.positive = positive
        self.negative = negative
        self.callback = callback

    def compose(self) -> ComposeResult:
        yield Grid(
            Label(self.title, id="title"),
            Button(self.positive, variant="error", id="positive"),
            Button(self.negative, variant="primary", id="negative"),
            id="dialog",
        )
    def on_button_pressed(self, event: Button.Pressed) -> None:
        if self.callback is not None:
            self.callback(event)

class CommenderApp(App):
    BINDINGS = [("q", "quit", "Quit")]
    CSS_PATH = "main.tcss"

    def __init__(self):
        super().__init__()
        self.device = None
        self.active_item: str = ""

        # Get lockdown client
        self.connect()

    def connect(self):
        devices = select_devices_by_connection_type(connection_type='USB')
        if not any(devices):
            self.device = None
            return

        if len(devices) == 1:
            self.device = create_using_usbmux(serial=devices[0].serial)
        else:
            self.device = prompt_device_list(
                [create_using_usbmux(serial=dev.serial) for dev in devices])

    def compose(self) -> ComposeResult:
        yield Header()
        with Static(classes="box top"):
            yield Static(id="status")
        with Horizontal(classes="container bottom"):
            yield Vertical(id="menu-box", classes="box bottom menu")
            with Vertical(id="content-box", classes="box bottom view"):
                yield Static("Please select an option.")
        yield Footer()

    def action_draw_basic(self, menu_extras: str = ""):
        # Draw top box
        if self.device is None:
            self.query_one("#status", Static).update("Device: None")
        else:
            di = self.device.short_info
            df = f'{di['DeviceName']} ({di['ProductType']})'
            dv = f'{di['ProductVersion']} ({di['BuildVersion']})'
            ds = self.device.get_value(key='SerialNumber')
            self.query_one("#status", Static).update(f"Device: {df}\nOS version: {dv}\nSerial number: {ds}")

        # Draw bottom menu box
        menu_box = self.query_one("#menu-box", Vertical)
        if len(menu_extras) > 0:
            has_matched = True
            match menu_extras:
                case "apps":
                    menu_box.mount(ListView(
                        ListItem(Static("List installed applications", name="apps-list"))
                    ))
                case _:
                    has_matched = False

            # Check for already added child menu
            if has_matched:
                if len(menu_box.children) > 2:
                    menu_box.children[2].remove()
                menu_box.children[1].focus()
            else:
                if len(menu_box.children) > 1:
                    menu_box.children[1].remove()
            return
        menu_box.remove_children()

        if self.device is None:
            menu_box.mount(ListView(ListItem(Static("Reconnect", name="reconnect"))))
        else:
            menu_box.mount(ListView(
                ListItem(Static("Restore/Downgrade", name="restore")),
                ListItem(Static("Jailbreak", name="jb")),
                ListItem(Static("Applications", name="apps")),
                ListItem(Static("Management", name="manage")),
                ListItem(Static("Utilities", name="utils")),
                ListItem(Static("Information", name="info")),
            ))

    def on_mount(self) -> None:
        self.title = "iPyCommender"
        self.action_draw_basic()

    def on_list_view_selected(self, event: ListView.Selected):
        content_box = self.query_one("#content-box", Vertical)
        content_box.remove_children()

        item_name = event.item.children[0].name
        menu_extras = item_name
        match item_name:
            # Activated menu
            case "apps":
                content_box.mount(Static("Please select an option."))

            case "apps-list":
                content_box.mount(
                    TextArea.code_editor(
                        text=json.dumps(InstallationProxyService(lockdown=self.device).get_apps(),
                                        sort_keys=True, indent=4, default=default_json_encoder),
                        language="json", read_only=True
                    )
                )
                menu_extras = "apps"
            case "info":
                content_box.mount(
                    TextArea.code_editor(
                        text=json.dumps(self.device.all_values,
                                        sort_keys=True, indent=4, default=default_json_encoder),
                        language="json", read_only=True
                    )
                )

            # No device menu
            case "reconnect":
                self.connect()

            # Default
            case _:
                content_box.mount(Static("Not supported yet :)"))
        self.action_draw_basic(menu_extras)

    def action_quit(self) -> None:
        exit()

if __name__ == '__main__':
    logging.basicConfig(format="[%(levelname)s] %(name)s: %(message)s")

    app = CommenderApp()
    app.run()
