#!/usr/bin/env python3
"""
Generator for a GB Studio v4 (4.3.x) demo game, built on the app's blank template.

Usage: python3 gen_gb_demo.py <project_root> <blank_template_dir> [sample_assets_dir]

- project_root: target project dir (e.g. ~/gb-demo). The blank template is copied in,
  then assets are overwritten/generated and game content (.gbsres) is written.
- blank_template_dir: the GB Studio app's 'blank' project template (canonical schemas).
- sample_assets_dir (optional): dir containing Tronimal_Sound_Effects.sav(.gbsres)
  (from the gbs2 sample project) for a ready-made SFX pack.

Everything is derived from schemas verified against GB Studio 4.3.2:
  project.gbsproj, project/{settings,variables,engine_field_values,palettes/*}.gbsres,
  project/scenes/<s>/{scene.gbsres, actors/*.gbsres, triggers/*.gbsres},
  assets/**/<file>.<gbsres sibling>.
"""
import hashlib, json, os, shutil, struct, sys, uuid, zlib

# ---------------------------------------------------------------- constants
K = (7, 24, 33)      # black   #071821
D = (48, 104, 80)    # dark    #306850  (backgrounds only)
L = (134, 192, 108)  # light   #86c06c
W = (224, 248, 207)  # white   #e0f8cf
T = (101, 255, 0)    # transparent (sprites only) #65ff00

PAL_BG = [K, D, L, W]     # DMG green, backgrounds
PAL_SPR = [K, L, W, T]    # sprites

def u():
    return str(uuid.uuid4())

def slug(s):
    out = []
    for ch in s.lower():
        out.append(ch if ch.isalnum() else "_")
    return "".join(out)

# ---------------------------------------------------------------- png writer (no deps)
def write_png(path, w, h, px):
    """px: list of rows, each row list of (r,g,b). RGB8, no alpha."""
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"".join(struct.pack("BBB", *p) for p in row) for row in px)
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 9))
           + chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)

def grid(rows, pal):
    """rows: list of strings (<=16 chars, '.' = transparent); frames are 16x16."""
    assert len(rows) == 16, "sprite frames are 16px tall"
    out = []
    for r in rows:
        assert len(r) <= 16, f"frame row width {len(r)} > 16"
        out.append([pal[c] for c in r.ljust(16, ".")])
    return out

SPR_CHARS = {"K": K, "L": L, "W": W, "T": T, ".": T}

# ---------------------------------------------------------------- pixel art
# Player: 96x16, 6 frames: down1 down2 up1 up2 right1 right2  (left = auto-flip)
def _head(facing):
    # facing: 'down' shows face, 'up' shows hair, 'right' shows profile
    if facing == "down":
        return [
            "....KKKKKK......",
            "...KWWWWWWK.....",
            "...KWKWWKWK.....",
            "...KWWWWWWK.....",
            "....KKKKKK......",
        ]
    if facing == "up":
        return [
            "....KKKKKK......",
            "....KKKKKK......",
            "....KLLLLK......",
            "....KKKKKK......",
            "....KKKKKK......",
        ]
    # right profile
    return [
            ".....KKKKK......",
            ".....KWWWWK.....",
            ".....KWKKWK.....",
            ".....KWWWWK.....",
            ".....KKKKK......",
        ]

def _body_down(leg):
    b = [
        "....KLLLLK......",
        "....KLWLLK......",
        "....KLLLLK......",
        "....KLLLLK......",
        ".....KLLK.......",
        ".....KLLK.......",
        ".....KKKK.......",
    ]
    if leg == 0:
        b += ["......K.K.......", ".....KK..K......", ".....KK..K......"]
    else:
        b += ["......KK........", "......K.K.......", "......KK........"]
    b.append("................")
    return b

def _body_up(leg):
    b = [
        "....KLLLLK......",
        "....KLLKLK......",
        "....KLLLLK......",
        "....KLLLLK......",
        ".....KLLK.......",
        ".....KLLK.......",
        ".....KKKK.......",
    ]
    if leg == 0:
        b += ["......K.K.......", ".....KK..K......", ".....KK..K......"]
    else:
        b += ["......KK........", "......K.K.......", "......KK........"]
    b.append("................")
    return b

