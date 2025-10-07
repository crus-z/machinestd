import pyxel

# =================== CONSTS ===================
WIDTH, HEIGHT, TILE_SIZE = 128, 128, 8
MAP_TILES_W, MAP_TILES_H = 16, 16

# tilemap tile offsets (in tiles)
# Map1 at (0,0), Map2 at (16,0), Custom map at (16,16)
MAP_SRC_TILE_X = [0, 16, 16]
MAP_SRC_TILE_Y = [0, 0, 16]

# game states
STATE_MENU = 0
STATE_MAP_SELECT = 1
STATE_GAME = 2
STATE_PAUSE = 3
STATE_BOSS_CHOICE = 4
STATE_MAP_EDITOR = 5

# spawn / wave
SPAWN_INTERVAL_FRAMES = 60
SPAWN_ROUNDS_PER_WAVE = 3

# tower costs
COST_NORMAL = 20
COST_AOE = 35
COST_DRONE = 50

# ================= GLOBALS ===================
cursor_x = 0
cursor_y = 0
show_info = False

boss_active = False
boss_pending = False

editor_message = ["", ""]
editor_msg_timer = 0

pyxel.init(WIDTH, HEIGHT, title="MachinesTD")
pyxel.load("my_resource.pyxres")

game_state = STATE_MENU
pause_selection = 0
map_selection = 0

BASE_HP = 10
base_hp = BASE_HP
money = 50
wave = 1
max_waves = 10
infinite_mode = False

wave_active = False
wave_timer = 0
spawn_rounds_done = 0

enemy_paths = []
enemies = []
towers = []
projectiles = []

boss_pending = False
boss_active = False

# build selection
selected_tower_type = 0  # 0 normal, 1 aoe, 2 drone

# tower sprite maps (tile coords in image bank)
NORMAL_SPRITES = [(5, 6), (4, 7), (5, 7)]
AOE_SPRITES = [(7, 6), (6, 7), (7, 7)]
DRONE_TOWER_SPRITES = [(5, 4), (4, 5), (5, 5)]
DRONE_SPRITES = [(7, 4), (6, 5), (7, 5)]

# custom map flags
custom_map_exists = False
editor_message_shown = False

# editor cursor & state
editor_selected_tile = (3, 0)  # default grass tile in tileset coordinates

# ================= HELPERS ===================
def is_path(tile): return tile == (1, 0)
def is_grass(tile): return tile == (3, 0)
def is_spawn(tile): return tile == (5, 0)
def is_base(tile): return tile == (7, 0)

# tilemap helpers for custom editor region
def editor_in_area(x, y):
    # x,y are tilemap coords
    return 16 <= x < 32 and 16 <= y < 32

# ================= PATHFINDING =================
def find_paths(map_index=0):
    tm = pyxel.tilemaps[0]
    x_offset = MAP_SRC_TILE_X[map_index]
    y_offset = MAP_SRC_TILE_Y[map_index]
    spawns = []
    goals = []

    # Scan tilemap region for this map
    for y in range(y_offset, y_offset + MAP_TILES_H):
        for x in range(x_offset, x_offset + MAP_TILES_W):
            t = tm.pget(x, y)
            if is_spawn(t):
                spawns.append((x, y))
            if is_base(t):
                goals.append((x, y))

    # if no valid start/goal, return nothing
    if not spawns or not goals:
        return [], [], x_offset, y_offset

    # Depth-first search for pathfinding
    def dfs(start, goal):
        visited = set()
        path = []

        def _dfs(pos):
            if pos in visited:
                return False
            visited.add(pos)
            path.append(pos)
            if pos == goal:
                return True
            x, y = pos
            for nx, ny in [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]:
                if (x_offset <= nx < x_offset + MAP_TILES_W and
                    y_offset <= ny < y_offset + MAP_TILES_H):
                    tile = tm.pget(nx, ny)
                    if is_path(tile) or is_base(tile):
                        if _dfs((nx, ny)):
                            return True
            path.pop()
            return False

        if _dfs(start):
            return path
        return []

    # Build all spawn→base paths
    paths = []
    for s in spawns:
        abs_path = dfs(s, goals[0])
        if abs_path:
            # convert to local (0–15) coordinates
            local = [(x - x_offset, y - y_offset) for x, y in abs_path]
            paths.append(local)

    # ✅ Return everything needed
    return paths, spawns, x_offset, y_offset

# ================= ENEMIES =====================
DEFAULT_SPEED_TILES = 1.0

