"""
reggae_drum_engine.py
=====================
Reggae Drum Pattern Generator for Groove Agent SE 6 / Cubase 13 Pro

Generates two MIDI files:
  output/reggae_one_bar_loop.mid      - Single polished 1-bar loop
  output/reggae_full_arrangement.mid  - Full 136-bar song arrangement

Also generates:
  output/groove_agent_se6.drm         - Cubase Drum Map (named Drum Editor lanes)

GROOVE DESIGN PHILOSOPHY
-------------------------
Real reggae drummers are DISCIPLINED, not random. This engine enforces:

  1. FIXED REPEATING PATTERNS
     The groove skeleton is identical every bar within a section.
     Only timing (+/- ticks) and velocity (+/- values) vary -- not structure.

  2. CYMBALS MARK SECTIONS ONLY
     Crash cymbals fire ONCE: on bar 1 of any section where energy rises.
     No random mid-pattern crashes. No splash on random bars.
     Ride bell is only used in Final Chorus -- not in verses.

  3. RIM ROLLS EVERY 8 BARS
     A cross-stick roll (8 rapid 16th hits, building velocity) fires
     on the LAST bar of every 8-bar phrase, globally counted.
     Between rolls: the groove stays locked and repetitive.

  4. THE ONE-DROP IS SACRED
     Kick + cross-stick on BEAT 3 (step 8) is the reggae heartbeat.
     The kick pattern does not vary randomly bar-to-bar.
     Pickup notes (step 7) are structural -- always present in verse sections.

  5. HUMANIZATION = FEEL, NOT CHAOS
     random.gauss() adds realistic micro-timing per instrument feel zone.
     random.randint() adds subtle velocity shading.
     Neither decides WHAT to play -- only HOW it feels.

MIDI IMPLEMENTATION (Groove Agent SE 6 Acoustic Agent)
-------------------------------------------------------
  Channel  : 10 (mido channel=9, 0-indexed)
  CC#4     : Hi-Hat Foot Controller -- openness 0=closed, 127=open
             Sent 3 ticks BEFORE each hat note so GA SE 6 reads it first.
             In GA SE 6: hi-hat pad Macro page -> FC filter must NOT be yellow.
  CC#7     : Volume (fixed per slot in GA SE 6)
  CC#10    : Pan    (fixed per slot in GA SE 6)
  AVOID CC#64 -- interferes with GA SE 6 pattern transport reset

GM NOTE LAYOUT (GA SE 6 Acoustic Agent default)
  35  Kick soft (ghost touch / pickup)
  36  Kick hard (main anchor)
  37  Cross-stick / Side-stick  <-- reggae beat 3 rimshot
  38  Snare acoustic (vel 28-55 = ghost layer, vel 100+ = rimshot layer)
  42  Hi-Hat closed tip
  44  Hi-Hat pedal chick
  46  Hi-Hat open
  49  Crash cymbal 1
  50  Tom High
  48  Tom Hi-Mid
  47  Tom Lo-Mid
  43  Tom Floor
  51  Ride body
  53  Ride bell
  54  Tambourine
  69  Cabasa
  70  Shaker / Maracas
"""

import random
import os
import mido
import xml.etree.ElementTree as ET
from mido import Message, MidiFile, MidiTrack, MetaMessage

# ===========================================================
# GM NOTE CONSTANTS  (Groove Agent SE 6 / General MIDI)
# ===========================================================
KICK_HARD   = 36
KICK_SOFT   = 35
CROSS_STICK = 37
SNARE       = 38
HH_CLOSED   = 42
HH_OPEN     = 46
HH_PEDAL    = 44
TOM_HIGH    = 50
TOM_HIMID   = 48
TOM_LOMID   = 47
TOM_FLOOR   = 43
CRASH       = 49
RIDE_BODY   = 51
RIDE_BELL   = 53
TAMBOURINE  = 54
CABASA      = 69
SHAKER      = 70

# CC#4 openness zones (GA SE 6 Acoustic Agent)
HAT_CLOSED     = 0
HAT_SEMI_CLOSED= 25
HAT_SEMI_OPEN  = 55
HAT_OPEN       = 110

