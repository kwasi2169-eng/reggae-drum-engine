# Reggae Drum Engine for Groove Agent SE 6 / Cubase 13 Pro

A professional, musically authentic reggae drum pattern generator.
Produces Standard MIDI Files (.mid) and a Cubase Drum Map (.drm) ready to
drag straight into **Groove Agent SE 6** inside **Cubase 13 Pro**.

---

## What It Does

- Generates a **polished 1-bar one-drop loop** and a **full 136-bar song arrangement**
- Outputs a **Cubase Drum Map** (`.drm`) for named lanes in the Drum Editor
- Bakes **CC#4 Hi-Hat Foot Controller** data into the MIDI so Groove Agent SE 6
  hears real hat openness (closed / semi-open / open) on every hit
- Applies authentic reggae micro-timing feel:
  - **Snare layback** (+10 ticks behind beat) -- the roots pocket
  - **Hat push** (-4 ticks ahead of beat) -- locks the groove
  - Gaussian jitter on timing, subtle velocity variance -- human feel without chaos

---

## Groove Design Philosophy

Real reggae drummers are disciplined, not random. This engine enforces:

| Rule | What it means |
|---|---|
| **Fixed repeating patterns** | The groove skeleton is identical every bar within a section. Humanization adds feel -- not new notes. |
| **Cymbals mark sections only** | A crash fires once on bar 1 of any section where energy rises. Never mid-bar, never random. |
| **Rim rolls every 8 bars** | A cross-stick crescendo roll fires on bar 7, 15, 23... globally. Not randomly. |
| **The one-drop is sacred** | Kick + cross-stick on Beat 3 (step 8) is the reggae heartbeat. It does not vary randomly. |
| **Space is music** | The Dub Breakdown section strips everything to kick-on-1, cross-stick-on-3, shaker -- and nothing else. |

---

## Song Structure (136 bars)

| Section | Bars | Energy | Groove Character |
|---|---|---|---|
| Intro | 8 | Low | Shaker only, builds to sparse hat |
| Verse 1 | 16 | Mid | Full one-drop (Carlton Barrett style) |
| Pre-Chorus 1 | 8 | Mid | Ride bell replaces offbeat hat -- lifts energy |
| Chorus 1 | 16 | High | Four-on-floor steppers kick + ride |
| Verse 2 | 16 | Mid | Full one-drop |
| Pre-Chorus 2 | 8 | Mid | Ride bell |
| Chorus 2 | 16 | High | Steppers + ride |
| Dub Breakdown | 8 | Low | Quarter-note hats, kick on 1, maximum space |
| Final Chorus | 16 | High | Steppers + ride, tom fill on last bar |
| Outro | 8 | Low | Strips back to shaker |

---

## Requirements

- **Python 3.8 or higher**
- **mido** library (pure Python, no external dependencies, no APIs)

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/kwasi2169-eng/reggae-drum-engine.git
cd reggae-drum-engine

# 2. (Recommended) Create a virtual environment
python -m venv venv

# On Windows:
venv\Scripts\activate

# On macOS / Linux:
source venv/bin/activate

# 3. Install the only dependency
pip install -r requirements.txt
```

---

## Usage

### Basic run (120 BPM, output to ./output folder)
```bash
python reggae_drum_engine.py
```

### Custom BPM (change inside the script)
Open `reggae_drum_engine.py` and edit the last two lines:
```python
if __name__ == "__main__":
    generate(bpm=74, output_dir="output")   # change 74 to your project BPM
```

Then run:
```bash
python reggae_drum_engine.py
```

### What gets generated
```
output/
  reggae_one_bar_loop.mid       # 1-bar polished loop (for sampling)
  reggae_full_arrangement.mid   # 136-bar full arrangement
  groove_agent_se6.drm          # Cubase 13 Drum Map (named lanes)