class Enemy:
    def __init__(self, path, speed_tiles=DEFAULT_SPEED_TILES, hp=5, reward=5, sprite=(5,2)):
        self.path = path
        self.index = 0
        tx, ty = self.path[0]
        self.px = tx * TILE_SIZE
        self.py = ty * TILE_SIZE
        self.speed = speed_tiles * TILE_SIZE
        self.alive = True
        self.hp = hp
        self.reward = reward
        self.sprite = sprite
        self.rewarded = False   # ✅ add this line

    def update(self):
        global base_hp, money
        if self.hp <= 0:
            self.alive = False
            if not self.rewarded:   # ✅ only give once
                money += self.reward
                self.rewarded = True
            return

        if self.index >= len(self.path) - 1:
            self.alive = False
            base_hp -= 1
            return

        nx, ny = self.path[self.index + 1]
        tx = nx * TILE_SIZE
        ty = ny * TILE_SIZE
        dx = tx - self.px
        dy = ty - self.py
        dist = (dx*dx + dy*dy) ** 0.5
        step = (self.speed / 60.0)
        if dist == 0:
            self.index += 1
            return
        if step >= dist:
            self.px = tx; self.py = ty; self.index += 1
        else:
            self.px += (dx/dist) * step
            self.py += (dy/dist) * step

    def draw(self):
        pyxel.blt(int(self.px), int(self.py), 0, self.sprite[0]*8, self.sprite[1]*8, 8, 8, 0)

class FastEnemy(Enemy):
    def __init__(self, path):
        super().__init__(path, speed_tiles=2.0, hp=3, reward=6, sprite=(7,2))

class BossEnemy(Enemy):
    def __init__(self, path):
        super().__init__(path, speed_tiles=0.6, hp=200, reward=100, sprite=(3,4))

# ================= PROJECTILES ==================
class Projectile:
    def __init__(self, x, y, target, damage, speed=2.5, aoe_radius=0):
        self.x = x
        self.y = y
        self.target = target
        self.damage = damage
        self.speed = speed
        self.aoe_radius = aoe_radius
        self.alive = True

    def update(self):
        if not self.target.alive:
            self.alive = False
            return
        tx = self.target.px + TILE_SIZE/2
        ty = self.target.py + TILE_SIZE/2
        dx = tx - self.x
        dy = ty - self.y
        dist = (dx*dx + dy*dy) ** 0.5
        if dist < 3:
            # impact
            if self.aoe_radius > 0:
                for e in enemies:
                    ex = e.px + TILE_SIZE/2
                    ey = e.py + TILE_SIZE/2
                    if (ex - tx)**2 + (ey - ty)**2 <= self.aoe_radius**2:
                        e.hp -= self.damage
            else:
                self.target.hp -= self.damage
            self.alive = False
            return
        if dist != 0:
            self.x += (dx/dist) * self.speed
            self.y += (dy/dist) * self.speed

    def draw(self):
        pyxel.circ(int(self.x), int(self.y), 1, 7)

# ================= DRONE ========================
class Drone:
    def __init__(self, tower):
        # start centered on tower
        self.tower = tower
        self.x = tower.tx * TILE_SIZE + TILE_SIZE//2
        self.y = tower.ty * TILE_SIZE + TILE_SIZE//2
        self.speed = 1.6
        self.reload = 20
        self.timer = 0
        self.target = None

    def update(self):
        # pick nearest target
        best = None
        bestd = 1e9
        for e in enemies:
            if not e.alive: continue
            dx = (e.px + TILE_SIZE/2) - self.x
            dy = (e.py + TILE_SIZE/2) - self.y
            d = dx*dx + dy*dy
            if d < bestd:
                bestd = d; best = e
        self.target = best
        if not self.target:
            # slowly return to tower center
            tx = self.tower.tx * TILE_SIZE + TILE_SIZE//2
            ty = self.tower.ty * TILE_SIZE + TILE_SIZE//2
            dx = tx - self.x; dy = ty - self.y
            dist = (dx*dx + dy*dy)**0.5
            if dist > 0:
                step = min(self.speed, dist)
                self.x += (dx/dist) * step
                self.y += (dy/dist) * step
            return
        tx = self.target.px + TILE_SIZE/2
        ty = self.target.py + TILE_SIZE/2
        dx = tx - self.x; dy = ty - self.y
        dist = (dx*dx + dy*dy)**0.5
        if dist > 0:
            step = self.speed
            if step >= dist:
                self.x = tx; self.y = ty
            else:
                self.x += dx/dist * step; self.y += dy/dist * step
        self.timer = max(0, self.timer - 1)
        if self.timer == 0 and dist < 20:
            self.target.hp -= self.tower.drone_damage
            if self.target.hp <= 0 and not self.target.rewarded:
                self.target.alive = False
                self.target.rewarded = True
                global money
                money += self.target.reward
            self.timer = self.reload

    def draw(self):
        # draw sprite based on tower level
        lvl = max(1, min(3, self.tower.level))
        sx, sy = DRONE_SPRITES[lvl-1]
        px = int(self.x) - 4
        py = int(self.y) - 4
        pyxel.blt(px, py, 0, sx*8, sy*8, 8, 8, 0)