def _body_right(leg):
    b = [
        ".....KLLLK......",
        ".....KLLKL......",
        ".....KLLLK......",
        ".....KLLLK......",
        "......KLK.......",
        "......KLK.......",
    ]
    if leg == 0:
        b += [".....K.KK.......", "....K...KK......", "....K..K.K......"]
    else:
        b += ["......KKK.......", "......K.KK......", ".....KK..K......"]
    b += ["................", "................"]
    return b

def player_frames():
    pal = SPR_CHARS
    f = []
    for leg in (0, 1):
        f.append(grid(_head("down") + _body_down(leg), pal))
    for leg in (0, 1):
        f.append(grid(_head("up") + _body_up(leg), pal))
    for leg in (0, 1):
        f.append(grid(_head("right") + _body_right(leg), pal))
    return f  # [down1, down2, up1, up2, right1, right2]

# NPC (rita/bo): 48x16, 3 frames: down up right  (left = auto-flip)
def npc_frames():
    pal = SPR_CHARS
    down = grid([
        "....KKKKKK......",
        "...KWWWWWWK.....",
        "...KWKWWKWK.....",
        "....KKKKKK......",
        "....KLLLLK......",
        "....KLWLLK......",
        "....KLLLLK......",
        "....KLLLLK......",
        ".....KLLK.......",
        ".....KLLK.......",
        "......KK......",
        "......KK......",
        ".....KKKK.....",
        "................",
        "................",
        "................",
    ], pal)
    up = grid([
        "....KKKKKK......",
        "....KKKKKK......",
        "....KLLKLK......",
        "....KKKKKK......",
        "....KLLLLK......",
        "....KLLKLK......",
        "....KLLLLK......",
        "....KLLLLK......",
        ".....KLLK.......",
        ".....KLLK.......",
        "......KK......",
        "......KK......",
        ".....KKKK.....",
        "................",
        "................",
        "................",
    ], pal)
    right = grid([
        ".....KKKKK......",
        ".....KWWWWK.....",
        ".....KWKKWK.....",
        ".....KKKKK......",
        ".....KLLLK......",
        ".....KLLKL......",
        ".....KLLLK......",
        ".....KLLLK......",
        "......KLK.......",
        "......KLK.......",
        "......KKK.......",
        "......KKK.......",
        ".....KKKKK......",
        "................",
        "................",
        "................",
    ], pal)
    return [down, up, right]

def star_frame():
    return grid([
        "................",
        "......KKKK......",
        ".....KWWWWK.....",
        "....KWWWWWWK....",
        "...KWWWWWWWWK...",
        "....KWWWWWWK....",
        ".....KWWWK......",
        "......KKK.......",
        "......KKK.......",
        ".....KWWWK......",
        "....KWWWWWWK....",
        "...KWWWWWWWWK...",
        "....KWWWWWWK....",
        ".....KWWWWK.....",
        "......KKKK......",
        "................",
    ], SPR_CHARS)

# ---------------------------------------------------------------- backgrounds
def _grass_tile(variant, seed):
    # deterministic per variant -> one fixed tile image per variant (keeps
    # unique-tile count far under the 192-per-scene limit)
    rng_state = [12345 + variant * 777]
    def rng():
        rng_state[0] = (rng_state[0] * 1103515245 + 12345) % (2 ** 31)
        return (rng_state[0] >> 16) / 65536.0
    t = []
    for y in range(8):
        row = []
        for x in range(8):
            r = rng()
            if r < 0.18 + 0.06 * variant:
                row.append(D)
            elif r < 0.24 + 0.06 * variant:
                row.append(W)
            else:
                row.append(L)
        t.append(row)
    return t

GRASS_BANK = [_grass_tile(v, None) for v in range(3)]

