import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import unittest
from unittest.mock import MagicMock
from hardware_api import HardwareAPI
from components.raspberry_pi import RaspberryPi
from components.pirate_audio import PirateAudio
from components.usb_speaker import USBSpeaker

class TestHardwareAPI(unittest.TestCase):
    def setUp(self):
        self.mock_app = MagicMock()
        self.mock_app.components = []
        self.api = HardwareAPI(self.mock_app)

    def test_find_active_pirate_audio_none(self):
        pa = PirateAudio(MagicMock(), 0, 0)
        pa.connected_to = None
        self.mock_app.components.append(pa)
        self.assertIsNone(self.api._find_active_pirate_audio())

    def test_find_active_pirate_audio_connected(self):
        pi = RaspberryPi(MagicMock(), 0, 0)
        pa = PirateAudio(MagicMock(), 0, 0)
        pa.connected_to = pi
        self.mock_app.components.extend([pi, pa])
        self.assertEqual(self.api._find_active_pirate_audio(), pa)

    def test_find_active_speaker_none(self):
        speaker = USBSpeaker(MagicMock(), 0, 0)
        speaker.connected_to = None
        self.mock_app.components.append(speaker)
        self.assertIsNone(self.api._find_active_speaker())

    def test_find_active_speaker_connected(self):
        pi = RaspberryPi(MagicMock(), 0, 0)
        speaker = USBSpeaker(MagicMock(), 0, 0)
        speaker.connected_to = pi
        self.mock_app.components.extend([pi, speaker])
        self.assertEqual(self.api._find_active_speaker(), speaker)

    def test_play_audio_no_speaker(self):
        self.assertFalse(self.api.play_audio('test.wav'))

if __name__ == '__main__':
    unittest.main()
