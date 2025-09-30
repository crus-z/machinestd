import pyxel

WIDTH = 128
HEIGHT = 128
TILE_SIZE = 8

cursor_x = 0
cursor_y = 0

pyxel.init(WIDTH, HEIGHT, title="PyxelTD")
pyxel.load("my_resource.pyxres")

BASE_HP = 10
base_hp = BASE_HP
money = 50   # dinheiro inicial
wave = 1
max_waves = 10
wave_active = False
wave_timer = 0

# map helpers
def is_path(tile):
    return tile == (1, 0)

def is_grass(tile):
    return tile == (3, 0)

def is_spawn(tile):
    return tile == (5, 0)

def is_base(tile):
    return tile == (7, 0)

def is_tree(tile):
    return tile == (1, 2)


# enemies speed
DEFAULT_SPEED_TILES = 1.0   # tile/sec
SPAWN_INTERVAL_FRAMES = 60  # frames/spawn

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
        pyxel.rect(int(self.px), int(self.py), TILE_SIZE, TILE_SIZE, 8)


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
        cost = self.level * 20
        global money
        if money >= cost:
            money -= cost
            self.level += 1
            self.damage += 1
            self.range += 5
            self.reload_time = max(10, self.reload_time - 2)

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
        # cor varia com o level
        color = 10 if self.level == 1 else 11 if self.level == 2 else 12
        pyxel.circ(self.tx * TILE_SIZE + 4, self.ty * TILE_SIZE + 4, 3, color)

        # mostra o range se o cursor estiver em cima
        if cursor_x == self.tx and cursor_y == self.ty:
            pyxel.circb(self.tx * TILE_SIZE + 4, self.ty * TILE_SIZE + 4, self.range, 5)


# Caminho dos inimigos
enemy_path = [
    (0, 1), (1, 1), (2, 1), (3, 1),
    (3, 2), (3, 3), (2, 3), (1, 3),
    (1, 2), (1, 1),
    (2, 1), (3, 1), (4, 1), (5, 1), (6, 1)
]

enemies = []
towers = []
projectiles = []
frame_count = 0


def start_wave():
    global wave_active, wave_timer, enemies
    if not wave_active:
        wave_active = True
        wave_timer = 0
        enemies = []


def update():
    global cursor_x, cursor_y, frame_count, enemies, money, wave, wave_active, wave_timer, projectiles

    if pyxel.btnp(pyxel.KEY_RIGHT):
        cursor_x = min(15, cursor_x + 1)
    if pyxel.btnp(pyxel.KEY_LEFT):
        cursor_x = max(0, cursor_x - 1)
    if pyxel.btnp(pyxel.KEY_DOWN):
        cursor_y = min(15, cursor_y + 1)
    if pyxel.btnp(pyxel.KEY_UP):
        cursor_y = max(0, cursor_y - 1)

    # Construir torre
    if pyxel.btnp(pyxel.KEY_SPACE):
        tile = pyxel.tilemaps[0].pget(cursor_x, cursor_y)
        if is_grass(tile) and money >= 20:
            towers.append(Tower(cursor_x, cursor_y))
            money -= 20

    # Upgrade torre
    if pyxel.btnp(pyxel.KEY_U):
        for t in towers:
            if t.tx == cursor_x and t.ty == cursor_y:
                t.upgrade()

    # Pular wave
    if pyxel.btnp(pyxel.KEY_RETURN):
        start_wave()

    # Gerenciar waves
    if wave_active:
        wave_timer += 1
        if wave_timer % SPAWN_INTERVAL_FRAMES == 0 and wave_timer // SPAWN_INTERVAL_FRAMES <= wave * 3:
            enemies.append(Enemy(enemy_path, hp=3+wave, reward=5))
        if len(enemies) == 0 and wave_timer > SPAWN_INTERVAL_FRAMES * wave * 3:
            wave_active = False
            wave += 1
            money += 10  # recompensa por wave

    # Atualizar inimigos
    for e in enemies:
        e.update()
    enemies = [e for e in enemies if e.alive]

    # Atualizar torres
    for t in towers:
        t.update(enemies, projectiles)

    # Atualizar projéteis
    for p in projectiles:
        p.update()
    projectiles = [p for p in projectiles if p.alive]


def draw():
    pyxel.cls(0)
    pyxel.bltm(0, 0, 0, 0, 0, 128, 128)

    pyxel.rectb(cursor_x * TILE_SIZE, cursor_y * TILE_SIZE, TILE_SIZE, TILE_SIZE, 7)

    pyxel.text(5, 5, f"HP: {base_hp}", 8)
    pyxel.text(5, 15, f"Money: {money}", 9)
    pyxel.text(5, 25, f"Wave: {wave}/{max_waves}", 7)
    pyxel.text(5, 35, "SPACE=build  U=upgrade", 6)
    pyxel.text(5, 45, "ENTER=skip wave", 6)

    for e in enemies:
        e.draw()
    for t in towers:
        t.draw()
    for p in projectiles:
        p.draw()

    if wave > max_waves:
        pyxel.text(40, 60, "YOU WIN!", 10)
    elif base_hp <= 0:
        pyxel.text(40, 60, "GAME OVER!", 8)


pyxel.run(update, draw)
