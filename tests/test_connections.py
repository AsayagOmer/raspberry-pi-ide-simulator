"""Tests for the Connection entity, ConnectionManager, and component integration.

Covers:
 - Connection entity creation, repr, is_aligned
 - ConnectionManager.try_connect with exact-position snapping
 - ConnectionManager.disconnect and disconnect_all
 - ConnectionManager.reconnect_by_position (state reload)
 - Port definitions (get_ports) on all components
 - snap_port_to positioning components exactly
 - Pirate Audio connect / disconnect / delete via CM
 - USB Speaker connect / disconnect / delete via CM
 - hardware.log logging through ConnectionManager
 - HardwareAPI finding active connected components
 - Threshold edge-cases (just inside / just outside)
"""

import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from unittest.mock import MagicMock, patch, mock_open
from components.base_component import BaseComponent
from components.raspberry_pi import RaspberryPi
from components.pirate_audio import PirateAudio
from components.usb_speaker import USBSpeaker
from components.connection import Connection, ConnectionManager
from hardware_api import HardwareAPI


# ── Lightweight mocks ──────────────────────────────────────────────────────

class MockCanvas:
    """Minimal canvas that satisfies component init without tkinter."""
    def __init__(self, app):
        self._app = app
        self._id = 0

    def winfo_toplevel(self):
        return self._app

    def _nid(self):
        self._id += 1
        return self._id

    def create_rectangle(self, *a, **kw): return self._nid()
    def create_oval(self, *a, **kw):      return self._nid()
    def create_text(self, *a, **kw):      return self._nid()
    def create_window(self, *a, **kw):    return self._nid()
    def create_line(self, *a, **kw):      return self._nid()

    def delete(self, *a, **kw): pass
    def move(self, *a, **kw): pass
    def coords(self, *a, **kw): pass
    def tag_bind(self, *a, **kw): pass
    def tag_raise(self, *a, **kw): pass
    def tag_lower(self, *a, **kw): pass
    def config(self, **kw): pass
    def itemconfig(self, *a, **kw): pass
    def find_withtag(self, tag): return ()
    def gettags(self, item_id): return ()


class MockApp:
    """Stand-in for IDEApp – has components, button_states, zoom, and a CM."""
    def __init__(self):
        self.components = []
        self.button_states = {'A': False, 'B': False, 'X': False, 'Y': False}
        self.hovered_component = None
        self.zoom_factor = 1.0
        self.connection_manager = ConnectionManager()
        self.canvas = MockCanvas(self)

    def save_hardware_state(self): pass
    def after(self, ms, func): func()
    def log_console(self, text): pass


def _make_components():
    """Instantiate a RPi, PirateAudio, and USBSpeaker on a shared mock."""
    app = MockApp()
    canvas = app.canvas
    pi  = RaspberryPi(canvas, 200, 200)
    pa  = PirateAudio(canvas, 0, 0)
    spk = USBSpeaker(canvas, 500, 500)
    app.components = [pi, pa, spk]
    return app, pi, pa, spk


# ═══════════════════════════════════════════════════════════════════════════
#  1.  Connection entity
# ═══════════════════════════════════════════════════════════════════════════

