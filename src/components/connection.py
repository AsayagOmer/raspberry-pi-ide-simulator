"""Connection entity and manager for hardware component connections.

A Connection represents a physical link between two component ports.
The ConnectionManager is the single authority for creating, tracking,
and destroying connections — ensuring that ports are at the exact same
position when a connection is established.
"""
import math
import os


class Connection:
    """A physical connection between two component ports.

    Stores the source (out-port) and target (in-port) components along with
    their port names.  Port positions are looked up dynamically so the
    ``is_aligned`` property always reflects the current canvas state.
    """

    def __init__(self, source, source_port, target, target_port):
        self.source = source            # component owning the out-port
        self.source_port = source_port  # port name, e.g. "gpio_socket"
        self.target = target            # component owning the in-port
        self.target_port = target_port  # port name, e.g. "gpio_header"

    def __repr__(self):
        src = self.source.__class__.__name__
        tgt = self.target.__class__.__name__
        return f"Connection({src}.{self.source_port} -> {tgt}.{self.target_port})"

    # -- helpers to look up live positions --

    def get_source_pos(self):
        """Return (x, y) of the source port, or None."""
        for p in self.source.get_ports():
            if p["name"] == self.source_port:
                return (p["x"], p["y"])
        return None

    def get_target_pos(self):
        """Return (x, y) of the target port, or None."""
        for p in self.target.get_ports():
            if p["name"] == self.target_port:
                return (p["x"], p["y"])
        return None

    @property
    def is_aligned(self):
        """True when source and target ports occupy the same position."""
        sp = self.get_source_pos()
        tp = self.get_target_pos()
        if sp is None or tp is None:
            return False
        return math.hypot(sp[0] - tp[0], sp[1] - tp[1]) < 1.0