DRUM_CH        = 9      # mido 0-indexed = MIDI Channel 10
TPB            = 480    # Ticks per beat (Cubase 13 default)
STEP           = TPB // 4   # 120 ticks = 1 sixteenth note


# ===========================================================
# HUMANIZER  --  feel only, never decides WHAT to play
# ===========================================================
class Humanizer:
    """
    Adds micro-timing and velocity variation per instrument feel zone.

    Feel zones at 120 BPM / 480 PPQ (1 tick = ~1.04 ms):
      hat    :  -4 ticks pushed ahead  (locks the groove)
      kick   :  gaussian only, sigma=5 (on the grid)
      snare  : +10 ticks layback       (the reggae pocket)
      neutral:  gaussian only, sigma=6

    Structural decisions (what note, what step) are NEVER made here.
    """
    def __init__(self, timing_sigma=6, velocity_variance=6,
                 snare_layback=10, hat_push=4):
        self.timing_sigma      = timing_sigma
        self.velocity_variance = velocity_variance
        self.snare_layback     = snare_layback
        self.hat_push          = hat_push

    def tick(self, base: int, feel: str = "neutral") -> int:
        jitter = int(random.gauss(0, self.timing_sigma))
        if feel == "snare":
            jitter += self.snare_layback
        elif feel == "hat":
            jitter -= self.hat_push
        return max(0, base + jitter)

    def vel(self, base: int, lo: int = -1, hi: int = -1) -> int:
        spread = self.velocity_variance if lo < 0 else (hi - lo) // 2
        v = base + random.randint(-spread, spread)
        return max(1, min(127, v))


# ===========================================================
# EVENT BUILDER
# ===========================================================
class EventBuilder:
    """Accumulates note and CC events. All times are absolute ticks."""

    def __init__(self, humanizer: Humanizer):
        self.h     = humanizer
        self.notes = []   # (abs_tick, note, velocity, dur_ticks, channel)
        self.ccs   = []   # (abs_tick, channel, cc_num, value)

    # --- raw helpers ---
    def _note(self, tick, note, vel, dur, feel="neutral"):
        t = self.h.tick(tick, feel)
        v = self.h.vel(vel)
        self.notes.append((t, note, v, dur, DRUM_CH))

    def _cc(self, tick, num, val):
        self.ccs.append((max(0, tick), DRUM_CH, num, val))

    def hat_cc(self, tick, openness):
        """CC#4 emitted 3 ticks before hat note so GA SE 6 reads it first."""
        self._cc(max(0, tick - 3), 4, openness)

    # --- instrument helpers ---
    def kick(self, tick, vel=118, soft=False):
        note = KICK_SOFT if soft else KICK_HARD
        self._note(tick, note, vel, 55, "kick")

    def cross_stick(self, tick, vel=112):
        self._note(tick, CROSS_STICK, vel, 55, "snare")

    def ghost(self, tick, vel=40):
        v = max(28, min(55, vel + random.randint(-5, 5)))
        self._note(tick, SNARE, v, 30, "snare")

    def snare_hit(self, tick, vel=102):
        self._note(tick, SNARE, vel, 55, "snare")

    def hat_closed(self, tick, vel=85):
        self.hat_cc(tick, HAT_CLOSED)
        self._note(tick, HH_CLOSED, vel, 28, "hat")

    def hat_semi_open(self, tick, vel=100):
        self.hat_cc(tick, HAT_SEMI_OPEN)
        self._note(tick, HH_CLOSED, vel, 35, "hat")   # CC#4 sets openness

    def hat_open(self, tick, vel=106):
        self.hat_cc(tick, HAT_OPEN)
        self._note(tick, HH_OPEN, vel, 85, "hat")

    def hat_choke(self, tick):
        """Pre-close CC#4 before next hit to choke open ring."""
        self.hat_cc(tick, HAT_CLOSED)

    def hat_pedal(self, tick, vel=70):
        self._note(tick, HH_PEDAL, vel, 28, "hat")

    def crash(self, tick, vel=112):
        """Section-entry crash -- used sparingly, never mid-bar."""
        self._note(tick, CRASH, vel, 380, "neutral")

    def ride_body(self, tick, vel=88):
        self._note(tick, RIDE_BODY, vel, 38, "hat")

    def ride_bell(self, tick, vel=98):
        self._note(tick, RIDE_BELL, vel, 42, "hat")

    def shaker(self, tick, vel=58):
        self._note(tick, SHAKER, vel, 22, "hat")

    def tambourine(self, tick, vel=86):
        self._note(tick, TAMBOURINE, vel, 28, "neutral")

    def cabasa(self, tick, vel=78):
        self._note(tick, CABASA, vel, 22, "neutral")

    def tom(self, tick, drum=TOM_HIMID, vel=100):
        self._note(tick, drum, vel, 75, "neutral")