class TestConnectionEntity(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()

    def test_repr(self):
        conn = Connection(self.pa, "gpio_socket", self.pi, "gpio_header")
        self.assertIn("PirateAudio", repr(conn))
        self.assertIn("RaspberryPi", repr(conn))

    def test_is_aligned_when_at_same_pos(self):
        """Ports at the same position ⇒ is_aligned == True."""
        # Snap PA socket to RPi GPIO
        self.pa.snap_port_to("gpio_socket", self.pi.gpio_x, self.pi.gpio_y)
        conn = Connection(self.pa, "gpio_socket", self.pi, "gpio_header")
        self.assertTrue(conn.is_aligned)

    def test_is_aligned_false_when_apart(self):
        conn = Connection(self.pa, "gpio_socket", self.pi, "gpio_header")
        self.assertFalse(conn.is_aligned)

    def test_get_source_pos_and_target_pos(self):
        conn = Connection(self.pa, "gpio_socket", self.pi, "gpio_header")
        sp = conn.get_source_pos()
        tp = conn.get_target_pos()
        self.assertIsNotNone(sp)
        self.assertIsNotNone(tp)
        self.assertEqual(sp, (self.pa.socket_x, self.pa.socket_y))
        self.assertEqual(tp, (self.pi.gpio_x, self.pi.gpio_y))

    def test_get_pos_returns_none_for_bad_port(self):
        conn = Connection(self.pa, "nonexistent", self.pi, "gpio_header")
        self.assertIsNone(conn.get_source_pos())


# ═══════════════════════════════════════════════════════════════════════════
#  2.  Port definitions (get_ports)
# ═══════════════════════════════════════════════════════════════════════════

class TestPortDefinitions(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()

    def test_rpi_has_three_in_ports(self):
        ports = self.pi.get_ports()
        self.assertEqual(len(ports), 3)
        names = {p["name"] for p in ports}
        self.assertEqual(names, {"gpio_header", "usb2_port", "usb3_port"})
        for p in ports:
            self.assertEqual(p["direction"], "in")

    def test_pirate_audio_has_gpio_socket_out(self):
        ports = self.pa.get_ports()
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0]["name"], "gpio_socket")
        self.assertEqual(ports[0]["direction"], "out")

    def test_usb_speaker_has_usb_plug_out(self):
        ports = self.spk.get_ports()
        self.assertEqual(len(ports), 1)
        self.assertEqual(ports[0]["name"], "usb_plug")
        self.assertEqual(ports[0]["direction"], "out")

    def test_base_component_has_empty_ports(self):
        base = BaseComponent(self.app.canvas, 0, 0)
        self.assertEqual(base.get_ports(), [])


# ═══════════════════════════════════════════════════════════════════════════
#  3.  snap_port_to — exact position matching
# ═══════════════════════════════════════════════════════════════════════════