def meadow_bg():
    rows = []
    for ty in range(18):
        tiles = [GRASS_BANK[(tx + ty * 3) % 3] for tx in range(20)]
        for y in range(8):
            row = []
            for tx in range(20):
                row.extend(tiles[tx][y])
            rows.append(row)
    return rows

def hut_bg():
    rows = []
    rng_state = [999]
    def rng():
        rng_state[0] = (rng_state[0] * 1103515245 + 12345) % (2 ** 31)
        return (rng_state[0] >> 16) / 65536.0
    # pre-generate a small floor tile bank (6 variants) so the scene stays
    # within the 192 unique-tile limit; noise pixels are baked into each tile
    bank = []
    for v in range(6):
        st = [999 + v * 131]
        def r2():
            st[0] = (st[0] * 1103515245 + 12345) % (2 ** 31)
            return (st[0] >> 16) / 65536.0
        t = []
        for y in range(8):
            row = []
            for x in range(8):
                c = D
                if y == 4:
                    c = L
                if r2() < 0.10:
                    c = K
                row.append(c)
            t.append(row)
        bank.append(t)
    for ty in range(18):
        tiles = [bank[(tx + ty * 5) % 6] for tx in range(20)]
        for y in range(8):
            row = []
            for tx in range(20):
                if ty < 2:
                    row.extend(K if (y < 4 or x in (0, 7)) else D for x in range(8))
                elif ty in (8, 9) and tx == 0:
                    row.extend(K if (x < 6 and y > 1) else D for x in range(8))  # doorway
                else:
                    row.extend(tiles[tx][y])
            rows.append(row)
    return rows

# ---------------------------------------------------------------- MOD writer
# v4.3.2 parseMod dialect: [20B name][31 x 31B sample blocks][1B songLen][1B unused]
# [128B positions][4B "M.K.!"][patterns: 64 rows x 4ch x 4B, count = max(positions)+1]
# Sample data is NOT consumed by GBT (duty/wave/noise come from engine defaults),
# so all 31 sample blocks can be empty; only pattern cells matter.
# Cell: b0 = instHi|noteHi, b1 = noteLo, b2 = instLo<<4|effect, b3 = param.
# Note values are 0-indexed; GBT's usable range is 0-based 24..71 (= 1-based C3..B7).
def write_mod(path, song_name="GB Demo"):
    h = bytearray()
    h += song_name.encode("ascii").ljust(20, b"\x00")
    for _ in range(31):
        h += b"\x00" * 22                          # sample name
        h += struct.pack(">H", 0)                # sampleLength
        h += bytes([0, 0x40])                    # finetune, volume
        h += struct.pack(">HH", 0, 0)            # repeatPoint, repeatLength
    h += bytes([1, 0])                           # songLen, unused
    h += bytes(128)                              # positions: all zero -> 1 pattern
    h += b"M.K.!"
    melody = [36, 40, 42, 40, 36, 42, 40, 42, 43, 48, 43, 42, 42, 40, 36, 0]  # C4 E4 G4 ...
    bass = [24] * 4 + [30] * 4 + [28] * 4 + [29] * 4                               # C3 A3 F#3 G3
    def cell(note, inst, eff=0, param=0):
        return bytes([(inst & 0xF0) | (note >> 8), note & 0xFF,
                      ((inst & 0x0F) << 4) | eff, param])
    pat = bytearray()
    for r in range(64):
        i = r % 16
        c1 = cell(melody[i], 2, 0x0F, 0x06) if r == 0 else cell(melody[i], 2)  # pulse 50%, F06=125bpm
        c2 = bytes(4)                                                            # (silent)
        c3 = cell(bass[i], 14) if bass[i] else bytes(4)                           # square bass
        if r == 0:
            c4 = cell(0, 0, 0x0C, 0x20)                                          # noise volume 32
        elif i % 2 == 1:
            c4 = cell(24, 28, 0x0C, 0x20) if i % 4 == 1 else cell(24, 28, 0xEC, 1)  # hat blips
        else:
            c4 = bytes(4)
        pat += c1 + c2 + c3 + c4
    h += pat
    with open(path, "wb") as f:
        f.write(bytes(h))