# ================= TOWERS =======================
class BaseTower:
    def __init__(self, tx, ty, map_index):
        self.tx = tx; self.ty = ty; self.map_index = map_index
        self.level = 1

    def upgrade(self):
        global money
        if self.level >= 3: return
        cost = self.level * 20
        if money >= cost:
            money -= cost
            self.level += 1
            self.on_upgrade()

    def on_upgrade(self):
        pass

    def sell_value(self):
        total_cost = 20 + 20 * (self.level - 1)
        return total_cost // 2

    def center_px(self):
        return self.tx * TILE_SIZE + TILE_SIZE//2

    def center_py(self):
        return self.ty * TILE_SIZE + TILE_SIZE//2

    def draw_ui(self):
        cx = self.center_px(); cy = self.center_py()
        pyxel.circb(cx, cy, self.get_ui_range(), 5)
        pyxel.text(self.tx*TILE_SIZE, self.ty*TILE_SIZE - 10, f"LV {self.level}/3", 7)

class NormalTower(BaseTower):
    def __init__(self, tx, ty, map_index):
        super().__init__(tx, ty, map_index)
        self.range = 30
        self.damage = 1
        self.reload = 30
        self.timer = 0

    def on_upgrade(self):
        self.damage += 1
        self.range += 5
        self.reload = max(10, self.reload - 3)

    def update(self, enemies_list, projectiles_list):
        self.timer = max(0, self.timer - 1)
        if self.timer == 0:
            for e in enemies_list:
                dx = (e.px + TILE_SIZE/2) - self.center_px()
                dy = (e.py + TILE_SIZE/2) - self.center_py()
                if dx*dx + dy*dy <= self.range*self.range:
                    projectiles_list.append(Projectile(self.center_px(), self.center_py(), e, self.damage))
                    self.timer = self.reload
                    break

    def draw(self):
        sx, sy = NORMAL_SPRITES[max(0, min(2, self.level-1))]
        px = self.center_px() - 4
        py = self.center_py() - 4
        pyxel.blt(px, py, 0, sx*8, sy*8, 8, 8, 0)
        if cursor_x == self.tx and cursor_y == self.ty and map_selection == self.map_index:
            self.draw_ui()

    def get_ui_range(self):
        return self.range

class AOETower(BaseTower):
    def __init__(self, tx, ty, map_index):
        super().__init__(tx, ty, map_index)
        self.range = 20
        self.splash = 12
        self.damage = 2
        self.reload = 45
        self.timer = 0
        # projectile count: level1=3, level2=4, level3=5
        self.projectile_count = 3

    def on_upgrade(self):
        self.damage += 1
        self.splash += 2
        self.range += 3
        self.reload = max(10, self.reload - 5)
        self.projectile_count = min(5, self.projectile_count + 1)

    def update(self, enemies_list, projectiles_list):
        self.timer = max(0, self.timer - 1)
        if self.timer == 0:
            for e in enemies_list:
                dx = (e.px + TILE_SIZE / 2) - self.center_px()
                dy = (e.py + TILE_SIZE / 2) - self.center_py()
                if dx * dx + dy * dy <= self.range * self.range:
                    n = self.projectile_count
                    # produce simple spread offsets (no trig): use fixed offset patterns
                    offsets = [(-8, -4), (-4, -2), (0, 0), (4, 2), (8, 4)]
                    # center around the enemy position
                    for i in range(n):
                        ox, oy = offsets[i]
                        dummy = type("T", (), {})()
                        dummy.px = e.px + ox
                        dummy.py = e.py + oy
                        dummy.alive = True
                        dummy.hp = 9999
                        projectiles_list.append(Projectile(self.center_px(), self.center_py(), dummy, self.damage, speed=2.5, aoe_radius=self.splash))
                    self.timer = self.reload
                    break

    def draw(self):
        sx, sy = AOE_SPRITES[max(0, min(2, self.level - 1))]
        px = self.center_px() - 4
        py = self.center_py() - 4
        pyxel.blt(px, py, 0, sx * 8, sy * 8, 8, 8, 0)


    def get_ui_range(self):
        return self.range