class TestSnapPortTo(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()

    def test_pirate_audio_snap_aligns_exactly(self):
        target_x, target_y = self.pi.gpio_x, self.pi.gpio_y
        self.pa.snap_port_to("gpio_socket", target_x, target_y)
        self.assertAlmostEqual(self.pa.socket_x, target_x, places=5)
        self.assertAlmostEqual(self.pa.socket_y, target_y, places=5)

    def test_usb_speaker_snap_aligns_exactly(self):
        target_x, target_y = self.pi.usb2_x, self.pi.usb2_y
        self.spk.snap_port_to("usb_plug", target_x, target_y)
        self.assertEqual(self.spk.plug_x, target_x)
        self.assertEqual(self.spk.plug_y, target_y)

    def test_snap_unknown_port_does_nothing(self):
        old_x, old_y = self.pa.socket_x, self.pa.socket_y
        self.pa.snap_port_to("nonexistent", 999, 999)
        self.assertEqual(self.pa.socket_x, old_x)
        self.assertEqual(self.pa.socket_y, old_y)


# ═══════════════════════════════════════════════════════════════════════════
#  4.  ConnectionManager.try_connect
# ═══════════════════════════════════════════════════════════════════════════

class TestTryConnect(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def _place_pa_near_gpio(self):
        """Position PA socket near RPi GPIO header."""
        z = self.app.zoom_factor
        gx, gy = 145, self.pa.h
        self.pa.x = self.pi.gpio_x - gx * z + 5  # +5px off — still within 40
        self.pa.y = self.pi.gpio_y - gy * z + 5
        self.pa.update_ports()

    def _place_plug_near_usb2(self):
        """Position USB plug near RPi USB 2.0 port."""
        self.spk.plug_x = self.pi.usb2_x + 5
        self.spk.plug_y = self.pi.usb2_y + 5

    # -- PA → GPIO --

    def test_pa_connects_and_returns_connection(self):
        self._place_pa_near_gpio()
        with patch("builtins.open", mock_open()):
            conn = self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
        self.assertIsNotNone(conn)
        self.assertIsInstance(conn, Connection)
        self.assertIs(conn.source, self.pa)
        self.assertIs(conn.target, self.pi)

    def test_pa_ports_exactly_aligned_after_connect(self):
        """The whole point: after try_connect the ports must be at the SAME position."""
        self._place_pa_near_gpio()
        with patch("builtins.open", mock_open()):
            conn = self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
        self.assertTrue(conn.is_aligned,
                        f"Source {conn.get_source_pos()} != Target {conn.get_target_pos()}")

    def test_pa_connected_to_set(self):
        self._place_pa_near_gpio()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
        self.assertIs(self.pa.connected_to, self.pi)

    def test_pa_connection_stored_in_manager(self):
        self._place_pa_near_gpio()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
        self.assertEqual(len(self.cm.connections), 1)
        self.assertIs(self.cm.connections[0].source, self.pa)

    def test_pa_too_far_returns_none(self):
        self.pa.x = 0
        self.pa.y = 0
        self.pa.update_ports()
        conn = self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
        self.assertIsNone(conn)
        self.assertIsNone(self.pa.connected_to)

    def test_pa_idempotent_reconnect(self):
        """Calling try_connect twice with same position returns same connection."""
        self._place_pa_near_gpio()
        with patch("builtins.open", mock_open()):
            c1 = self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
            c2 = self.cm.try_connect(self.pa, self.app.components, zoom=self.app.zoom_factor)
        self.assertIs(c1, c2)
        self.assertEqual(len(self.cm.connections), 1)

    # -- Speaker → USB 2.0 --

    def test_spk_connects_and_ports_aligned(self):
        self._place_plug_near_usb2()
        with patch("builtins.open", mock_open()):
            conn = self.cm.try_connect(self.spk, self.app.components, zoom=self.app.zoom_factor)
        self.assertIsNotNone(conn)
        self.assertTrue(conn.is_aligned,
                        f"Source {conn.get_source_pos()} != Target {conn.get_target_pos()}")

    def test_spk_connected_to_set(self):
        self._place_plug_near_usb2()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.spk, self.app.components, zoom=self.app.zoom_factor)
        self.assertIs(self.spk.connected_to, self.pi)


# ═══════════════════════════════════════════════════════════════════════════
#  5.  ConnectionManager.disconnect
# ═══════════════════════════════════════════════════════════════════════════

class TestDisconnect(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager
        # Pre-connect PA
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z
        self.pa.y = self.pi.gpio_y - self.pa.h * z
        self.pa.update_ports()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=z)

    def test_disconnect_removes_connection(self):
        with patch("builtins.open", mock_open()):
            self.cm.disconnect(self.pa)
        self.assertEqual(len(self.cm.connections), 0)
        self.assertIsNone(self.pa.connected_to)

    def test_disconnect_specific_port(self):
        with patch("builtins.open", mock_open()):
            self.cm.disconnect(self.pa, port_name="gpio_socket")
        self.assertEqual(len(self.cm.connections), 0)

    def test_disconnect_wrong_port_keeps_connection(self):
        with patch("builtins.open", mock_open()):
            self.cm.disconnect(self.pa, port_name="usb_plug")
        self.assertEqual(len(self.cm.connections), 1)
        self.assertIs(self.pa.connected_to, self.pi)

    def test_disconnect_all_removes_everything(self):
        # Also connect speaker
        self.spk.plug_x = self.pi.usb2_x + 1
        self.spk.plug_y = self.pi.usb2_y + 1
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.spk, self.app.components, zoom=1.0)
        self.assertEqual(len(self.cm.connections), 2)

        with patch("builtins.open", mock_open()):
            self.cm.disconnect_all(self.pi)  # target for both
        self.assertEqual(len(self.cm.connections), 0)


# ═══════════════════════════════════════════════════════════════════════════
#  6.  hardware.log logging via ConnectionManager
# ═══════════════════════════════════════════════════════════════════════════

class TestHardwareLogging(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def _connect_pa(self):
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z
        self.pa.y = self.pi.gpio_y - self.pa.h * z
        self.pa.update_ports()

    def test_connect_logs_to_hardware_log(self):
        self._connect_pa()
        with patch("builtins.open", mock_open()) as m:
            self.cm.try_connect(self.pa, self.app.components, zoom=1.0)
        m.assert_called_with(os.path.join("logs", "hardware.log"), "a")
        m().write.assert_called_with("Pirate Audio is connected to GPIO Header\n")

    def test_disconnect_logs_to_hardware_log(self):
        self._connect_pa()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=1.0)
        with patch("builtins.open", mock_open()) as m:
            self.cm.disconnect(self.pa)
        m.assert_called_with(os.path.join("logs", "hardware.log"), "a")
        m().write.assert_called_with("Pirate Audio is disconnected from GPIO Header\n")

    def test_speaker_connect_log(self):
        self.spk.plug_x = self.pi.usb2_x + 1
        self.spk.plug_y = self.pi.usb2_y + 1
        with patch("builtins.open", mock_open()) as m:
            self.cm.try_connect(self.spk, self.app.components, zoom=1.0)
        m().write.assert_called_with("Mini USB 2.0 external speaker is connected to USB 2.0 Port\n")

    def test_speaker_disconnect_log(self):
        self.spk.plug_x = self.pi.usb2_x + 1
        self.spk.plug_y = self.pi.usb2_y + 1
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.spk, self.app.components, zoom=1.0)
        with patch("builtins.open", mock_open()) as m:
            self.cm.disconnect(self.spk)
        m().write.assert_called_with("Mini USB 2.0 external speaker is disconnected from USB 2.0 Port\n")