```

---

## Using in Cubase 13 Pro with Groove Agent SE 6

### Step 1 -- Load the plugin
1. Create an **Instrument Track**
2. Load **Groove Agent SE 6** as the instrument
3. Inside GA SE 6, pick any **Acoustic Agent** kit
   (e.g. "Vintage Studio Kit", "Studio Standard Kit")

### Step 2 -- Import the Drum Map
1. In Cubase: **MIDI menu > Drum Map Setup > Import**
2. Select `output/groove_agent_se6.drm`
3. In the **Inspector**, set **Drum Map** to `"GA SE6 Roots Reggae"`
4. Open the MIDI in the **Drum Editor** -- every lane is labelled by name

### Step 3 -- Load the MIDI
Drag `reggae_full_arrangement.mid` (or `reggae_one_bar_loop.mid`) directly
onto the GA SE 6 Instrument Track in the project window.

### Step 4 -- Enable Hi-Hat CC#4 (IMPORTANT)
The MIDI file carries **CC#4 (Hi-Hat Foot Controller)** data before every
hat hit, telling GA SE 6 how open the hi-hat should be.

In GA SE 6:
- Click on the **hi-hat pad**
- Go to its **Macro** or **Instrument** page
- Find the **"FC" (Foot Controller) filter button**
- **Make sure it is NOT highlighted / yellow**
- If it is yellow, click it once to deactivate it

If FC is filtered out, all hi-hats will sound identical (fully closed).
With FC active, you get closed, semi-open, and open articulations automatically.

### Step 5 -- Match tempo
Make sure your **Cubase project tempo** matches the `bpm` value in the script.
The default is **120 BPM**.

### Step 6 (Optional) -- Export mixer to Cubase
Right-click the Kit in GA SE 6 > **"Export Mixer to Cubase"**
This creates one MixConsole channel per drum piece for full mix control.

---

## MIDI Technical Reference (for advanced users)

| Parameter | Value |
|---|---|
| MIDI Channel | 10 (mido index 9 -- GM drums) |
| PPQ / Ticks Per Beat | 480 (Cubase 13 default) |
| 1 sixteenth note | 120 ticks |
| CC#4 (Hi-Hat Foot) | 0=closed, 55=semi-open, 110=open |
| CC#7 (Volume) | Fixed in GA SE 6 per slot |
| CC#10 (Pan) | Fixed in GA SE 6 per slot |

**Note:** Do not send CC#64 (Sustain Pedal) to GA SE 6 -- it can reset
the plugin's pattern transport.

### GM Note Map used
| Note | Sound |
|---|---|
| 35 | Kick (soft / ghost touch) |
| 36 | Kick (hard / anchor) |
| 37 | Cross-Stick / Side-Stick |
| 38 | Snare (vel 28-55 = ghost layer, vel 100+ = rimshot layer) |
| 42 | Hi-Hat Closed |
| 44 | Hi-Hat Pedal Chick |
| 46 | Hi-Hat Open |
| 43 | Tom Floor |
| 47 | Tom Lo-Mid |
| 48 | Tom Hi-Mid |
| 50 | Tom High |
| 49 | Crash Cymbal |
| 51 | Ride Body |
| 53 | Ride Bell |
| 54 | Tambourine |
| 69 | Cabasa |
| 70 | Shaker / Maracas |

---

## Privacy & Safety

- **No API keys, tokens, or accounts required**
- **No network access** -- runs entirely offline
- **No data collected** -- nothing is sent anywhere
- The only dependency (`mido`) is a pure-Python MIDI library with no telemetry

---

## Customisation Prompts

You can edit these values in `reggae_drum_engine.py`:

```python
# In the Humanizer class:
timing_sigma    = 6    # Gaussian timing jitter sigma (ticks). Higher = more human.
velocity_variance = 6  # +/- velocity variance per hit
snare_layback   = 10   # Ticks behind beat for snare/cross-stick (pocket depth)
hat_push        = 4    # Ticks ahead of beat for hi-hats (forward push)

# In generate():
bpm             = 120  # Must match Cubase project tempo
output_dir      = "output"
```

To add a completely new section style, write a new `groove_*()` function
following the same pattern as `groove_one_drop()` and register it in
`build_bar()`.

---

## License

MIT License -- free to use, modify, and distribute.
