import pyxel

WIDTH = 128
HEIGHT = 128
TILE_SIZE = 8

cursor_x = 0
cursor_y = 0

pyxel.init(WIDTH, HEIGHT, title="PyxelTD")
pyxel.load("my_resource.pyxres")

# ===================== GAME STATES =====================
STATE_MENU = 0
STATE_GAME = 1
game_state = STATE_MENU

BASE_HP = 10
base_hp = BASE_HP
money = 50
wave = 1
max_waves = 10
wave_active = False
wave_timer = 0

# ===================== TILE HELPERS =====================
def is_path(tile): return tile == (1, 0)
def is_grass(tile): return tile == (3, 0)
def is_spawn(tile): return tile == (5, 0)
def is_base(tile): return tile == (7, 0)
def is_tree(tile): return tile == (1, 2)

# ===================== PATHFINDING =====================
def find_path():
    tm = pyxel.tilemaps[0]
    visited = set()
    path = []
    start = None
    goal = None

    for y in range(16):
        for x in range(16):
            if is_spawn(tm.pget(x, y)):
                start = (x, y)
            if is_base(tm.pget(x, y)):
                goal = (x, y)

    if not start or not goal:
        print("❌ ERROR: spawn or base tile missing")
        return []

    def dfs(pos):
        if pos in visited:
            return False
        visited.add(pos)
        path.append(pos)
        if pos == goal:
            return True

        x, y = pos
        for nx, ny in [(x+1,y),(x-1,y),(x,y+1),(x,y-1)]:
            if 0 <= nx < 16 and 0 <= ny < 16:
                tile = tm.pget(nx, ny)
                if is_path(tile) or is_base(tile):
                    if dfs((nx, ny)):
                        return True
        path.pop()
        return False

    dfs(start)
    return path

# ===================== ENEMY =====================
DEFAULT_SPEED_TILES = 1.0
SPAWN_INTERVAL_FRAMES = 60

class Enemy:
    def __init__(self, path, speed_tiles=DEFAULT_SPEED_TILES, hp=5, reward=5):
        self.path = path
        self.index = 0
        tx, ty = self.path[0]
        self.px = tx * TILE_SIZE
        self.py = ty * TILE_SIZE
        self.speed = speed_tiles * TILE_SIZE
        self.alive = True
        self.hp = hp
        self.reward = reward

    def update(self):
        global base_hp, money
        if self.hp <= 0:
            self.alive = False
            money += self.reward
            return

        if self.index >= len(self.path) - 1:
            self.alive = False
            base_hp -= 1
            return

        next_tx, next_ty = self.path[self.index + 1]
        target_x = next_tx * TILE_SIZE
        target_y = next_ty * TILE_SIZE

        dx = target_x - self.px
        dy = target_y - self.py
        dist = (dx * dx + dy * dy) ** 0.5

        dt = 1.0 / 60.0
        step = self.speed * dt

        if dist == 0:
            self.index += 1
            return

        if step >= dist:
            self.px = target_x
            self.py = target_y
            self.index += 1
        else:
            self.px += (dx / dist) * step
            self.py += (dy / dist) * step

    def draw(self):
        pyxel.blt(int(self.px), int(self.py), 0, 5*8, 2*8, TILE_SIZE, TILE_SIZE, 0)

# ===================== PROJECTILE =====================
class Projectile:
    def __init__(self, x, y, target, damage):
        self.x = x
        self.y = y
        self.target = target
        self.damage = damage
        self.speed = 2.5
        self.alive = True

    def update(self):
        if not self.target.alive:
            self.alive = False
            return

        dx = self.target.px - self.x
        dy = self.target.py - self.y
        dist = (dx * dx + dy * dy) ** 0.5

        if dist < 2:
            self.target.hp -= self.damage
            self.alive = False
            return

        self.x += (dx / dist) * self.speed
        self.y += (dy / dist) * self.speed

    def draw(self):
        pyxel.circ(int(self.x), int(self.y), 1, 7)

# ===================== TOWER =====================
class Tower:
    def __init__(self, tx, ty):
        self.tx = tx
        self.ty = ty
        self.level = 1
        self.range = 30
        self.damage = 1
        self.reload_time = 30
        self.timer = 0

    def upgrade(self):
        global money
        if self.level >= 3:
            return
        cost = self.level * 20
        if money >= cost:
            money -= cost
            self.level += 1
            self.damage += 1
            self.range += 5
            self.reload_time = max(10, self.reload_time - 2)

    def sell_value(self):
        total_cost = 20 + 20 * (self.level - 1)
        return total_cost // 2

    def update(self, enemies, projectiles):
        self.timer = max(0, self.timer - 1)
        if self.timer == 0:
            for e in enemies:
                dx = e.px - self.tx * TILE_SIZE
                dy = e.py - self.ty * TILE_SIZE
                if dx*dx + dy*dy <= self.range*self.range:
                    projectiles.append(
                        Projectile(self.tx*TILE_SIZE+4, self.ty*TILE_SIZE+4, e, self.damage)
                    )
                    self.timer = self.reload_time
                    break

    def draw(self):
        color = 10 if self.level == 1 else 9 if self.level == 2 else 12
        pyxel.circ(self.tx*TILE_SIZE+4, self.ty*TILE_SIZE+4, 3, color)

        if cursor_x == self.tx and cursor_y == self.ty:
            pyxel.circb(self.tx*TILE_SIZE+4, self.ty*TILE_SIZE+4, self.range, 5)
            pyxel.text(self.tx*TILE_SIZE, self.ty*TILE_SIZE - 10, f"LV {self.level}/3", 7)
            if self.level < 3:
                pyxel.text(self.tx*TILE_SIZE, self.ty*TILE_SIZE - 18, f"UPG:{self.level*20}", 9)
            else:
                pyxel.text(self.tx*TILE_SIZE, self.ty*TILE_SIZE - 18, "MAX", 8)