# ═══════════════════════════════════════════════════════════════════════════
#  7.  Component drag integration (on_drag_motion / on_drag_stop)
# ═══════════════════════════════════════════════════════════════════════════

class TestPirateAudioDragIntegration(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def _connect_pa(self):
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z
        self.pa.y = self.pi.gpio_y - self.pa.h * z
        self.pa.update_ports()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=z)

    def test_on_drag_stop_creates_connection(self):
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z + 5
        self.pa.y = self.pi.gpio_y - self.pa.h * z + 5
        self.pa.update_ports()

        ev = MagicMock()
        with patch("builtins.open", mock_open()):
            self.pa.on_drag_stop(ev)

        self.assertIs(self.pa.connected_to, self.pi)
        self.assertEqual(len(self.cm.connections), 1)
        self.assertTrue(self.cm.connections[0].is_aligned)

    def test_on_drag_motion_disconnects(self):
        self._connect_pa()

        ev = MagicMock()
        ev.x = self.pa.x + 500
        ev.y = self.pa.y + 500
        self.pa.drag_x = self.pa.x
        self.pa.drag_y = self.pa.y

        with patch("builtins.open", mock_open()):
            self.pa.on_drag_motion(ev)

        self.assertIsNone(self.pa.connected_to)
        self.assertEqual(len(self.cm.connections), 0)


class TestUSBSpeakerDragIntegration(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def _setup_plug_drag_detection(self):
        """Make canvas.find_withtag / gettags return the plug tag."""
        self.spk.canvas.find_withtag = lambda t: (999,) if t == "current" else ()
        self.spk.canvas.gettags = lambda item_id: (self.spk.plug_tag,)

    def test_on_drag_stop_plug_creates_connection(self):
        self._setup_plug_drag_detection()
        self.spk.plug_x = self.pi.usb2_x + 5
        self.spk.plug_y = self.pi.usb2_y + 5

        ev = MagicMock()
        with patch("builtins.open", mock_open()):
            self.spk.on_drag_stop(ev)

        self.assertIs(self.spk.connected_to, self.pi)
        conn = self.cm.connections[0]
        self.assertTrue(conn.is_aligned,
                        f"Plug {conn.get_source_pos()} != USB2 {conn.get_target_pos()}")

    def test_on_drag_motion_plug_disconnects(self):
        self._setup_plug_drag_detection()
        self.spk.plug_x = self.pi.usb2_x
        self.spk.plug_y = self.pi.usb2_y
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.spk, self.app.components, zoom=1.0)

        ev = MagicMock()
        ev.x = self.spk.plug_x + 300
        ev.y = self.spk.plug_y + 300
        with patch("builtins.open", mock_open()):
            self.spk.on_drag_motion(ev)

        self.assertIsNone(self.spk.connected_to)
        self.assertEqual(len(self.cm.connections), 0)

    def test_body_drag_moves_plug_when_disconnected(self):
        self.spk.connected_to = None
        old_plug_x = self.spk.plug_x
        old_plug_y = self.spk.plug_y

        # gettags returns body tag (not plug)
        self.spk.canvas.find_withtag = lambda t: (1,) if t == "current" else ()
        self.spk.canvas.gettags = lambda item_id: (self.spk.tag,)

        ev = MagicMock()
        ev.x = self.spk.x + 50
        ev.y = self.spk.y + 30
        self.spk.drag_x = self.spk.x
        self.spk.drag_y = self.spk.y

        self.spk.on_drag_motion(ev)

        self.assertEqual(self.spk.plug_x, old_plug_x + 50)
        self.assertEqual(self.spk.plug_y, old_plug_y + 30)


