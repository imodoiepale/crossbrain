"""Per-video-frame audio features for beat-synced visuals.

    python audio_features.py <song.(wav|mp3)> <out.npz> [fps=24]

Writes energy, smooth (4 s section energy), kick (decaying low-band attack), high, onset (all 0..1, one value
per video frame), beats (seconds) and tempo. Needs librosa (the lyrics-video-engine embedded python has it:
C:\path\to\lyrics-video-engine\\resources\\python\\python.exe).
"""
import sys

import librosa
import numpy as np

src, out = sys.argv[1], sys.argv[2]
FPS = int(sys.argv[3]) if len(sys.argv) > 3 else 24
y, sr = librosa.load(src, sr=22050, mono=True)
hop = sr // FPS
n_frames = int(np.ceil(len(y) / sr * FPS))


def per_frame(x, times):
    return np.interp(np.arange(n_frames) / FPS, times, x).astype(np.float32)


def norm(x):
    lo, hi = np.percentile(x, 5), np.percentile(x, 99)
    return np.clip((x - lo) / (hi - lo + 1e-9), 0, 1)


S = np.abs(librosa.stft(y, n_fft=2048, hop_length=hop))
freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
t = librosa.frames_to_time(np.arange(S.shape[1]), sr=sr, hop_length=hop)
low = norm(S[(freqs > 30) & (freqs < 150)].sum(0))
high = norm(S[(freqs > 4000) & (freqs < 11000)].sum(0))
rms = norm(librosa.feature.rms(S=S)[0])
onset = norm(librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop))
tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop)
beat_t = librosa.frames_to_time(beats, sr=sr, hop_length=hop)

kick_raw = np.maximum(0, np.diff(low, prepend=low[0]))        # sharp attack of the low band ...
kick = np.zeros_like(kick_raw)
for i in range(len(kick_raw)):                                 # ... with a decaying envelope
    kick[i] = max(kick_raw[i] * 3, (kick[i - 1] * 0.82) if i else 0)
kick = np.clip(kick, 0, 1)

energy = per_frame(rms, t)
smooth = np.convolve(energy, np.ones(FPS * 4) / (FPS * 4), mode="same")
np.savez(out, energy=energy, smooth=smooth.astype(np.float32), kick=per_frame(kick, t), high=per_frame(high, t),
         onset=per_frame(onset, t), beats=beat_t.astype(np.float32), tempo=np.float32(np.atleast_1d(tempo)[0]), fps=FPS)
print("frames", n_frames, "tempo", float(np.atleast_1d(tempo)[0]), "beats", len(beat_t))
assert len(energy) == n_frames and energy.max() <= 1.0     # self-check: one value per frame, normalised