class DroneTower(BaseTower):
    def __init__(self, tx, ty, map_index):
        super().__init__(tx, ty, map_index)
        self.drone = Drone(self)
        self.drone_damage = 2

    def on_upgrade(self):
        self.drone_damage += 1

    def update(self, enemies_list, projectiles_list):
        if self.drone:
            self.drone.update()

    def draw(self):
        sx, sy = DRONE_TOWER_SPRITES[max(0, min(2, self.level-1))]
        px = self.center_px() - 4
        py = self.center_py() - 4
        pyxel.blt(px, py, 0, sx*8, sy*8, 8, 8, 0)
        if self.drone:
            self.drone.draw()

    def get_ui_range(self):
        return 25

# ================= GAME CONTROL ===================
def start_wave():
    global wave_active, wave_timer, enemies, spawn_rounds_done, boss_pending, boss_active
    wave_active = True
    wave_timer = 0
    enemies.clear()
    spawn_rounds_done = 0
    boss_active = False
    boss_pending = (wave % 10 == 0)

def reset_game():
    global game_state, wave, wave_active, wave_timer, enemies, towers, projectiles, money, base_hp, infinite_mode
    game_state = STATE_MENU
    wave = 1
    wave_active = False
    wave_timer = 0
    enemies.clear()
    towers.clear()
    projectiles.clear()
    money = 50
    base_hp = BASE_HP
    infinite_mode = False

def safe_return_to_menu():
    global game_state, enemies, towers, projectiles, base_hp, money, wave, wave_active
    global wave_timer, spawn_rounds_done, boss_active, boss_pending, infinite_mode, cursor_x, cursor_y

    # clear active entities
    enemies.clear()
    towers.clear()
    projectiles.clear()

    # reset core state
    base_hp = BASE_HP
    money = 50
    wave = 1
    wave_active = False
    wave_timer = 0
    spawn_rounds_done = 0
    boss_active = False
    boss_pending = False
    infinite_mode = False

    cursor_x = 0
    cursor_y = 0

    # back to main menu
    game_state = STATE_MENU


# ================= UI / Menus ===================
def update_menu():
    global game_state
    if pyxel.btnp(pyxel.KEY_RETURN):
        game_state = STATE_MAP_SELECT

