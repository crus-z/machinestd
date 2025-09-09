import pyxel

WIDTH = 128
HEIGHT = 128
TILE_SIZE = 8

cursor_x = 0
cursor_y = 0

pyxel.init(WIDTH, HEIGHT, title="Tower Defense")
pyxel.load("tdgame.pyxres")

def is_path(tile):
    return tile == (1, 0)

def is_grass(tile):
    return tile == (3, 0)

def is_spawn(tile):
    return tile == (5, 0)

def is_base(tile):
    return tile == (7, 0)

def update():
    global cursor_x, cursor_y

    if pyxel.btnp(pyxel.KEY_RIGHT):
        cursor_x = min(15, cursor_x + 1)
    if pyxel.btnp(pyxel.KEY_LEFT):
        cursor_x = max(0, cursor_x - 1)
    if pyxel.btnp(pyxel.KEY_DOWN):
        cursor_y = min(15, cursor_y + 1)
    if pyxel.btnp(pyxel.KEY_UP):
        cursor_y = max(0, cursor_y - 1)

    pass

def draw():
    pyxel.cls(0)
    pyxel.bltm(0, 0, 0, 0, 0, 16, 16)

    pyxel.rectb(cursor_x * TILE_SIZE, cursor_y * TILE_SIZE, TILE_SIZE, TILE_SIZE, 7)
    tile = pyxel.tilemaps[0].pget(cursor_x, cursor_y)

    
    text = "?"
    if is_grass(tile):
        text = "grass"
    elif is_path(tile):
        text = "path"
    elif is_spawn(tile):
        text = "spawn"
    elif is_base(tile):
        text = "base"

    pyxel.text(5, 5, f"Tile: {text}", 7)

pyxel.run(update, draw)