"""Tests for brainwave.py.

Two layers: the frames generator read directly, and the command
line run as a subprocess so exit codes, stderr, and the files on
disk are all the real ones. The validation tests pin the three
silent failures the comment campaign logged (a beat wider than
twice the base, a tone above half the sample rate, and a duration
too short to hold one frame) plus the output path failure that
used to end in a traceback.
"""
import math
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path

HERE = Path(__file__).parent
SCRIPT = HERE / "brainwave.py"
sys.path.insert(0, str(HERE))

import brainwave  # noqa: E402


def run_cli(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, timeout=60,
    )


class FramesTests(unittest.TestCase):
    def test_frame_count_matches_duration(self):
        frames = list(brainwave.frames("binaural", 220.0, 10.0, 0.01, 0.5))
        self.assertEqual(len(frames), 441)

    def test_binaural_channels_differ(self):
        frames = list(brainwave.frames("binaural", 220.0, 10.0, 0.05, 0.5))
        self.assertTrue(any(left != right for left, right in frames))

    def test_isochronic_channels_are_identical(self):
        frames = list(brainwave.frames("isochronic", 220.0, 10.0, 0.05, 0.5))
        self.assertTrue(all(left == right for left, right in frames))

    def test_samples_stay_inside_16_bit_range(self):
        frames = list(brainwave.frames("binaural", 220.0, 10.0, 0.05, 1.0))
        self.assertTrue(
            all(-32767 <= s <= 32767 for pair in frames for s in pair)
        )

    def test_first_frame_is_silent_from_the_fade(self):
        frames = list(brainwave.frames("binaural", 220.0, 10.0, 1.0, 0.5))
        self.assertEqual(frames[0], (0, 0))


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "out.wav"

    def tearDown(self):
        self.tmp.cleanup()

    def args(self, *extra):
        return [*extra, "-o", str(self.out)]

    def test_valid_binaural_file_shape(self):
        result = run_cli(*self.args("--duration", "1"))
        self.assertEqual(result.returncode, 0)
        with wave.open(str(self.out)) as wav:
            self.assertEqual(wav.getnchannels(), 2)
            self.assertEqual(wav.getframerate(), 44100)
            self.assertEqual(wav.getnframes(), 44100)

    def test_valid_isochronic_file_shape(self):
        result = run_cli(*self.args("--mode", "isochronic", "--duration", "1"))
        self.assertEqual(result.returncode, 0)
        with wave.open(str(self.out)) as wav:
            self.assertEqual(wav.getnframes(), 44100)

    def test_beat_zero_plain_tone_accepted(self):
        result = run_cli(*self.args("--beat", "0", "--duration", "0.01"))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.out.exists())

    def test_negative_beat_refused(self):
        result = run_cli(*self.args("--beat", "-5", "--duration", "1"))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.out.exists())

    def test_beat_wider_than_twice_base_refused_in_binaural(self):
        result = run_cli(*self.args("--base", "100", "--beat", "300",
                                     "--duration", "1"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("negative frequency", result.stderr)
        self.assertFalse(self.out.exists())

    def test_wide_beat_still_accepted_in_isochronic(self):
        # In isochronic mode the beat only gates the carrier, so a
        # wide beat makes no negative tone and stays legal.
        result = run_cli(*self.args("--mode", "isochronic", "--base", "100",
                                     "--beat", "300", "--duration", "0.01"))
        self.assertEqual(result.returncode, 0)
        self.assertTrue(self.out.exists())

    def test_base_above_half_sample_rate_refused(self):
        for mode in ("binaural", "isochronic"):
            result = run_cli(*self.args("--mode", mode, "--base", "30000",
                                         "--duration", "1"))
            self.assertEqual(result.returncode, 1, mode)
            self.assertIn("half the sample rate", result.stderr)
            self.assertFalse(self.out.exists())

    def test_binaural_right_tone_above_half_sample_rate_refused(self):
        # Base 22000 is under the limit on its own; base plus half
        # the beat is 22100, which is over it.
        result = run_cli(*self.args("--base", "22000", "--beat", "200",
                                     "--duration", "1"))
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.out.exists())

    def test_sub_frame_duration_refused(self):
        result = run_cli(*self.args("--duration", "0.00001"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("shorter than one frame", result.stderr)
        self.assertFalse(self.out.exists())

    def test_short_but_real_duration_accepted(self):
        result = run_cli(*self.args("--duration", "0.001"))
        self.assertEqual(result.returncode, 0)
        with wave.open(str(self.out)) as wav:
            self.assertEqual(wav.getnframes(), 44)

    def test_existing_range_checks_still_refuse(self):
        bad = [
            ("--duration", "0"),
            ("--volume", "0"),
            ("--volume", "1.5"),
            ("--volume", "nan"),
            ("--beat", "inf"),
            ("--base", "0"),
        ]
        for extra in bad:
            result = run_cli(*self.args(*extra, "--duration", "0.01")
                             if "--duration" not in extra else
                             self.args(*extra))
            self.assertEqual(result.returncode, 1, extra)
            self.assertFalse(self.out.exists(), extra)

    def test_unwritable_output_path_is_one_error_line(self):
        missing = Path(self.tmp.name) / "no-such-dir" / "x.wav"
        result = run_cli("--duration", "0.01", "-o", str(missing))
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not write", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_help_exits_0(self):
        result = run_cli("--help")
        self.assertEqual(result.returncode, 0)

    def test_unknown_argument_exits_2(self):
        result = run_cli("--bogus")
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