# ═══════════════════════════════════════════════════════════════════════════
#  8.  Delete disconnects through ConnectionManager
# ═══════════════════════════════════════════════════════════════════════════

class TestDeleteDisconnects(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def test_delete_pa_removes_connection_and_logs(self):
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z
        self.pa.y = self.pi.gpio_y - self.pa.h * z
        self.pa.update_ports()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=z)

        with patch("builtins.open", mock_open()) as m:
            self.pa.delete()
        self.assertEqual(len(self.cm.connections), 0)
        m().write.assert_called_with("Pirate Audio is disconnected from GPIO Header\n")

    def test_delete_disconnected_pa_no_log(self):
        with patch("builtins.open", mock_open()) as m:
            self.pa.delete()
        m.assert_not_called()

    def test_delete_spk_removes_connection_and_logs(self):
        self.spk.plug_x = self.pi.usb2_x
        self.spk.plug_y = self.pi.usb2_y
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.spk, self.app.components, zoom=1.0)

        with patch("builtins.open", mock_open()) as m:
            self.spk.delete()
        self.assertEqual(len(self.cm.connections), 0)
        m().write.assert_called_with("Mini USB 2.0 external speaker is disconnected from USB 2.0 Port\n")


# ═══════════════════════════════════════════════════════════════════════════
#  9.  reconnect_by_position (state reload)
# ═══════════════════════════════════════════════════════════════════════════

class TestReconnectByPosition(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def test_reconnects_when_ports_at_same_pos(self):
        # Snap PA to GPIO so ports are exactly aligned
        self.pa.snap_port_to("gpio_socket", self.pi.gpio_x, self.pi.gpio_y)
        self.cm.reconnect_by_position(self.app.components, threshold=1.0)
        self.assertEqual(len(self.cm.connections), 1)
        self.assertIs(self.pa.connected_to, self.pi)

    def test_does_not_reconnect_when_far(self):
        self.cm.reconnect_by_position(self.app.components, threshold=1.0)
        self.assertEqual(len(self.cm.connections), 0)
        self.assertIsNone(self.pa.connected_to)

    def test_reconnects_speaker_too(self):
        self.spk.snap_port_to("usb_plug", self.pi.usb2_x, self.pi.usb2_y)
        self.cm.reconnect_by_position(self.app.components, threshold=1.0)
        conn = self.cm.find_connection(self.spk)
        self.assertIsNotNone(conn)
        self.assertIs(conn.target, self.pi)

    def test_clear_all_then_reconnect(self):
        self.pa.snap_port_to("gpio_socket", self.pi.gpio_x, self.pi.gpio_y)
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=1.0)
        self.assertEqual(len(self.cm.connections), 1)

        self.cm.clear_all()
        self.assertEqual(len(self.cm.connections), 0)
        self.assertIsNone(self.pa.connected_to)

        self.cm.reconnect_by_position(self.app.components, threshold=1.0)
        self.assertEqual(len(self.cm.connections), 1)
        self.assertIs(self.pa.connected_to, self.pi)


# ═══════════════════════════════════════════════════════════════════════════
#  10.  HardwareAPI compat
# ═══════════════════════════════════════════════════════════════════════════

class TestHardwareAPICompat(unittest.TestCase):
    """HardwareAPI still finds active components via connected_to (set by CM)."""

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager
        self.api = HardwareAPI(self.app)

    def test_find_pa_after_cm_connect(self):
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z
        self.pa.y = self.pi.gpio_y - self.pa.h * z
        self.pa.update_ports()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=z)
        self.assertEqual(self.api._find_active_pirate_audio(), self.pa)

    def test_find_pa_none_after_cm_disconnect(self):
        z = self.app.zoom_factor
        self.pa.x = self.pi.gpio_x - 145 * z
        self.pa.y = self.pi.gpio_y - self.pa.h * z
        self.pa.update_ports()
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=z)
            self.cm.disconnect(self.pa)
        self.assertIsNone(self.api._find_active_pirate_audio())

    def test_find_spk_after_cm_connect(self):
        self.spk.plug_x = self.pi.usb2_x
        self.spk.plug_y = self.pi.usb2_y
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.spk, self.app.components, zoom=1.0)
        self.assertEqual(self.api._find_active_speaker(), self.spk)


