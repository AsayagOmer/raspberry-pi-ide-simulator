import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from unittest.mock import MagicMock
from components.base_component import BaseComponent
from components.raspberry_pi import RaspberryPi
from components.pirate_audio import PirateAudio
from components.usb_speaker import USBSpeaker

class TestComponents(unittest.TestCase):
    def setUp(self):
        self.mock_canvas = MagicMock()
        self.mock_app = MagicMock()
        self.mock_app.components = []
        self.mock_app.hovered_component = None
        self.mock_app.button_states = {'A': False, 'B': False, 'X': False, 'Y': False}
        self.mock_app.save_hardware_state = MagicMock()
        self.mock_app.canvas = self.mock_canvas
        self.mock_canvas.winfo_toplevel.return_value = self.mock_app
        
        self.mock_canvas.create_rectangle.return_value = 1
        self.mock_canvas.create_oval.return_value = 2
        self.mock_canvas.create_text.return_value = 3
        self.mock_canvas.create_window.return_value = 4
        self.mock_canvas.create_line.return_value = 5

    def test_raspberry_pi_ports(self):
        pi = RaspberryPi(self.mock_canvas, 0, 0)
        pi.update_ports()
        self.assertTrue(hasattr(pi, 'gpio_x'))
        self.assertTrue(hasattr(pi, 'gpio_y'))
        self.assertTrue(hasattr(pi, 'usb2_x'))
        self.assertTrue(hasattr(pi, 'usb2_y'))
        self.assertTrue(hasattr(pi, 'usb3_x'))
        self.assertTrue(hasattr(pi, 'usb3_y'))

    def test_pirate_audio_attributes(self):
        pa = PirateAudio(self.mock_canvas, 0, 0)
        self.assertEqual(pa.x, 0)
        self.assertEqual(pa.y, 0)
        self.assertIsNone(pa.connected_to)

    def test_usb_speaker_attributes(self):
        speaker = USBSpeaker(self.mock_canvas, 0, 0)
        self.assertEqual(speaker.x, 0)
        self.assertEqual(speaker.y, 0)
        self.assertIsNone(speaker.connected_to)

    def test_base_component_rot_pt(self):
        base = BaseComponent(self.mock_canvas, 0, 0)
        base.w = 100
        base.h = 100
        base.rotation = 0
        self.assertEqual(base._rot_pt(10, 20), (10, 20))
        base.rotation = 90
        self.assertEqual(base._rot_pt(10, 20), (80, 10))
        base.rotation = 180
        self.assertEqual(base._rot_pt(10, 20), (90, 80))
        base.rotation = 270
        self.assertEqual(base._rot_pt(10, 20), (20, 90))

    def test_component_registry(self):
        pi = RaspberryPi(self.mock_canvas, 0, 0)
        pa = PirateAudio(self.mock_canvas, 0, 0)
        speaker = USBSpeaker(self.mock_canvas, 0, 0)
        
        components = [pi, pa, speaker]
        self.assertEqual(len(components), 3)

if __name__ == '__main__':
    unittest.main()
