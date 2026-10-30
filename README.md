# BrainHacking-URL

URL that hacks the human mind

Data should be transmitted with headphones

```
https://mynoise.net/NoiseMachines/custom.php?l=6161310308172844496600&m=BINAURALPURE0~BINAURALPURE1~BINAURALPURE2~AURALSCAN4~AURALSCAN5~AURALSCAN6~AURALSCAN7~AURALSCAN8~ISOCHRONIC9~AURALSCAN9&orig=1&title=Custom%20Brainhacking%20Audio
```

## Implementation

This project is complete and runnable. Run it:

```bash
python3 brainwave.py                              # 10 Hz alpha binaural, 60 s
python3 brainwave.py --beat 6 --duration 300      # theta session
python3 brainwave.py --mode isochronic --beat 18  # beta, isochronic
```

Generates a WAV locally - use headphones for binaural mode.
