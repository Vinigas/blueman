from gettext import gettext as _
from typing import Callable, Union

from _blueman import RFCOMMError
from gi.repository import GLib

from blueman.Service import Service
from blueman.bluez.errors import BluezDBusException
from blueman.main.NetworkManager import NMConnectionError
from blueman.main.PluginManager import StopException
from blueman.plugins.AppletPlugin import AppletPlugin
from blueman.bluez.Device import Device
from blueman.services.Functions import get_service

import logging

from blueman.services.meta import SerialService, NetworkService


class DBusService(AppletPlugin):
    __depends__ = ["StatusIcon"]
    __unloadable__ = False
    __description__ = _("Provides DBus API for other Blueman components")
    __author__ = "Walmis"

    def on_load(self):

        AppletPlugin.add_method(self.on_rfcomm_connected)
        AppletPlugin.add_method(self.on_rfcomm_disconnect)
        AppletPlugin.add_method(self.rfcomm_connect_handler)
        AppletPlugin.add_method(self.service_connect_handler)
        AppletPlugin.add_method(self.service_disconnect_handler)

        self._add_dbus_method("QueryPlugins", (), "as", self.parent.Plugins.get_loaded)
        self._add_dbus_method("QueryAvailablePlugins", (), "as", lambda: list(self.parent.Plugins.get_classes()))
        self._add_dbus_method("SetPluginConfig", ("s", "b"), "", self.parent.Plugins.set_config)
        self._add_dbus_method("ConnectService", ("o", "s"), "", self.connect_service, is_async=True)
        self._add_dbus_method("DisconnectService", ("o", "s", "d"), "", self._disconnect_service, is_async=True)
        self._add_dbus_method("OpenPluginDialog", (), "", self._open_plugin_dialog)

    def on_device_disconnect(self, device):
        pass

    def connect_service(self, object_path: str, uuid: str, ok: Callable[[], None],
                        err: Callable[[Union[BluezDBusException, NMConnectionError,
                                             RFCOMMError, GLib.Error, str]], None]) -> None:
        try:
            self.parent.Plugins.RecentConns
        except KeyError:
            logging.warning("RecentConns plugin is unavailable")
        else:
            self.parent.Plugins.RecentConns.notify(object_path, uuid)

        if uuid == '00000000-0000-0000-0000-000000000000':
            device = Device(obj_path=object_path)
            device.connect(reply_handler=ok, error_handler=err)
        else:
            def cb(_inst, ret):
                if ret:
                    raise StopException

            service = get_service(Device(obj_path=object_path), uuid)
            assert service is not None

            if isinstance(service, SerialService) and 'NMDUNSupport' in self.parent.Plugins.get_loaded():
                self.parent.Plugins.run_ex("service_connect_handler", cb, service, ok, err)
            elif isinstance(service, SerialService) and 'PPPSupport' in self.parent.Plugins.get_loaded():
                def reply(rfcomm):
                    self.parent.Plugins.run("on_rfcomm_connected", service, rfcomm)
                    ok()

                rets = self.parent.Plugins.run("rfcomm_connect_handler", service, reply, err)
                if True in rets:
                    pass
                else:
                    logging.info("No handler registered")
                    err("Service not supported\nPossibly the plugin that handles this service is not loaded")
            else:
                if not self.parent.Plugins.run_ex("service_connect_handler", cb, service, ok, err) \
                        and isinstance(service, (SerialService, NetworkService)):
                    service.connect(reply_handler=lambda *args: ok(), error_handler=err)

    def _disconnect_service(self, object_path: str, uuid: str, port: int, ok: Callable[[], None],
                            err: Callable[[Union[BluezDBusException, NMConnectionError,
                                                 GLib.Error, str]], None]) -> None:
        if uuid == '00000000-0000-0000-0000-000000000000':
            device = Device(obj_path=object_path)
            device.disconnect(reply_handler=ok, error_handler=err)
        else:
            def cb(_inst, ret):
                if ret:
                    raise StopException

            service = get_service(Device(obj_path=object_path), uuid)
            assert service is not None

            if isinstance(service, SerialService) and 'NMDUNSupport' in self.parent.Plugins.get_loaded():
                self.parent.Plugins.run_ex("service_disconnect_handler", cb, service, ok, err)
            elif isinstance(service, SerialService) and 'PPPSupport' in self.parent.Plugins.get_loaded():
                service.disconnect(port, reply_handler=ok, error_handler=err)

                self.parent.Plugins.run("on_rfcomm_disconnect", port)

                logging.info("Disconnecting rfcomm device")
            else:
                if not self.parent.Plugins.run_ex("service_disconnect_handler", cb, service, ok, err) \
                        and isinstance(service, NetworkService):
                    service.disconnect(reply_handler=ok, error_handler=err)

    def service_connect_handler(self, service: Service, ok: Callable[..., None], err: Callable[..., None]) -> bool:
        return False

    def service_disconnect_handler(self, service: Service, ok: Callable[..., None], err: Callable[..., None]) -> bool:
        return False

    def _open_plugin_dialog(self):
        self.parent.Plugins.StandardItems.on_plugins()

    def rfcomm_connect_handler(self, service: Service, reply: Callable[..., None], err: Callable[..., None]) -> bool:
        return False

    def on_rfcomm_connected(self, service, port):
        pass

    def on_rfcomm_disconnect(self, port):
        pass