class ConnectionManager:
    """Central authority for creating / destroying hardware connections.

    Components call *try_connect* after a drag-stop and *disconnect* when
    they are dragged away (or deleted).  The manager:

    1. Checks port compatibility.
    2. Snaps the source port to the **exact** position of the target port.
    3. Creates a ``Connection`` entity.
    4. Maintains ``component.connected_to`` for backward-compat with
       ``HardwareAPI``.
    5. Writes connect / disconnect events to ``hardware.log``.
    """

    # out-port name -> compatible in-port name
    PORT_COMPATIBILITY = {
        "gpio_socket": "gpio_header",
        "usb_plug":    "usb2_port",
    }

    # (source_port, target_port) -> (connect_msg, disconnect_msg)
    LOG_MESSAGES = {
        ("gpio_socket", "gpio_header"): (
            "Pirate Audio is connected to GPIO Header",
            "Pirate Audio is disconnected from GPIO Header",
        ),
        ("usb_plug", "usb2_port"): (
            "Mini USB 2.0 external speaker is connected to USB 2.0 Port",
            "Mini USB 2.0 external speaker is disconnected from USB 2.0 Port",
        ),
    }

    def __init__(self):
        self.connections: list[Connection] = []

    # ---- public API --------------------------------------------------

    def try_connect(self, source, all_components, snap_threshold=40, zoom=1.0):
        """Attempt to connect *source*'s out-ports to a nearby in-port.

        Iterates over every out-port on *source*, finds the closest
        compatible in-port among *all_components* that is within
        ``snap_threshold * zoom`` pixels, snaps the port to the exact
        target position, and records a ``Connection``.

        Returns the new (or existing) ``Connection``, or ``None``.
        """
        source_ports = [p for p in source.get_ports() if p["direction"] == "out"]

        for s_port in source_ports:
            compat = self.PORT_COMPATIBILITY.get(s_port["name"])
            if compat is None:
                continue

            for target in all_components:
                if target is source:
                    continue
                for t_port in target.get_ports():
                    if t_port["direction"] != "in" or t_port["name"] != compat:
                        continue

                    dist = math.hypot(s_port["x"] - t_port["x"],
                                      s_port["y"] - t_port["y"])
                    if dist >= snap_threshold * zoom:
                        continue

                    # ---- snap to exact position ----
                    source.snap_port_to(s_port["name"], t_port["x"], t_port["y"])

                    # already connected to this exact target+port?
                    existing = self.find_connection(source, s_port["name"])
                    if (existing
                            and existing.target is target
                            and existing.target_port == t_port["name"]):
                        return existing

                    # replace any prior connection on this port
                    if existing:
                        self._remove_connection(existing)

                    conn = Connection(source, s_port["name"],
                                      target, t_port["name"])
                    self.connections.append(conn)
                    source.connected_to = target

                    self._log_connect(s_port["name"], t_port["name"])
                    
                    try:
                        import winsound
                        winsound.PlaySound("C:/Windows/Media/Windows Navigation Start.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
                    except Exception:
                        pass
                        
                    return conn

        return None

    def disconnect(self, source, port_name=None):
        """Remove connections where *source* is the source component.

        If *port_name* is given, only that specific port is disconnected.
        """
        to_remove = [
            c for c in self.connections
            if c.source is source
            and (port_name is None or c.source_port == port_name)
        ]
        for conn in to_remove:
            self._remove_connection(conn)

    def disconnect_all(self, component):
        """Remove every connection that involves *component* (source **or** target)."""
        to_remove = [
            c for c in self.connections
            if c.source is component or c.target is component
        ]
        for conn in to_remove:
            self._remove_connection(conn)

    def find_connection(self, component, port_name=None):
        """Return the ``Connection`` where *component* is the source (first match)."""
        for conn in self.connections:
            if conn.source is component and (port_name is None or conn.source_port == port_name):
                return conn
        return None

    def find_connections_for(self, component):
        """Return all connections involving *component*."""
        return [c for c in self.connections
                if c.source is component or c.target is component]

    def get_connected_target(self, component):
        """Convenience: return the target of the first source-connection, or ``None``."""
        conn = self.find_connection(component)
        return conn.target if conn else None

    def is_connected(self, component):
        return self.find_connection(component) is not None

    def clear_all(self):
        """Drop every connection **without** logging (used before state reload)."""
        for conn in self.connections:
            conn.source.connected_to = None
        self.connections.clear()

    def reconnect_by_position(self, all_components, threshold=1.0):
        """Silently recreate connections whose ports are already aligned.

        Called after loading / restoring hardware state — the components
        have been placed at their saved positions so ports that were
        previously snapped together should be at (nearly) the same spot.
        No hardware.log entries are written.
        """
        for source in all_components:
            for s_port in source.get_ports():
                if s_port["direction"] != "out":
                    continue
                compat = self.PORT_COMPATIBILITY.get(s_port["name"])
                if compat is None:
                    continue
                for target in all_components:
                    if target is source:
                        continue
                    for t_port in target.get_ports():
                        if t_port["direction"] != "in" or t_port["name"] != compat:
                            continue
                        dist = math.hypot(s_port["x"] - t_port["x"],
                                          s_port["y"] - t_port["y"])
                        if dist < threshold:
                            conn = Connection(source, s_port["name"],
                                              target, t_port["name"])
                            self.connections.append(conn)
                            source.connected_to = target

    # ---- internal helpers --------------------------------------------

    def _remove_connection(self, conn):
        if conn in self.connections:
            self.connections.remove(conn)
            conn.source.connected_to = None
            self._log_disconnect(conn.source_port, conn.target_port)

    def _log_connect(self, source_port, target_port):
        key = (source_port, target_port)
        if key in self.LOG_MESSAGES:
            with open(os.path.join("logs", "hardware.log"), "a") as f:
                f.write(self.LOG_MESSAGES[key][0] + "\n")

    def _log_disconnect(self, source_port, target_port):
        key = (source_port, target_port)
        if key in self.LOG_MESSAGES:
            with open(os.path.join("logs", "hardware.log"), "a") as f:
                f.write(self.LOG_MESSAGES[key][1] + "\n")