# ---------------------------------------------------------------- gbsres builders
def ev(command, args, children=None, eid=None):
    e = {"id": eid or u(), "command": command, "args": args}
    if children is not None:
        e["children"] = children
    return e

def num(v):
    return {"type": "number", "value": v}

def sprite_gbsres(template_path, png_path):
    """Copy a template sprite .gbsres, refresh checksum for the replaced PNG."""
    data = json.load(open(template_path))
    data["checksum"] = hashlib.md5(open(png_path, "rb").read()).hexdigest()
    return data

def collision_string(w, h, door_side, door_y, door_h=2):
    """RLE: 1 hex count (1..15) + 1 hex type nibble (0=none,1=top,2=bottom,4=left,8=right,f=solid)."""
    vals = []
    for y in range(h):
        for x in range(w):
            v = 0
            if y == 0: v |= 1
            if y == h - 1: v |= 2
            if x == 0: v |= 4
            if x == w - 1: v |= 8
            if v: v = 0xF  # full solid border
            if door_side == "right" and x == w - 1 and door_y <= y < door_y + door_h: v = 0
            if door_side == "left" and x == 0 and door_y <= y < door_y + door_h: v = 0
            vals.append(v)
    out, i, n = "", 0, len(vals)
    while i < n:
        v = vals[i]
        j = i
        while j + 1 < n and vals[j + 1] == v:
            j += 1
        run = j - i + 1
        while run > 15:
            out += f"{15:x}{v:x}"
            run -= 15
            i += 15
        out += f"{run:x}{v:x}"
        i = j + 1
    return out

