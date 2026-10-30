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

SAMPLE_RATE = 44100


def frames(mode, base, beat, seconds, volume):
    total = int(SAMPLE_RATE * seconds)
    # 2 s fade in/out avoids clicks, capped at half the file so short
    # files still reach full volume in the middle instead of peaking
    # at a fraction of the requested volume.
    fade = min(int(SAMPLE_RATE * 2), total // 2)
    for n in range(total):
        t = n / SAMPLE_RATE
        env = min(1.0, n / fade, (total - n) / fade) if fade > 0 else 1.0
        if mode == "binaural":
            left = math.sin(2 * math.pi * (base - beat / 2) * t)
            right = math.sin(2 * math.pi * (base + beat / 2) * t)
        else:  # isochronic: one tone, gated at the beat rate
            gate = 1.0 if (t * beat) % 1.0 < 0.5 else 0.0
            left = right = math.sin(2 * math.pi * base * t) * gate
        yield (int(32767 * volume * env * left),
               int(32767 * volume * env * right))


def write_wav(path, mode, base, beat, seconds, volume):
    with wave.open(path, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        chunk = bytearray()
        for left, right in frames(mode, base, beat, seconds, volume):
            chunk += struct.pack("<hh", left, right)
            if len(chunk) >= 1 << 20:
                wav.writeframes(bytes(chunk))
                chunk.clear()
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