# ===========================================================
# STEP-TO-TICK HELPER
# ===========================================================
def S(bar: int, step: int) -> int:
    """Absolute tick for step (0-15) in bar (0-indexed)."""
    return (bar * 16 + step) * STEP


# ===========================================================
# CORE PATTERN LIBRARY
# All patterns are FIXED SKELETONS -- identical every bar.
# Humanizer adds feel; nothing here is structurally random.
# ===========================================================

# -----------------------------------------------------------
# THE ONE-DROP  (foundation of all reggae sections)
# Kick + cross-stick LOCKED on beat 3 (step 8).
# Open hat pickup on step 7 (beat 2 "a") -- always present.
# -----------------------------------------------------------
def groove_one_drop(eb: EventBuilder, bar: int):
    """
    Fixed one-drop skeleton -- the bedrock of roots reggae.
    Step layout:
      0   4   8   12   <- quarter beats
      CH  CH  CH   CH  <- closed hat (on-beats)
       S   S   S    S  <- semi-open hat (offbeats: 2,6,10,14)
              O        <- open hat pickup (step 7, beat 2 "a")
              X        <- cross-stick (step 8, beat 3)
      K       K        <- kick: step 8 anchor + step 7 soft pickup
    """
    # Hi-hats: 8th notes
    for step in range(0, 16, 2):
        if step in (2, 6, 10, 14):       # offbeat 8ths
            eb.hat_semi_open(S(bar, step), vel=98)
        else:                             # downbeat 8ths
            eb.hat_closed(S(bar, step), vel=82)

    # Open hat pickup before beat 3 -- structural, always fires
    eb.hat_open(S(bar, 7), vel=104)
    eb.hat_choke(S(bar, 8))              # kill ring when cross-stick lands

    # Pedal chick on beat 3 alongside the cross-stick
    eb.hat_pedal(S(bar, 8), vel=68)

    # ONE-DROP anchor: kick + cross-stick beat 3
    eb.kick(S(bar, 8), vel=120)
    eb.cross_stick(S(bar, 8), vel=112)

    # Structural pickup kick on step 7 (beat 2 "a")
    eb.kick(S(bar, 7), vel=72, soft=True)

    # Ghost snares at fixed structural positions
    eb.ghost(S(bar,  7), vel=38)
    eb.ghost(S(bar, 11), vel=36)
    eb.ghost(S(bar, 15), vel=36)


# -----------------------------------------------------------
# PERCUSSION LAYER  (shaker + cabasa + tambourine)
# Identical every bar, adds forward drive without noise.
# -----------------------------------------------------------
def groove_percussion(eb: EventBuilder, bar: int):
    """
    16th-note shaker (offbeats louder).
    Cabasa + Tambourine on beats 2 and 4 (steps 4, 12).
    """
    for step in range(16):
        vel = 48 if step % 2 == 0 else 68
        eb.shaker(S(bar, step), vel)

    eb.cabasa(S(bar,  4), vel=75)
    eb.cabasa(S(bar, 12), vel=75)
    eb.tambourine(S(bar,  4), vel=84)
    eb.tambourine(S(bar, 12), vel=84)