# ---------------------------------------------------------------- main
def main():
    project_root = os.path.abspath(sys.argv[1])
    blank = os.path.abspath(sys.argv[2])
    sample = os.path.abspath(sys.argv[3]) if len(sys.argv) > 3 else None
    print(f"[gen] project: {project_root}\n[gen] blank template: {blank}")

    if os.path.exists(project_root):
        shutil.rmtree(project_root)
    shutil.copytree(blank, project_root,
                    ignore=lambda d, n: [n] if n == ".DS_Store" else [])

    # --- project.gbsproj
    proj_p = os.path.join(project_root, "project.gbsproj")
    proj = json.load(open(proj_p))
    proj["name"] = "GB Demo"
    proj["author"] = "Hermes"
    json.dump(proj, open(proj_p, "w"), indent=2)

    # --- settings: start scene + gbt music driver (we ship a .mod)
    meadow_id, hut_id = u(), u()
    st_p = os.path.join(project_root, "project", "settings.gbsres")
    st = json.load(open(st_p))
    st["startSceneId"] = meadow_id
    st["musicDriver"] = "gbt"
    json.dump(st, open(st_p, "w"), indent=2)

    # --- variables
    var_p = os.path.join(project_root, "project", "variables.gbsres")
    vars_res = json.load(open(var_p))
    vars_res["variables"] = [{"id": "0", "name": "Stars", "symbol": "var_stars"}]
    json.dump(vars_res, open(var_p, "w"), indent=2)

    # --- remove placeholder background (replaced by meadow/hut)
    for f in ("placeholder.png", "placeholder.png.gbsres"):
        p = os.path.join(project_root, "assets", "backgrounds", f)
        if os.path.exists(p): os.remove(p)

    # --- assets: sprites (overwrite template PNGs, refresh checksums)
    sprites = os.path.join(project_root, "assets", "sprites")
    def put_sprite(fname, frames):
        # frames: list of 16x16 pixel grids, laid out horizontally in the file
        rows = [[fr[y][x] for fr in frames for x in range(16)] for y in range(16)]
        write_png(os.path.join(sprites, fname), 16 * len(frames), 16, rows)
    player_frames_list = player_frames()
    put_sprite("actor_animated.png", player_frames_list)
    npc = npc_frames()
    put_sprite("actor.png", npc)
    put_sprite("static.png", [star_frame()])

    for f in ("actor_animated.png", "actor.png", "static.png"):
        gbs = os.path.join(sprites, f + ".gbsres")
        if os.path.exists(gbs):
            data = sprite_gbsres(gbs, os.path.join(sprites, f))
            json.dump(data, open(gbs, "w"), indent=2)

    player_sprite_id = json.load(open(os.path.join(sprites, "actor_animated.png.gbsres")))["id"]
    npc_sprite_id = json.load(open(os.path.join(sprites, "actor.png.gbsres")))["id"]
    star_sprite_id = json.load(open(os.path.join(sprites, "static.png.gbsres")))["id"]
    # sanity: template settings must still reference the player sheet
    assert st["defaultPlayerSprites"]["TOPDOWN"] == player_sprite_id, "player sprite id mismatch"

    # --- assets: backgrounds
    bgs = os.path.join(project_root, "assets", "backgrounds")
    meadow_id_bg = u(); hut_id_bg = u()
    write_png(os.path.join(bgs, "meadow.png"), 160, 144, meadow_bg())
    write_png(os.path.join(bgs, "hut.png"), 160, 144, hut_bg())
    for fname, rid, name in (("meadow.png", meadow_id_bg, "meadow"),
                             ("hut.png", hut_id_bg, "hut")):
        res = {"_resourceType": "background", "id": rid, "name": name,
               "symbol": f"bg_{name}", "tileColors": "", "filename": fname,
               "width": 20, "height": 18, "imageWidth": 160, "imageHeight": 144,
               "autoColor": False}
        json.dump(res, open(os.path.join(bgs, fname + ".gbsres"), "w"), indent=2)

    # --- assets: music + sound
    music_id = u()
    mod_p = os.path.join(project_root, "assets", "music", "demo.mod")
    write_mod(mod_p)
    json.dump({"_resourceType": "music", "id": music_id, "name": "demo",
               "symbol": "song_demo", "settings": {}, "filename": "demo.mod",
               "type": "mod"}, open(os.path.join(project_root, "assets", "music", "demo.mod.gbsres"), "w"), indent=2)

    sound_id = None
    if sample:
        src = os.path.join(sample, "Tronimal_Sound_Effects.sav")
        if os.path.exists(src):
            dst = os.path.join(project_root, "assets", "sounds")
            os.makedirs(dst, exist_ok=True)
            shutil.copy(src, os.path.join(dst, "Tronimal_Sound_Effects.sav"))
            g = os.path.join(sample, "Tronimal_Sound_Effects.sav.gbsres")
            if os.path.exists(g):
                shutil.copy(g, os.path.join(dst, "Tronimal_Sound_Effects.sav.gbsres"))
                sound_id = json.load(open(g))["id"]

    # --- scenes
    proj = os.path.join(project_root, "project")
    def scene_gbsres(rid, name, stype, bg_id, w, h, cx, cy, collisions, script):
        return {"_resourceType": "scene", "id": rid, "_index": 0, "type": stype,
                "name": name, "symbol": f"scene_{slug(name)}", "x": cx, "y": cy,
                "width": w, "height": h, "backgroundId": bg_id, "tilesetId": "",
                "colorModeOverride": "none", "paletteIds": [""] * 6, "spritePaletteIds": [],
                "autoFadeSpeed": 1, "script": script,
                "playerHit1Script": [], "playerHit2Script": [], "playerHit3Script": [],
                "collisions": collisions}

    music_ev = lambda: ev("EVENT_MUSIC_PLAY", {"musicId": music_id, "loop": True})

    meadow = scene_gbsres(meadow_id, "Meadow", "TOPDOWN", meadow_id_bg, 20, 18, 0, 0,
                          collision_string(20, 18, "right", 8),
                          [music_ev()])
    hut = scene_gbsres(hut_id, "Hut", "TOPDOWN", hut_id_bg, 20, 18, 260, 0,
                       collision_string(20, 18, "left", 8),
                       [music_ev()])

    rita_id, bo_id, star_id = u(), u(), u()
    def actor_gbsres(rid, name, sp_id, x, y, direction, script, frame=0, animate=False):
        return {"_resourceType": "actor", "id": rid, "_index": 0, "symbol": f"actor_{slug(name)}",
                "prefabId": "", "name": name, "coordinateType": "tiles", "x": x, "y": y,
                "frame": frame, "animate": animate, "spriteSheetId": sp_id, "paletteId": "",
                "direction": direction, "moveSpeed": 1, "animSpeed": 15,
                "isPinned": False, "persistent": False, "collisionGroup": "",
                "collisionExtraFlags": [], "prefabScriptOverrides": {},
                "script": script, "startScript": [], "updateScript": [],
                "hit1Script": [], "hit2Script": [], "hit3Script": []}

    rita = actor_gbsres(rita_id, "Rita", npc_sprite_id, 5, 5, "down",
        [ev("EVENT_TEXT", {"text": "Hi! I'm Rita.\nThe star is in\nthe hut to the east."})])
    bo = actor_gbsres(bo_id, "Bo", npc_sprite_id, 14, 11, "down",
        [ev("EVENT_TEXT", {"text": "That star over\nthere? Grab it.\nYou're done!"})])
    star_script = [
        ev("EVENT_TEXT", {"text": "A shiny star!\nThat's the whole\ndemo. Nice walk!"}),
        ev("EVENT_SET_VALUE", {"variable": "0", "value": {"type": "true"}}),
    ]
    if sound_id:
        star_script.append(ev("EVENT_SOUND_PLAY_EFFECT",
            {"type": sound_id, "priority": "medium", "pitch": 4, "frequency": 200,
             "duration": 0.5, "wait": True, "effect": 0}))
    star_script.append(ev("EVENT_ACTOR_DEACTIVATE", {"actorId": star_id}))
    star = actor_gbsres(star_id, "Star", star_sprite_id, 11, 4, "down", star_script)

    def trigger_gbsres(rid, name, x, y, w, h, script):
        return {"_resourceType": "trigger", "id": rid, "_index": 0,
                "symbol": f"trigger_{slug(name)}", "prefabId": "", "name": name,
                "x": x, "y": y, "width": w, "height": h,
                "prefabScriptOverrides": {}, "script": script, "leaveScript": []}

    door_east = trigger_gbsres(u(), "Door East", 19, 8, 1, 2, [
        ev("EVENT_SWITCH_SCENE", {"sceneId": hut_id, "x": num(1), "y": num(8),
                                  "direction": "right", "fadeSpeed": "1"})])
    door_west = trigger_gbsres(u(), "Door West", 0, 8, 1, 2, [
        ev("EVENT_SWITCH_SCENE", {"sceneId": meadow_id, "x": num(17), "y": num(8),
                                  "direction": "left", "fadeSpeed": "1"})])

    scenes = [
        ("meadow", meadow,
         {"actors": {"rita": rita}, "triggers": {"door_east": door_east}}),
        ("hut", hut,
         {"actors": {"bo": bo, "star": star}, "triggers": {"door_west": door_west}}),
    ]
    for sname, s, parts in scenes:
        d = os.path.join(proj, "scenes", sname)
        os.makedirs(os.path.join(d, "actors"), exist_ok=True)
        os.makedirs(os.path.join(d, "triggers"), exist_ok=True)
        json.dump(s, open(os.path.join(d, "scene.gbsres"), "w"), indent=2)
        for n, a in parts["actors"].items():
            json.dump(a, open(os.path.join(d, "actors", f"{n}.gbsres"), "w"), indent=2)
        for n, t in parts["triggers"].items():
            json.dump(t, open(os.path.join(d, "triggers", f"{n}.gbsres"), "w"), indent=2)

    # re-save scenes after actor ids settled (already settled) — done above.
    print("[gen] OK — project written")
    print(f"[gen]   scenes: meadow={meadow_id[:8]}…  hut={hut_id[:8]}…")
    print(f"[gen]   player sprite: {player_sprite_id}")
    print(f"[gen]   collisions meadow: {len(meadow['collisions'])} chars, hut: {len(hut['collisions'])} chars")

if __name__ == "__main__":
    main()