def draw_menu():
    pyxel.cls(0)
    pyxel.bltm(0, 0, 0, 0, 16 * 8, 128, 128)

    pyxel.text(20, 15, "MACHINES TOWER DEFENSE", 10)
    pyxel.text(25, 30, "Press ENTER to Start", 7 if (pyxel.frame_count // 30) % 2 == 0 else 1)

    pyxel.text(10, 50, "CONTROLS:", 11)
    pyxel.text(10, 60, "Arrows: Move Cursor", 7)
    pyxel.text(10, 70, "1/2/3: Select Tower", 7)
    pyxel.text(10, 80, "Space: Build", 7)
    pyxel.text(10, 90, "U: Upgrade | Backspace: Sell", 7)
    pyxel.text(10, 100, "P: Pause", 7)
    pyxel.text(10, 110, "I: Tower Info", 7)


def update_map_select():
    global map_selection, game_state, enemy_paths, custom_map_exists, editor_message_shown
    if pyxel.btnp(pyxel.KEY_UP):
        map_selection = (map_selection - 1) % 3
    if pyxel.btnp(pyxel.KEY_DOWN):
        map_selection = (map_selection + 1) % 3
    if pyxel.btnp(pyxel.KEY_RETURN):
        if map_selection < 2:
            game_state = STATE_GAME
            enemy_paths, spawns, map_x_offset, map_y_offset = find_paths(2)
            start_wave()
        else:
            # custom map logic
            if not custom_map_exists:
                game_state = STATE_MAP_EDITOR
            else:
                enemy_paths, spawns, map_x_offset, map_y_offset = find_paths(2)
                if enemy_paths:
                    game_state = STATE_GAME
                    start_wave()
                else:
                    game_state = STATE_MAP_EDITOR
    if pyxel.btnp(pyxel.KEY_D) and custom_map_exists:
        tm = pyxel.tilemaps[0]
        for yy in range(16, 32):
            for xx in range(16, 32):
                tm.pset(xx, yy, (3, 0))
        custom_map_exists = False
    if pyxel.btnp(pyxel.KEY_BACKSPACE):
        game_state = STATE_MENU


def draw_map_select():
    pyxel.cls(0)
    pyxel.text(40, 30, "SELECT MAP", 10)
    blink = (pyxel.frame_count // 15) % 2 == 0
    color1 = 7 if map_selection == 0 and blink else 5
    color2 = 7 if map_selection == 1 and blink else 5
    color3 = 7 if map_selection == 2 and blink else 5

    pyxel.text(40, 60, "Map 1", color1)
    pyxel.text(40, 72, "Map 2", color2)

    if not custom_map_exists:
        pyxel.text(40, 84, "Create Map", color3)
    else:
        pyxel.text(40, 84, "Play Map", color3)
        pyxel.text(40, 96, "Edit Map (E)", 6)
        pyxel.text(40, 108, "Delete Map (D)", 6)

    if pyxel.btnp(pyxel.KEY_E) and custom_map_exists:
        game_state = STATE_MAP_EDITOR

    pyxel.text(10, 120, "Backspace: Return to menu", 5)
    
# ================= PAUSE MENU ===================

def update_pause():
    global game_state, pause_selection

    if pyxel.btnp(pyxel.KEY_UP):
        pause_selection = (pause_selection - 1) % 2
    elif pyxel.btnp(pyxel.KEY_DOWN):
        pause_selection = (pause_selection + 1) % 2

    if pyxel.btnp(pyxel.KEY_RETURN):
        if pause_selection == 0:
            game_state = STATE_GAME
        elif pause_selection == 1:
            safe_return_to_menu()

def draw_pause():
    pyxel.cls(0)
    pyxel.text(45, 40, "PAUSED", 10)
    pyxel.text(36, 70, "Resume", 7 if pause_selection == 0 else 5)
    pyxel.text(36, 80, "Return to Lobby", 7 if pause_selection == 1 else 5)


def update_boss_choice():
    global game_state, infinite_mode, pause_selection, wave
    if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_DOWN):
        pause_selection = 1 - pause_selection
    if pyxel.btnp(pyxel.KEY_RETURN):
        if pause_selection == 0:
            reset_game()
        else:
            infinite_mode = True
            # proceed next wave as usual
            if wave >= max_waves:
                wave += 1
            start_wave()
            game_state = STATE_GAME

def draw_boss_choice():
    pyxel.cls(0)
    pyxel.text(20, 30, "BOSS defeated!", 10)
    pyxel.text(10, 50, "Return to Lobby", 7 if pause_selection == 0 else 5)
    pyxel.text(10, 62, "Play 10 more waves", 7 if pause_selection == 1 else 5)
    pyxel.text(10, 100, "Press ENTER to choose", 5)

# ================= MAP EDITOR ===================
editor_save_message = ""
editor_save_timer = 0

def update_map_select():
    global map_selection, game_state, enemy_paths, custom_map_exists
    global editor_message, editor_msg_timer

    # Move up/down between maps
    if pyxel.btnp(pyxel.KEY_UP):
        map_selection = (map_selection - 1) % 3
    if pyxel.btnp(pyxel.KEY_DOWN):
        map_selection = (map_selection + 1) % 3

    # ENTER = play map
    if pyxel.btnp(pyxel.KEY_RETURN):
        if map_selection < 2:
            game_state = STATE_GAME
            enemy_paths, spawns, map_x_offset, map_y_offset = find_paths(map_selection)
            start_wave()
        else:
            if not custom_map_exists:
                game_state = STATE_MAP_EDITOR
                editor_message = ["Connect portals", "to bases in order to play"]
                editor_msg_timer = 180
            else:
                enemy_paths, spawns, map_x_offset, map_y_offset = find_paths(2)
                if enemy_paths:
                    game_state = STATE_GAME
                    start_wave()
                else:
                    game_state = STATE_MAP_EDITOR
                    editor_message = ["Connect portals", "to bases in order to play"]
                    editor_msg_timer = 180

    # E = Edit custom map (always opens editor)
    if pyxel.btnp(pyxel.KEY_E):
        game_state = STATE_MAP_EDITOR
        editor_message = ["Connect portals", "to bases in order to play"]
        editor_msg_timer = 180

    # D = Delete custom map
    if pyxel.btnp(pyxel.KEY_D) and custom_map_exists:
        tm = pyxel.tilemaps[0]
        for yy in range(16, 32):
            for xx in range(16, 32):
                tm.pset(xx, yy, (3, 0))
        custom_map_exists = False

    # BACKSPACE = Return to menu
    if pyxel.btnp(pyxel.KEY_BACKSPACE):
        game_state = STATE_MENU

def draw_map_editor():
    pyxel.cls(0)
    pyxel.bltm(0, 0, 0, 128, 128, 128, 128)
    pyxel.text(3, 5, "MAP EDITOR (Custom Map)", 10)
    pyxel.text(3,13, "Press P to return and play", 10)
    
    pyxel.text(3, 28, "1 = Grass | 2 = Tree | 3 = Path", 7)
    pyxel.text(3, 36, "4 = Base | 5 = Portal", 7)
    pyxel.rectb(cursor_x*TILE_SIZE, cursor_y*TILE_SIZE, TILE_SIZE, TILE_SIZE, 7)

    tile_names = {(3,0):"Grass",(1,2):"Tree",(1,0):"Path",(7,0):"Base",(5,0):"Portal"}
    name = tile_names.get(editor_selected_tile, "Unknown")
    pyxel.text(5, 118, f"Selected tile: {name}", 7)

    if editor_save_message:
        pyxel.text(40, 100, editor_save_message, 10)

        global editor_msg_timer, editor_message
    if editor_msg_timer > 0:
        x = 40
        y = 50
        pyxel.text(x, y, editor_message[0], 10)
        pyxel.text(x, y + 10, editor_message[1], 10)
        editor_msg_timer -= 1

def update_map_editor():
    global cursor_x, cursor_y, editor_selected_tile, custom_map_exists, game_state
    global editor_save_message, editor_save_timer

    # Move cursor
    if pyxel.btnp(pyxel.KEY_LEFT):
        move_editor_cursor(-1, 0)
    if pyxel.btnp(pyxel.KEY_RIGHT):
        move_editor_cursor(1, 0)
    if pyxel.btnp(pyxel.KEY_UP):
        move_editor_cursor(0, -1)
    if pyxel.btnp(pyxel.KEY_DOWN):
        move_editor_cursor(0, 1)

    # Choose tiles with number keys
    # 1=Grass, 2=Tree, 3=Path, 4=Base, 5=Portal
    if pyxel.btnp(pyxel.KEY_1):
        editor_selected_tile = (3, 0)
    if pyxel.btnp(pyxel.KEY_2):
        editor_selected_tile = (1, 2)
    if pyxel.btnp(pyxel.KEY_3):
        editor_selected_tile = (1, 0)
    if pyxel.btnp(pyxel.KEY_4):
        editor_selected_tile = (7, 0)
    if pyxel.btnp(pyxel.KEY_5):
        editor_selected_tile = (5, 0)

    # Place tile with SPACE
    if pyxel.btnp(pyxel.KEY_SPACE):
        tm = pyxel.tilemaps[0]
        tx = cursor_x + 16
        ty = cursor_y + 16
        tm.pset(tx, ty, editor_selected_tile)
        custom_map_exists = True

    # Save confirmation text (optional visual feedback)
    if editor_save_timer > 0:
        editor_save_timer -= 1
        if editor_save_timer == 0:
            editor_save_message = ""

    # Press P to return to map select
    if pyxel.btnp(pyxel.KEY_P):
        game_state = STATE_MAP_SELECT


def move_editor_cursor(dx, dy):
    global cursor_x, cursor_y
    cursor_x = max(0, min(MAP_TILES_W - 1, cursor_x + dx))
    cursor_y = max(0, min(MAP_TILES_H - 1, cursor_y + dy))

# ================= GAME UPDATE ===================
def update_game():
    global cursor_x, cursor_y, enemies, money, wave, wave_active, wave_timer, projectiles, base_hp
    global spawn_rounds_done, boss_pending, boss_active, selected_tower_type, game_state, pause_selection, infinite_mode

    # ===== Win / Lose handling =====
    if (wave > max_waves and not infinite_mode) or base_hp <= 0:
        if pyxel.btnp(pyxel.KEY_RETURN):
            reset_game()  # Return to menu after win/lose
        return

    if base_hp <= 0:
        if pyxel.btnp(pyxel.KEY_RETURN):
            reset_game()
        return

    if pyxel.btnp(pyxel.KEY_P):
        game_state = STATE_PAUSE
        pause_selection = 0
        return

    # movement
    if pyxel.btnp(pyxel.KEY_RIGHT): cursor_x = min(MAP_TILES_W - 1, cursor_x + 1)
    if pyxel.btnp(pyxel.KEY_LEFT): cursor_x = max(0, cursor_x - 1)
    if pyxel.btnp(pyxel.KEY_DOWN): cursor_y = min(MAP_TILES_H - 1, cursor_y + 1)
    if pyxel.btnp(pyxel.KEY_UP): cursor_y = max(0, cursor_y - 1)

    # tower selection 1/2/3
    if pyxel.btnp(pyxel.KEY_1): selected_tower_type = 0
    if pyxel.btnp(pyxel.KEY_2): selected_tower_type = 1
    if pyxel.btnp(pyxel.KEY_3): selected_tower_type = 2

    # build with SPACE
    if pyxel.btnp(pyxel.KEY_SPACE):
        abs_x = cursor_x + MAP_SRC_TILE_X[map_selection]
        abs_y = cursor_y + MAP_SRC_TILE_Y[map_selection]
        tile = pyxel.tilemaps[0].pget(abs_x, abs_y)
        occupied = any((t.tx == cursor_x and t.ty == cursor_y and t.map_index == map_selection) for t in towers)
        if is_grass(tile) and not occupied:
            cost = [COST_NORMAL, COST_AOE, COST_DRONE][selected_tower_type]
            if money >= cost:
                money -= cost
                if selected_tower_type == 0:
                    towers.append(NormalTower(cursor_x, cursor_y, map_selection))
                elif selected_tower_type == 1:
                    towers.append(AOETower(cursor_x, cursor_y, map_selection))
                elif selected_tower_type == 2:
                    towers.append(DroneTower(cursor_x, cursor_y, map_selection))

    if pyxel.btnp(pyxel.KEY_I):
        global show_info
        show_info = not show_info


    # upgrade
    if pyxel.btnp(pyxel.KEY_U):
        for t in towers:
            if t.tx == cursor_x and t.ty == cursor_y and t.map_index == map_selection:
                t.upgrade()

    # sell
    if pyxel.btnp(pyxel.KEY_BACKSPACE):
        for t in towers:
            if t.tx == cursor_x and t.ty == cursor_y and t.map_index == map_selection:
                money += t.sell_value()
                towers.remove(t)
                break

    # waves/spawning
    if wave_active:
        wave_timer += 1

        if spawn_rounds_done < SPAWN_ROUNDS_PER_WAVE and wave_timer % SPAWN_INTERVAL_FRAMES == 0:
            # === Enemy Spawn Logic ===
            base_spawn = 2
            spawn_count_per_portal = base_spawn + (wave - 1)  # +1 per wave

            # number of fast enemies starts at 2 in wave 2, +1 per wave
            fast_enemy_count = 0
            if wave >= 2:
                fast_enemy_count = 2 + (wave - 2)

            paths, spawns, map_x_offset, map_y_offset = find_paths(map_selection)

            for spawn in spawns:
                sx, sy = spawn
                local_paths = [p for p in paths if p and (p[0][0] + map_x_offset, p[0][1] + map_y_offset) == (sx, sy)]
                path = local_paths[0] if local_paths else (paths[0] if paths else [])

                for k in range(spawn_count_per_portal):
                    if not path:
                        continue
                    if k < fast_enemy_count:
                        e = FastEnemy(path)
                        e.hp = 6 + wave * 2  # stronger fast enemies
                        e.reward = 6 + wave
                        enemies.append(e)
                    else:
                        e = Enemy(path, hp=4 + wave * 2, reward=5 + wave)
                        enemies.append(e)

                    # spawn directly at portal center
                    enemies[-1].px = (sx - map_x_offset) * TILE_SIZE
                    enemies[-1].py = (sy - map_y_offset) * TILE_SIZE

            spawn_rounds_done += 1

        # update enemies
        for e in enemies:
            e.update()
        enemies[:] = [e for e in enemies if e.alive]

        # boss spawn
        # boss spawn (every 10 waves, +1 boss per 10 waves)
        # === Boss spawn logic ===
        if boss_pending and spawn_rounds_done >= SPAWN_ROUNDS_PER_WAVE and len(enemies) == 0 and not boss_active:
            paths, _, _, _ = find_paths(map_selection)
            if paths:
                boss_active = True
                boss_pending = False
                boss_count = max(1, wave // 10)
                for i in range(boss_count):
                    path = paths[i % len(paths)]
                    boss = BossEnemy(path)
                    # Stronger scaling so bosses remain tough
                    boss.hp = 400 + (wave * 70) + ((wave // 10) * 200)
                    boss.reward = 150 + (wave * 15)
                    enemies.append(boss)

        # boss defeated → show infinite/lobby choice (but NO victory message)
        if boss_active and not any(isinstance(e, BossEnemy) and e.alive for e in enemies):
            boss_active = False
            pause_selection = 0
            # Only show boss choice screen if it's a boss wave
            if wave % 10 == 0:
                game_state = STATE_BOSS_CHOICE
            return
        

        # end of wave
        if spawn_rounds_done >= SPAWN_ROUNDS_PER_WAVE and len(enemies) == 0 and not boss_active:
            wave_active = False
            if not infinite_mode and wave >= max_waves:
                return
            else:
                wave += 1
                boss_pending = (wave % 10 == 0)
                money += 10
                start_wave()

    # tower updates
    for t in towers:
        if t.map_index == map_selection:
            t.update(enemies, projectiles)

    # projectile updates
    for p in projectiles:
        p.update()
    projectiles[:] = [p for p in projectiles if p.alive]

# ================= DRAW ==========================
def draw_game():
    pyxel.cls(0)
    # draw appropriate map area
    # bltm params are (x,y,tm,src_x,src_y,width,height) — using tile units for src
    # We'll draw full 128x128 and offset using tilemap src coordinates
    if map_selection == 0:
        pyxel.bltm(0, 0, 0, 0, 0, 128, 128)
    elif map_selection == 1:
        pyxel.bltm(0, 0, 0, 128, 0, 128, 128)
    elif map_selection == 2:
        pyxel.bltm(0, 0, 0, 128, 128, 128, 128)

    # cursor
    pyxel.rectb(cursor_x*TILE_SIZE, cursor_y*TILE_SIZE, TILE_SIZE, TILE_SIZE, 7)

    # draw enemies, towers, projectiles
    for e in enemies: e.draw()
    for t in towers:
        if t.map_index == map_selection: t.draw()
    for p in projectiles: p.draw()

    if show_info:
        for t in towers:
            if t.map_index == map_selection and t.tx == cursor_x and t.ty == cursor_y:
                pyxel.text(5, 95, f"Tower Info:", 10)
                pyxel.text(5, 105, f"Type: {t.__class__.__name__}", 7)
                pyxel.text(5, 115, f"Level: {t.level}", 7)
                if isinstance(t, NormalTower):
                    pyxel.text(95, 105, f"Dmg:{t.damage}", 7)
                    pyxel.text(95, 115, f"Rng:{t.range}", 7)
                elif isinstance(t, AOETower):
                    pyxel.text(70, 105, f"Dmg:{t.damage} Proj:{t.projectile_count}", 7)
                    pyxel.text(70, 115, f"Splash:{t.splash}", 7)
                elif isinstance(t, DroneTower):
                    pyxel.text(95, 105, f"Dmg:{t.drone_damage}", 7)

    if (not infinite_mode) and wave > max_waves and not boss_active:
        pyxel.text(30, 60, "YOU WIN!", 10)
        pyxel.text(10, 70, "Press ENTER to return to menu", 7)
    elif base_hp <= 0:
        pyxel.text(30, 60, "GAME OVER!", 8)
        pyxel.text(10, 70, "Press ENTER to return to menu", 7)

        # HUD
    pyxel.text(2, 2, f"HP:{base_hp}", 8)
    pyxel.text(40, 2, f"${money}", 9)
    if not infinite_mode:
        if wave <= max_waves:
            wave_text = f"W:{wave}/{max_waves}"
        else:
            wave_text = f"W:{wave}"
    else:
         wave_text = f"W:{wave}"
    pyxel.text(80, 2, wave_text, 7)

    names = ["Normal", "AOE", "Drone"]
    pyxel.text(2, 12, f"Sel: {names[selected_tower_type]} (1/2/3)", 7)



def draw():
    if game_state == STATE_MENU:
        draw_menu()
    elif game_state == STATE_MAP_SELECT:
        draw_map_select()
    elif game_state == STATE_GAME:
        draw_game()
    elif game_state == STATE_PAUSE:
        draw_pause()
    elif game_state == STATE_BOSS_CHOICE:
        draw_boss_choice()
    elif game_state == STATE_MAP_EDITOR:
        draw_map_editor()

# ============== main loop helpers for menus (small) ==========
def update():
    if game_state == STATE_MENU:
        update_menu()
    elif game_state == STATE_MAP_SELECT:
        update_map_select()
    elif game_state == STATE_GAME:
        update_game()
    elif game_state == STATE_PAUSE:
        update_pause()
    elif game_state == STATE_BOSS_CHOICE:
        update_boss_choice()
    elif game_state == STATE_MAP_EDITOR:
        update_map_editor()

# initialize
def init_game_start():
    global enemy_paths
    enemy_paths = find_paths(map_selection)
    start_wave()

# run initial setup
enemy_paths = find_paths(map_selection)
start_wave()
pyxel.run(update, draw)