# -----------------------------------------------------------
# STEPPERS KICK LAYER  (chorus sections)
# Four-on-the-floor driving kick over the one-drop cross-stick.
# -----------------------------------------------------------
def groove_steppers_kick(eb: EventBuilder, bar: int):
    """
    Four-on-the-floor kick: beats 1, 2, 3, 4.
    Beat 3 is loudest (one-drop anchor).
    """
    for step, vel in ((0, 116), (4, 106), (8, 122), (12, 108)):
        eb.kick(S(bar, step), vel=vel)


# -----------------------------------------------------------
# CHORUS HAT/RIDE LAYER
# Ride body on on-beats, ride bell on offbeats.
# Replaces hi-hats for a bigger, more open chorus sound.
# NO ghost hats during chorus ride -- keeps it clean.
# -----------------------------------------------------------
def groove_chorus_ride(eb: EventBuilder, bar: int):
    for step in range(0, 16, 2):
        if step in (2, 6, 10, 14):
            eb.ride_bell(S(bar, step), vel=96)
        else:
            eb.ride_body(S(bar, step), vel=85)


# -----------------------------------------------------------
# INTRO / OUTRO  (sparse -- building in, stripping out)
# -----------------------------------------------------------
def groove_intro(eb: EventBuilder, bar: int, bar_in_section: int, total: int):
    """
    Bars 0-3: shaker + tambourine only (anticipation).
    Bars 4+:  sparse closed hat on quarter notes, ghost cross-stick.
    No kick. No crash. No fills.
    """
    for step in range(16):
        vel = 44 if step % 2 == 0 else 62
        eb.shaker(S(bar, step), vel)
    eb.tambourine(S(bar,  4), 80)
    eb.tambourine(S(bar, 12), 80)

    if bar_in_section >= (total // 2):
        # Add quarter-note hats in second half of intro
        for step in (0, 4, 8, 12):
            eb.hat_closed(S(bar, step), vel=68)


def groove_outro(eb: EventBuilder, bar: int, bar_in_section: int, total: int):
    """Mirror of intro -- progressively strips away."""
    remaining = total - bar_in_section

    for step in range(16):
        vel = 44 if step % 2 == 0 else 62
        eb.shaker(S(bar, step), vel)

    if remaining > (total // 2):
        # Full groove in first half of outro
        groove_one_drop(eb, bar)
        groove_percussion(eb, bar)
    else:
        # Strip to hats only then shaker
        for step in (0, 4, 8, 12):
            eb.hat_closed(S(bar, step), vel=60)
        eb.tambourine(S(bar, 4), 75)


# -----------------------------------------------------------
# PRE-CHORUS  (same one-drop groove + ride bell replaces offbeat hat)
# No structural extras -- the ride bell lifts the energy upward.
# -----------------------------------------------------------
def groove_pre_chorus(eb: EventBuilder, bar: int):
    """
    Same one-drop skeleton, but offbeat hat replaced by ride bell.
    Builds energy toward the chorus without adding noise.
    """
    # On-beat closed hats
    for step in (0, 4, 8, 12):
        eb.hat_closed(S(bar, step), vel=80)

    # Offbeat ride bell (replaces semi-open hat)
    for step in (2, 6, 10, 14):
        eb.ride_bell(S(bar, step), vel=94)

    # Open hat pickup + choke (same as verse)
    eb.hat_open(S(bar, 7), vel=102)
    eb.hat_choke(S(bar, 8))
    eb.hat_pedal(S(bar, 8), vel=65)

    # Kick + cross-stick on beat 3
    eb.kick(S(bar, 8), vel=120)
    eb.cross_stick(S(bar, 8), vel=114)
    eb.kick(S(bar, 7), vel=72, soft=True)

    # Ghost snares (same fixed positions)
    eb.ghost(S(bar,  7), vel=38)
    eb.ghost(S(bar, 11), vel=36)
    eb.ghost(S(bar, 15), vel=34)


# -----------------------------------------------------------
# CHORUS  (full steppers -- four-on-floor + ride + cross-stick)
# Ride on every 8th note. No open hat. Ghost notes under ride.
# -----------------------------------------------------------
def groove_chorus(eb: EventBuilder, bar: int):
    """
    Steppers chorus pattern.
    Ride body/bell replaces hi-hat entirely.
    Cross-stick stays on beat 3 -- still the reggae anchor.
    """
    groove_chorus_ride(eb, bar)
    groove_steppers_kick(eb, bar)

    # Cross-stick on beat 3 (one-drop anchor even in chorus)
    eb.cross_stick(S(bar, 8), vel=116)

    # Ghost snares under the ride -- sparse, same fixed positions
    eb.ghost(S(bar,  7), vel=38)
    eb.ghost(S(bar, 11), vel=34)


# -----------------------------------------------------------
# DUB BREAKDOWN  (space is the music)
# Quarter-note hats only. Kick on beat 1 only. Minimal cross-stick.
# -----------------------------------------------------------
def groove_dub(eb: EventBuilder, bar: int):
    """
    Classic dub space: only what is essential.
    Quarter-note closed hats, kick on beat 1, cross-stick on beat 3.
    Shaker keeps the 16th-note pulse locked underneath.
    No ghosts. No fills. No cymbals.
    """
    for step in (0, 4, 8, 12):
        eb.hat_closed(S(bar, step), vel=68)

    for step in range(16):
        vel = 42 if step % 2 == 0 else 60
        eb.shaker(S(bar, step), vel)

    eb.kick(S(bar, 0), vel=112)
    eb.cross_stick(S(bar, 8), vel=96)
    eb.cabasa(S(bar,  4), vel=68)
    eb.cabasa(S(bar, 12), vel=68)


# -----------------------------------------------------------
# RIM ROLL  (every 8 bars, last bar of that phrase)
# 8 rapid 16th cross-stick hits from step 8, building velocity.
# Replaces the last half of whatever pattern was running.
# -----------------------------------------------------------
def groove_rim_roll(eb: EventBuilder, bar: int):
    """
    Iconic reggae cross-stick roll on the final bar of every 8-bar phrase.
    Fires on steps 8 through 15 -- beat 3 through bar end.
    Velocity crescendo: 88 -> 116 across 8 hits.
    """
    vels = (88, 94, 98, 102, 106, 110, 114, 116)
    for i, step in enumerate(range(8, 16)):
        t = S(bar, step)
        eb.cross_stick(t, vel=vels[i])

    # Also play the first half of the normal groove (beats 1-2)
    for step in (0, 2, 4, 6):
        if step in (2, 6):
            eb.hat_semi_open(S(bar, step), vel=96)
        else:
            eb.hat_closed(S(bar, step), vel=80)

    eb.kick(S(bar, 0), vel=60, soft=True)
    for step in range(16):
        vel = 46 if step % 2 == 0 else 66
        eb.shaker(S(bar, step), vel)


# -----------------------------------------------------------
# TOM FILL  (4-step descending roll -- only inside rim_roll bars
# if dub section, fires at final bar of dub as a transition out)
# -----------------------------------------------------------
def groove_tom_fill(eb: EventBuilder, bar: int):
    """
    Descending tom roll across steps 12-15.
    Used ONLY at the end of the Dub Breakdown to announce re-entry.
    Followed by a crash on bar 0 of the next section.
    """
    toms = (TOM_HIGH, TOM_HIMID, TOM_LOMID, TOM_FLOOR)
    vels = (88, 96, 108, 118)
    for step, drum, vel in zip(range(12, 16), toms, vels):
        eb.tom(S(bar, step), drum=drum, vel=vel)

    # Half-bar groove still plays underneath
    for step in (0, 2, 4, 6):
        if step in (2, 6):
            eb.hat_semi_open(S(bar, step), vel=95)
        else:
            eb.hat_closed(S(bar, step), vel=80)
    eb.kick(S(bar, 8), vel=115)
    eb.cross_stick(S(bar, 8), vel=110)
    for step in range(12):
        vel = 46 if step % 2 == 0 else 66
        eb.shaker(S(bar, step), vel)


# -----------------------------------------------------------
# SECTION-ENTRY CRASH
# Only fires when energy RISES (1->2, 2->3, or 1->3).
# Only on beat 1 of bar 0 of the new section.
# Never fires mid-section. Never fires twice.
# -----------------------------------------------------------
def section_crash(eb: EventBuilder, bar: int, prev_energy: int, new_energy: int):
    if new_energy > prev_energy:
        eb.crash(S(bar, 0), vel=115)


# ===========================================================
# SINGLE BAR DISPATCHER
# Decides which patterns to combine based on section + bar index.
# All decisions here are DETERMINISTIC based on section metadata.
# ===========================================================
def build_bar(eb: EventBuilder, abs_bar: int, section_name: str,
              bar_in_section: int, section_length: int,
              is_rim_roll_bar: bool, is_dub_tom_bar: bool):
    """
    Dispatches the correct pattern combination for one bar.
    The rim roll overrides the second half of any pattern.
    Tom fill overrides only the dub transition bar.
    """
    if section_name == "Intro":
        groove_intro(eb, abs_bar, bar_in_section, section_length)

    elif section_name == "Outro":
        groove_outro(eb, abs_bar, bar_in_section, section_length)

    elif section_name == "Dub Breakdown":
        if is_dub_tom_bar:
            groove_tom_fill(eb, abs_bar)
        elif is_rim_roll_bar:
            groove_rim_roll(eb, abs_bar)
            for step in range(12):
                vel = 42 if step % 2 == 0 else 60
                eb.shaker(S(abs_bar, step), vel)
        else:
            groove_dub(eb, abs_bar)

    elif "Verse" in section_name:
        if is_rim_roll_bar:
            groove_rim_roll(eb, abs_bar)
            groove_percussion(eb, abs_bar)
        else:
            groove_one_drop(eb, abs_bar)
            groove_percussion(eb, abs_bar)

    elif "Pre-Chorus" in section_name:
        if is_rim_roll_bar:
            groove_rim_roll(eb, abs_bar)
            groove_percussion(eb, abs_bar)
        else:
            groove_pre_chorus(eb, abs_bar)
            groove_percussion(eb, abs_bar)

    elif "Chorus" in section_name:
        if is_rim_roll_bar:
            groove_rim_roll(eb, abs_bar)
            groove_percussion(eb, abs_bar)
        else:
            groove_chorus(eb, abs_bar)
            groove_percussion(eb, abs_bar)


# ===========================================================
# CUBASE DRUM MAP EXPORTER
# ===========================================================
class DrumMapExporter:
    """
    Generates a Cubase 13 Drum Map (.drm) XML file.
    Import: MIDI menu -> Drum Map Setup -> Import...
    """
    MAP = [
        (35, "Kick (Soft/Ghost)",        10, 16),
        (36, "Kick (Hard/Anchor)",        10, 16),
        (37, "Cross-Stick / Side-Stick",  10, 16),
        (38, "Snare (Ghost or Full)",     10, 16),
        (42, "Hi-Hat Closed",             10, 16),
        (44, "Hi-Hat Pedal Chick",        10, 16),
        (46, "Hi-Hat Open",               10, 16),
        (43, "Tom Floor",                 10, 16),
        (47, "Tom Lo-Mid",                10, 16),
        (48, "Tom Hi-Mid",                10, 16),
        (50, "Tom High",                  10, 16),
        (49, "Crash Cymbal",              10, 16),
        (51, "Ride Body",                 10, 16),
        (53, "Ride Bell",                 10, 16),
        (54, "Tambourine",                10, 16),
        (69, "Cabasa",                    10, 16),
        (70, "Shaker / Maracas",          10, 16),
    ]

    def export(self, path: str, name: str = "GA SE6 Roots Reggae"):
        root = ET.Element("drummap")
        root.set("name", name)
        for note, label, ch, q in self.MAP:
            e = ET.SubElement(root, "entry")
            for k, v in [("note", note), ("name", label), ("channel", ch),
                         ("output", note), ("quantize", q), ("mute", 0),
                         ("iNote", note), ("oNote", note), ("len", 1), ("disp", 0)]:
                e.set(k, str(v))
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        with open(path, "wb") as f:
            tree.write(f, xml_declaration=True, encoding="utf-8")
        print(f"  [DRM] {path}")


# ===========================================================
# MIDI ASSEMBLER
# ===========================================================
def assemble_midi(eb: EventBuilder, bpm: int, out_path: str, track_name: str):
    """
    Converts EventBuilder contents to a Standard MIDI File.
    Event priority at same tick: CCs (1) -> note-offs (2) -> note-ons (3)
    """
    midi  = MidiFile(ticks_per_beat=TPB)
    track = MidiTrack()
    midi.tracks.append(track)

    track.append(MetaMessage("track_name", name=track_name, time=0))
    track.append(MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(MetaMessage("time_signature",
                             numerator=4, denominator=4,
                             clocks_per_click=24,
                             notated_32nd_notes_per_beat=8, time=0))

    # GM System ON SysEx (tells GA SE 6 this is a GM drum file)
    track.append(mido.Message("sysex", data=[0x7E, 0x7F, 0x09, 0x01], time=0))

    # Initialise drum channel
    track.append(Message("control_change", channel=DRUM_CH, control=7,  value=100, time=0))
    track.append(Message("control_change", channel=DRUM_CH, control=10, value=64,  time=0))
    track.append(Message("control_change", channel=DRUM_CH, control=4,  value=0,   time=0))

    raw = []
    for (tick, note, vel, dur, ch) in eb.notes:
        raw.append((tick,       3, Message("note_on",  channel=ch, note=note, velocity=vel, time=0)))
        raw.append((tick + dur, 2, Message("note_off", channel=ch, note=note, velocity=0,   time=0)))
    for (tick, ch, cc, val) in eb.ccs:
        raw.append((tick, 1, Message("control_change", channel=ch, control=cc, value=val, time=0)))

    raw.sort(key=lambda x: (x[0], x[1]))

    cur = 0
    for tick, _, msg in raw:
        delta = max(0, tick - cur)
        cur   = tick
        track.append(msg.copy(time=int(delta)))

    track.append(MetaMessage("end_of_track", time=0))
    midi.save(out_path)
    n_n = sum(1 for _, p, _ in raw if p == 3)
    n_c = sum(1 for _, p, _ in raw if p == 1)
    print(f"  [MID] {out_path}  ({n_n} notes, {n_c} CC events)")


# ===========================================================
# MAIN GENERATOR
# ===========================================================
def generate(bpm: int = 120, output_dir: str = "output"):
    """
    Generate all output files.

    Parameters
    ----------
    bpm        : Tempo -- must match your Cubase project
    output_dir : Folder for generated files
    """
    os.makedirs(output_dir, exist_ok=True)

    print(f"\nReggae Drum Engine  |  GA SE 6 / Cubase 13  |  {bpm} BPM\n")

    # ----------------------------------------------------------
    # 1. ONE-BAR LOOP  (for sampling / loop library use)
    # ----------------------------------------------------------
    print("Generating 1-bar one-drop loop...")
    eb_loop = EventBuilder(Humanizer())
    groove_one_drop(eb_loop, bar=0)
    groove_percussion(eb_loop, bar=0)
    assemble_midi(eb_loop, bpm,
                  os.path.join(output_dir, "reggae_one_bar_loop.mid"),
                  "Reggae 1-Bar Loop")

    # ----------------------------------------------------------
    # 2. FULL ARRANGEMENT  (136 bars)
    #
    # SONG STRUCTURE:
    #   Section          | Bars | Energy | Notes
    #   Intro            |   8  |   1    | Shaker only -> sparse build
    #   Verse 1          |  16  |   2    | Full one-drop
    #   Pre-Chorus 1     |   8  |   2    | Ride bell replaces offbeat hat
    #   Chorus 1         |  16  |   3    | Steppers + ride
    #   Verse 2          |  16  |   2    | Full one-drop
    #   Pre-Chorus 2     |   8  |   2    | Ride bell
    #   Chorus 2         |  16  |   3    | Steppers + ride
    #   Dub Breakdown    |   8  |   1    | Stripped -- space is music
    #   Final Chorus     |  16  |   3    | Steppers + ride (tom fill exit)
    #   Outro            |   8  |   1    | Strips back to shaker
    #
    # CYMBAL RULE:  Crash fires ONLY on bar 0 of energy-rising sections.
    # RIM ROLL RULE: Every bar where abs_bar % 8 == 7 (globally counted).
    # ----------------------------------------------------------
    print("Generating full 136-bar arrangement...")

    sections = [
        ("Intro",          8, 1),
        ("Verse 1",       16, 2),
        ("Pre-Chorus 1",   8, 2),
        ("Chorus 1",      16, 3),
        ("Verse 2",       16, 2),
        ("Pre-Chorus 2",   8, 2),
        ("Chorus 2",      16, 3),
        ("Dub Breakdown",  8, 1),
        ("Final Chorus",  16, 3),
        ("Outro",          8, 1),
    ]

    eb_arr      = EventBuilder(Humanizer())
    cur_bar     = 0
    prev_energy = 0

    for sec_name, bar_count, energy in sections:
        dub_tom_bar = cur_bar + bar_count - 1  # Only for Dub Breakdown

        for b in range(bar_count):
            abs_bar = cur_bar + b

            # Section-entry crash (energy rise only, bar 0 of section)
            if b == 0 and energy > prev_energy:
                section_crash(eb_arr, abs_bar, prev_energy, energy)

            # Rim roll every 8 bars globally (except intro/outro/first bar)
            is_rim_roll = (abs_bar % 8 == 7) and sec_name not in ("Intro", "Outro")

            # Dub Breakdown: tom fill ONLY on the very last bar
            is_dub_tom = (sec_name == "Dub Breakdown") and (abs_bar == dub_tom_bar)

            # If it's a rim roll bar AND a dub tom bar -- tom fill wins
            if is_dub_tom:
                is_rim_roll = False

            build_bar(eb_arr, abs_bar, sec_name, b, bar_count,
                      is_rim_roll, is_dub_tom)

        cur_bar    += bar_count
        prev_energy = energy

    assemble_midi(eb_arr, bpm,
                  os.path.join(output_dir, "reggae_full_arrangement.mid"),
                  "Reggae Full Arrangement")

    # ----------------------------------------------------------
    # 3. CUBASE DRUM MAP
    # ----------------------------------------------------------
    print("Generating Cubase Drum Map...")
    DrumMapExporter().export(
        os.path.join(output_dir, "groove_agent_se6.drm"),
        name="GA SE6 Roots Reggae"
    )

    print(f"""
Done. Files written to: {os.path.abspath(output_dir)}/

CUBASE 13 PRO SETUP
-------------------
1. Create Instrument Track -> load Groove Agent SE 6
   Pick any Acoustic Agent kit (e.g. "Vintage Studio Kit")

2. Import Drum Map:
   MIDI menu -> Drum Map Setup -> Import -> groove_agent_se6.drm
   Then: Inspector -> Drum Map -> "GA SE6 Roots Reggae"

3. Drag reggae_full_arrangement.mid onto the GA SE 6 track
   Open in Drum Editor for named instrument lanes

4. Hi-Hat CC#4 (IMPORTANT):
   In GA SE 6, on the hi-hat pad Macro page:
   The "FC" (Foot Controller) button must NOT be highlighted/yellow.
   If it is yellow, click it to deactivate -- the MIDI already carries CC#4.

5. Project tempo must be {bpm} BPM.
   To change tempo: edit BPM in this script and re-run.

6. Optional -- export GA SE 6 mixer to Cubase:
   Right-click the Kit -> "Export Mixer to Cubase"
   This creates one mixer channel per drum piece.
""")


if __name__ == "__main__":
    generate(bpm=120, output_dir="output")
