"""Word timestamps from an isolated vocal stem (Demucs) with faster-whisper, to check or re-time lyric sync.

    python whisper_words.py <vocals.wav> <out.json> [model_dir]

Prints segments as it goes; writes [{t, e, w, p}] (start, end, word, probability). 2 CPU threads so it can run
next to a render. Default model dir is the lyrics-video-engine one (has the "base" model offline).
"""
import json
import sys

from faster_whisper import WhisperModel

voc, out = sys.argv[1], sys.argv[2]
mdir = sys.argv[3] if len(sys.argv) > 3 else r"C:\path\to\whisper-models"
m = WhisperModel("base", device="cpu", compute_type="int8", cpu_threads=2, download_root=mdir)
segs, _ = m.transcribe(voc, language="en", word_timestamps=True, vad_filter=False, condition_on_previous_text=False)
words = []
for s in segs:
    print(f"[{s.start:7.2f} - {s.end:7.2f}] {s.text}", flush=True)
    words += [dict(t=round(w.start, 2), e=round(w.end, 2), w=w.word.strip(), p=round(w.probability, 2)) for w in s.words]
json.dump(words, open(out, "w"), indent=0)
print(len(words), "words ->", out)
