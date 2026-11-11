---
name: ai-clip-music-video
description: Turn short AI-generated video clips (Kling, Runway, Veo, Sora, Pika, Higgsfield...) plus a song and its lyrics into full-length, premium lyric music videos for YouTube (16:9) and Reels/TikTok/Shorts (9:16) - seamless looping, a virtual camera that reframes per song section, beat-synced bloom/flash/shake/chromatic hits, animated lyric typography with line-relevant light motifs, title cards, and frame-accurate lyric sync. Use this whenever the user has a few-second AI clip or still and a track and wants a lyric video, visualizer, music video, "make the lyrics dynamic / premium", "animate it to the beat", "crop it per section", or wants to redo/extend such a video for another song or artist - even if they only say "make a video for this song with this clip".
---

# AI clip -> full music video

A 5-10 s AI clip has to carry a 3-minute song. What makes it feel like a real video instead of a loop with
subtitles: the camera keeps changing what you look at, the picture reacts to the drums, the words arrive in
time with the voice and carry the meaning of the line, and the song's structure (intro, verse, chorus, drop,
outro) is visible in the edit. Everything below serves those four things.

The working reference implementation is `references/kling_fx_reference.py` (DESIRE by EPALLE, two Kling clips).
Copy it into the new project's output folder and adapt it; don't rewrite it from scratch. It reads word timings
from that project's `desire_suite.py` - replace those hooks (`ds.lines()`, `ds.events()`, `ds.CHORUS`,
`ds.climax_start()`, `ds.plane_cutout()`, `ds.sky_layer`) with the new song's data.

## 0. Creative brief first (5 minutes, saves hours of re-renders)

Before touching code, write a short brief with the user (ask only what you can't infer):
- **Song map**: intro, verses, choruses, bridge/drop, outro with timestamps. Get them from the lyrics' line
  groups and the audio energy (`smooth` from step 2); confirm the chorus and the drop by ear-time.
- **Mood -> type**: pick one display face + one text face that match the picture (DESIRE: Cinzel Decorative
  Bold for titles/chants, Cormorant Garamond Bold Italic for verses). Google Fonts, OFL, saved in `fonts/`.
  Check every letter of the artist's name in the display face - ornamental caps can misread (Cinzel's L read as I).
- **Motif map**: keyword -> light effect behind the line (fire/burning -> embers, money -> gold glints,
  fly/plane -> streaks, gods/inside -> rotating rays, love -> pink motes, chant lines -> shock rings). Lines
  that are the song's hook get the biggest treatment.
- **Title**: artist + song card at intro, returning at the outro. No "Official Lyric Video", no "Out now",
  no copyright line unless the user asks.
- **Formats**: which of 16:9 and 9:16, and where text lives in each (open sky beside the subject in 16:9;
  centred band in 9:16). Text never sits on the subject's face.

## 1. Prepare the clip: seamless loop at native size

AI clips usually have a camera push-in, so a crossfade loop ghosts. Use ping-pong (forward + reversed, drop the
duplicated end frames), keep native resolution - the virtual camera does the only resample:
```bash
ffmpeg -i clip.mp4 -an -filter_complex "[0:v]split[a][b];[b]reverse,trim=start_frame=1,setpts=PTS-STARTPTS[r];[a][r]concat=n=2:v=1,trim=end_frame=<2n-2>" -c:v libx264 -crf 12 pp.mp4
```
Drop the clip's own audio. Decode with `-stream_loop -1 -ss <t mod loop_len>`.

## 2. Analyse the audio and the words

- `scripts/audio_features.py song.wav audio.npz 24` -> per-frame energy, smooth, kick, high, onset, beats.
- Lyric timing: forced alignment (the lyrics-video-engine sidecar) is usually close but drifts on repeated
  hooks and ad-libs. Check against `scripts/whisper_words.py vocals.wav words.json` on the Demucs vocal stem,
  and re-time the lines that disagree by more than ~0.3 s. Outros with repeated "my desire, my desire" are the
  usual failure. Keep the user's text edits as a separate edited-words file applied onto the timings
  (same word counts, assert it), so re-alignment never loses them.

## 3. Virtual camera (reframing per section)

One shot per section, ~8 s moves inside long sections, each shot a slow move between two framings
(zoom 1.0-1.32 on named spots: wide, face, sun/light source, water/ground, sky). Grammar that reads as edited:
- intro: one slow push-in under the title; outro: pull back to the full frame under the returning title;
- verses: glide between framings (1.4 s ease out of the previous shot's end framing);
- chorus entries, chorus exits and the drop: **hard cut on the nearest beat**, tighter framing, plus a warm
  light leak sweeping across the cut;
- never a shot shorter than ~3 s; clamp the crop inside the frame; in 16:9 frame the subject away from the
  lyric column.
Build it as a matrix from native clip -> output size (`cv2.warpAffine`, `INTER_LANCZOS4`) then a light unsharp,
so zoom costs one resample.

## 4. Beat-synced picture

Per frame, from `audio.npz`: zoom breathes `+1.8% * kick^2` (more in choruses), shake `~7px * onset^3` only in
choruses/drop, bloom of highlights `(0.3 + kick^2 + 0.5*hit)` at quarter res, flash on the hardest onsets in
choruses, chromatic split of `round(3*kick^2*(1+hit))` px. Square the kick - the raw envelope is high on
average and makes everything mush. Lyric-cued set pieces (a jet crossing on "Jamaica", money on "paper") are
timed from the word timings, not by hand.

## 5. Lyric typography

Per word: fly in from below and alternating sides with scale 1.2 -> 1 over 0.3 s, blur -> sharp, glow flash
that settles, a light sweep across the word while it is sung; display/chant words land with a scale punch.
Per line: blurred 30% preview before it is sung, a dark haze plate behind the block (readability on any
background), gentle sway, bounce on the kick for chant lines, scatter + rise + blur on exit, gold hairline
drawing under verse lines. Balance rows (no orphan word), max 3 rows, shrink to fit.

## 6. Composite and encode

Order: camera -> beat bloom/leaks/flash -> set pieces -> lyric layer (premultiplied over) + light layer (screen)
-> title card overlay (alpha clip, ffmpeg overlay) -> encode. Python writes rgb24 to an ffmpeg encoder:
QSV h264 `-global_quality 18` (16:9) / `20` (9:16), fallback libx264; BT.709 tags + `h264_metadata` bsf;
AAC 320k 48 kHz from the master wav; `-map_metadata -1 -fflags +bitexact -movflags +faststart`.

## 7. Check before you say it's done

- `--preview t1,t2,...` stills at: title, first chorus entry (a cut), a set piece, a dense verse, the drop,
  the outro title. Look at them - text over the face, bloom blowing out skin, cropped title are the usual faults.
- `--clip t0 dur` for motion around a hard cut.
- After the full render: ffprobe duration == song length +-0.3 s with audio, and an 8-frame contact sheet.
- Scan for black/NaN frames if anything uses fractional powers (`x ** 1.5` of a slightly negative number is
  NaN -> GaussianBlur spreads it -> black square). Clamp with `max(0.0, ...)` and `np.nan_to_num`.

## Practical notes

- A 3-minute 1080p render is CPU-bound (~2-3 fps on a shared 4-core machine, 30-35 min per format): run the
  formats one after another in the background, never kill other people's python/ffmpeg processes.
- Never overwrite a previous delivered version: rename it (`-v2`, `-prev`) before re-rendering.
- Write Python with the Write tool, not bash heredocs (the rtk hook mangles backslashes).
- Inputs (clips, masters) are read-only; write only to the project's output folder.
