#!/usr/bin/env python3
"""BrainHacking - generate brainwave-entrainment audio locally.

The original BrainHacking-URL linked out to a hosted noise machine. This
tool generates the same class of audio on your own machine instead:
binaural beats (a slightly different pure tone in each ear - the brain
perceives the difference as a beat) and isochronic tones (a single tone
pulsed on/off at the beat rate). Output is a standard WAV file.

Use headphones for binaural beats - the effect depends on each ear
receiving a different tone.

Usage:
    python3 brainwave.py                          # 10 Hz alpha, 60 s binaural
    python3 brainwave.py --beat 6 --base 200      # 6 Hz theta over 200 Hz
    python3 brainwave.py --mode isochronic --duration 300 -o theta.wav

Beat guide: delta 0.5-4 Hz (sleep), theta 4-8 (meditation), alpha 8-13
(relaxed focus), beta 13-30 (alertness), gamma 30+ (concentration).
"""
import argparse
import math
import struct
import sys
import wave

# I fix the rate at 44100 for every file. No option can change it, so
# the frame math below can treat the rate as a constant, and any code
# reading these files back can assume the same rate.
SAMPLE_RATE = 44100


def frames(mode, base, beat, seconds, volume):
    # I hand this function values that main has already checked. It does
    # no checking of its own, so calling it directly with a negative or
    # non-finite number is on the caller.
    # int() truncates, so a duration that lands between frames loses
    # the fraction. A duration under one frame (about 0.00002 s) gives
    # total 0 and the file comes out as a valid header with no audio.
    total = int(SAMPLE_RATE * seconds)
    # 2 s fade in/out avoids clicks, capped at half the file so short
    # files still reach full volume in the middle instead of peaking
    # at a fraction of the requested volume.
    fade = min(int(SAMPLE_RATE * 2), total // 2)
    for n in range(total):
        t = n / SAMPLE_RATE
        # The envelope is the smallest of the fade-in ramp, the fade-out
        # ramp, and 1.0, so the middle of a long file sits at full level
        # and both ends taper. When fade is 0 (a one frame file) I skip
        # the division and use 1.0 rather than divide by zero.
        env = min(1.0, n / fade, (total - n) / fade) if fade > 0 else 1.0
        if mode == "binaural":
            # I split the beat around the carrier, half below in the
            # left ear and half above in the right, so the two tones
            # differ by exactly the beat frequency. Nothing stops a
            # caller from passing a beat wider than twice the base,
            # which pushes the left frequency below zero; the sine
            # still renders, as a tone at the mirrored frequency.
            left = math.sin(2 * math.pi * (base - beat / 2) * t)
            right = math.sin(2 * math.pi * (base + beat / 2) * t)
        else:  # isochronic: one tone, gated at the beat rate
            # The gate is open for the first half of each beat cycle
            # and shut for the second half. At beat 0 the modulo is
            # always 0, so the gate never shuts and the output is a
            # plain steady tone. Both channels get the same samples,
            # which is what makes this mode work on speakers too.
            gate = 1.0 if (t * beat) % 1.0 < 0.5 else 0.0
            left = right = math.sin(2 * math.pi * base * t) * gate
        # The pack in write_wav cannot overflow: volume is at most 1,
        # env is at most 1, and a sine is at most 1, so each product
        # stays inside the 16 bit range. int() truncates toward zero,
        # which costs under one step of level and keeps the sign.
        yield (int(32767 * volume * env * left),
               int(32767 * volume * env * right))


def write_wav(path, mode, base, beat, seconds, volume):
    # The header is written when the file opens, before a single frame
    # exists. That order is why main validates first: a failure raised
    # partway through the loop below would leave a header with missing
    # or partial audio at this path, and nothing here cleans it up.
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        # frames() yields one pair at a time, so I buffer pairs and
        # flush at 1 MiB (262144 stereo frames, about 6 seconds of
        # audio). A long session then holds one chunk in memory
        # instead of the whole file, and the disk gets large writes
        # instead of millions of small ones.
        chunk = bytearray()
        for left, right in frames(mode, base, beat, seconds, volume):
            chunk += struct.pack("<hh", left, right)
            if len(chunk) >= 1 << 20:
                wav.writeframes(bytes(chunk))
                chunk.clear()
        # The tail after the last full chunk still has to be written,
        # or every file would end early by up to one chunk.
        if chunk:
            wav.writeframes(bytes(chunk))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate binaural/isochronic brainwave audio (WAV).")
    parser.add_argument("--mode", choices=["binaural", "isochronic"], default="binaural")
    parser.add_argument("--base", type=float, default=220.0, help="carrier tone in Hz (default 220)")
    parser.add_argument("--beat", type=float, default=10.0, help="beat frequency in Hz (default 10, alpha)")
    parser.add_argument("--duration", type=float, default=60.0, help="seconds (default 60)")
    parser.add_argument("--volume", type=float, default=0.5, help="0.0-1.0 (default 0.5)")
    parser.add_argument("-o", "--output", default="brainwave.wav")
    args = parser.parse_args(argv)
    # argparse settles the mode on its own (a bad choice exits 2 before
    # this code runs). The numbers are mine to check, and I check them
    # all here, before write_wav opens any file. An earlier version let
    # bad values through and the failure landed mid-write, leaving a
    # 44 byte header with zero frames behind.
    # The isfinite check does real work in this condition: every
    # comparison against nan is false, so the range checks alone would
    # wave nan through, and inf would pass the beat and base checks.
    # Beat 0 stays allowed on purpose; it means a plain tone, in both
    # modes, and the README says so.
    # One limit I accept: I never check the carrier against half the
    # sample rate. A base above 22050 Hz still writes a file, but the
    # samples cannot hold that tone and what plays back folds down to
    # a lower frequency.
    values = (args.base, args.beat, args.duration, args.volume)
    if (not all(math.isfinite(v) for v in values)
            or args.base <= 0 or args.beat < 0
            or args.duration <= 0 or not 0 < args.volume <= 1):
        print("error: base must be > 0, beat must be >= 0, duration must be > 0, "
              "volume must be in (0, 1], and all values must be finite numbers",
              file=sys.stderr)
        return 1
    write_wav(args.output, args.mode, args.base, args.beat, args.duration, args.volume)
    print(f"Wrote {args.output}: {args.mode}, base {args.base:g} Hz, "
          f"beat {args.beat:g} Hz, {args.duration:g} s. Use headphones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