# ===================== GAME DATA =====================
enemy_path = find_path()
enemies = []
towers = []
projectiles = []

def start_wave():
    global wave_active, wave_timer, enemies
    wave_active = True
    wave_timer = 0
    enemies = []

# ===================== MENU =====================
def update_menu():
    global game_state
    if pyxel.btnp(pyxel.KEY_RETURN):
        game_state = STATE_GAME
        start_wave()

def draw_menu():
    pyxel.cls(0)
    pyxel.bltm(0, 0, 0, 0, 128, 128, 128)
    pyxel.text(5, 85, "CONTROLS:", 10)
    pyxel.text(5, 95, "ARROWS - MOVE CURSOR", 7)
    pyxel.text(5, 103, "SPACE - BUILD TOWER", 7)
    pyxel.text(5, 111, "U - UPGRADE TOWER", 7)
    pyxel.text(5, 119, "BACKSPACE - SELL TOWER", 7)
    if (pyxel.frame_count // 30) % 2 == 0:
        pyxel.text(38, 55, "PRESS ENTER!", 8)

# ===================== GAME =====================
def update_game():
    global cursor_x, cursor_y, enemies, money, wave, wave_active, wave_timer, projectiles, base_hp

    # movement
    if pyxel.btnp(pyxel.KEY_RIGHT): cursor_x = min(15, cursor_x + 1)
    if pyxel.btnp(pyxel.KEY_LEFT):  cursor_x = max(0, cursor_x - 1)
    if pyxel.btnp(pyxel.KEY_DOWN):  cursor_y = min(15, cursor_y + 1)
    if pyxel.btnp(pyxel.KEY_UP):    cursor_y = max(0, cursor_y - 1)

    # build tower (only if none exists there)
    if pyxel.btnp(pyxel.KEY_SPACE):
        tile = pyxel.tilemaps[0].pget(cursor_x, cursor_y)
        occupied = any(t.tx == cursor_x and t.ty == cursor_y for t in towers)
        if is_grass(tile) and not occupied and money >= 20:
            towers.append(Tower(cursor_x, cursor_y))
            money -= 20

    # upgrade tower
    if pyxel.btnp(pyxel.KEY_U):
        for t in towers:
            if t.tx == cursor_x and t.ty == cursor_y:
                t.upgrade()

    # sell tower
    if pyxel.btnp(pyxel.KEY_BACKSPACE):
        for t in towers:
            if t.tx == cursor_x and t.ty == cursor_y:
                money += t.sell_value()
                towers.remove(t)
                break

    # wave logic
    if wave_active:
        wave_timer += 1

        # spawn enemies
        if wave_timer % SPAWN_INTERVAL_FRAMES == 0 and wave_timer // SPAWN_INTERVAL_FRAMES <= wave * 3:
            enemies.append(Enemy(enemy_path, hp=3+wave, reward=5))

        # update enemies
        for e in enemies:
            e.update()
        enemies[:] = [e for e in enemies if e.alive]

        # auto-start next wave when all enemies dead and done spawning
        if len(enemies) == 0 and wave_timer > SPAWN_INTERVAL_FRAMES * wave * 3:
            wave_active = False
            wave += 1
            money += 10
            if wave <= max_waves:
                start_wave()
    else:
        # update towers and projectiles even between waves
        for t in towers: t.update(enemies, projectiles)
        for p in projectiles: p.update()
        projectiles[:] = [p for p in projectiles if p.alive]
        return

    # update towers and projectiles
    for t in towers: t.update(enemies, projectiles)
    for p in projectiles: p.update()
    projectiles[:] = [p for p in projectiles if p.alive]

def draw_game():
    pyxel.cls(0)
    pyxel.bltm(0, 0, 0, 0, 0, 128, 128)
    pyxel.rectb(cursor_x*TILE_SIZE, cursor_y*TILE_SIZE, TILE_SIZE, TILE_SIZE, 7)

    pyxel.text(2, 2, f"HP:{base_hp}", 8)
    pyxel.text(40, 2, f"${money}", 9)
    pyxel.text(80, 2, f"W:{wave}/{max_waves}", 7)

    for e in enemies: e.draw()
    for t in towers: t.draw()
    for p in projectiles: p.draw()

    if wave > max_waves:
        pyxel.text(40, 60, "YOU WIN!", 10)
    elif base_hp <= 0:
        pyxel.text(40, 60, "GAME OVER!", 8)

# ===================== MAIN LOOP =====================
def update():
    if game_state == STATE_MENU:
        update_menu()
    elif game_state == STATE_GAME:
        update_game()

def draw():
    if game_state == STATE_MENU:
        draw_menu()
    elif game_state == STATE_GAME:
        draw_game()

pyxel.run(update, draw)