# ═══════════════════════════════════════════════════════════════════════════
#  11.  Threshold edge-cases
# ═══════════════════════════════════════════════════════════════════════════

class TestThresholdEdgeCases(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager

    def test_just_inside_threshold_connects(self):
        z = self.app.zoom_factor
        threshold = 40 * z
        offset = threshold - 1
        gx, gy = 145, self.pa.h
        self.pa.x = self.pi.gpio_x + offset - gx * z
        self.pa.y = self.pi.gpio_y - gy * z
        self.pa.update_ports()

        with patch("builtins.open", mock_open()):
            conn = self.cm.try_connect(self.pa, self.app.components, zoom=z)
        self.assertIsNotNone(conn)

    def test_just_outside_threshold_does_not_connect(self):
        z = self.app.zoom_factor
        threshold = 40 * z
        offset = threshold + 1
        gx, gy = 145, self.pa.h
        self.pa.x = self.pi.gpio_x + offset - gx * z
        self.pa.y = self.pi.gpio_y - gy * z
        self.pa.update_ports()

        conn = self.cm.try_connect(self.pa, self.app.components, zoom=z)
        self.assertIsNone(conn)


# ═══════════════════════════════════════════════════════════════════════════
#  12.  ConnectionManager query helpers
# ═══════════════════════════════════════════════════════════════════════════

class TestManagerQueries(unittest.TestCase):

    def setUp(self):
        self.app, self.pi, self.pa, self.spk = _make_components()
        self.cm = self.app.connection_manager
        self.pa.snap_port_to("gpio_socket", self.pi.gpio_x, self.pi.gpio_y)
        with patch("builtins.open", mock_open()):
            self.cm.try_connect(self.pa, self.app.components, zoom=1.0)

    def test_find_connection(self):
        conn = self.cm.find_connection(self.pa)
        self.assertIsNotNone(conn)
        self.assertIs(conn.source, self.pa)

    def test_find_connection_by_port(self):
        conn = self.cm.find_connection(self.pa, "gpio_socket")
        self.assertIsNotNone(conn)

    def test_find_connection_wrong_port_returns_none(self):
        conn = self.cm.find_connection(self.pa, "usb_plug")
        self.assertIsNone(conn)

    def test_find_connections_for(self):
        conns = self.cm.find_connections_for(self.pi)
        self.assertEqual(len(conns), 1)
        self.assertIs(conns[0].target, self.pi)

    def test_get_connected_target(self):
        self.assertIs(self.cm.get_connected_target(self.pa), self.pi)

    def test_get_connected_target_none(self):
        self.assertIsNone(self.cm.get_connected_target(self.spk))

    def test_is_connected(self):
        self.assertTrue(self.cm.is_connected(self.pa))
        self.assertFalse(self.cm.is_connected(self.spk))


# ═══════════════════════════════════════════════════════════════════════════
#  13.  Port positions update after drag
# ═══════════════════════════════════════════════════════════════════════════

class TestPortPositionTracking(unittest.TestCase):

    def setUp(self):
        self.app = MockApp()
        self.canvas = self.app.canvas

    def test_rpi_ports_update_after_drag(self):
        pi = RaspberryPi(self.canvas, 100, 100)
        old_gpio = (pi.gpio_x, pi.gpio_y)
        pi.drag_x, pi.drag_y = 100, 100
        ev = MagicMock()
        ev.x, ev.y = 200, 250
        pi.on_drag_motion(ev)
        self.assertAlmostEqual(pi.gpio_x, old_gpio[0] + 100)
        self.assertAlmostEqual(pi.gpio_y, old_gpio[1] + 150)

    def test_pa_ports_update_after_drag(self):
        pa = PirateAudio(self.canvas, 50, 50)
        old_sock = (pa.socket_x, pa.socket_y)
        pa.drag_x, pa.drag_y = 50, 50
        ev = MagicMock()
        ev.x, ev.y = 100, 100
        with patch("builtins.open", mock_open()):
            pa.on_drag_motion(ev)
        self.assertAlmostEqual(pa.socket_x, old_sock[0] + 50)
        self.assertAlmostEqual(pa.socket_y, old_sock[1] + 50)


if __name__ == '__main__':
    unittest.main()
