import os

import cv2
import numpy as np

from audio_manager import SoundPlayer
from tracking import BlueTracker


MAX_HP = 3
SUCCESS_POINTS = 25
PERFECT_BASE_POINTS = 50
PERFECT_STREAK_BONUS = 25
PERFECT_ALIGNMENT_PIXELS = 4
RELEASE_ZONE_RATIO = 0.14
GROUND_MARGIN_RATIO = 0.10
BLOCK_WIDTH_RATIO = 0.14
BLOCK_HEIGHT_RATIO = 0.16
BUILDING_FLOORS_PER_STYLE = 10
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 720
BLOCK_SPAWN_X_RATIO = 0.16
BLOCK_SPAWN_TOP_OFFSET = 390
PINCH_MARGIN_PIXELS = 24
MIN_LANDING_OVERLAP_RATIO = 0.45
DROP_GRAVITY = 1.6
DROP_MAX_SPEED = 24.0
TOWER_SCROLL_MARGIN_RATIO = 0.62
CAMERA_SCROLL_STEP_RATIO = 0.035
HEART_SIZE = 34
HEART_MARGIN = 16
HEART_SPACING = 8
SKY_COLOR = (210, 220, 238)
GROUND_HEIGHT_RATIO = 0.13
CLOUD_START_FLOOR = 12
CLOUD_FULL_FLOOR = 24
SPACE_START_FLOOR = 42
SPACE_FULL_FLOOR = 58
HEART_IMAGE_PATHS = (
    "heart.png",
    os.path.join("assets", "heart.png"),
)
BUILDING_CROPPED_DIR = os.path.join("assets", "buildings")
BUILDING_FLOOR_STYLE_NAMES = (
    "blue",
    "red",
    "green",
    "brown",
)
BUILDING_FLOOR_EXTENSIONS = (
    ".jpg",
    ".png",
    ".jpeg",
)

BLOCK_COLORS = [
    (40, 180, 255),
    (80, 220, 130),
    (240, 170, 80),
    (210, 120, 230),
    (90, 210, 230),
]


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def smoothstep(edge0, edge1, value):
    if edge0 == edge1:
        return 1.0 if value >= edge1 else 0.0

    amount = clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return amount * amount * (3.0 - (2.0 * amount))


def blend_frame(base_frame, overlay_frame, alpha):
    if alpha <= 0.0:
        return
    if alpha >= 1.0:
        base_frame[:] = overlay_frame
        return
    cv2.addWeighted(overlay_frame, alpha, base_frame, 1.0 - alpha, 0, base_frame)


def draw_translucent_rect(frame, top_left, bottom_right, color, alpha):
    overlay = frame.copy()
    cv2.rectangle(overlay, top_left, bottom_right, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def ensure_alpha(image):
    if image is None:
        return None

    if image.shape[2] == 4:
        return image

    alpha = np.full(image.shape[:2], 255, dtype=np.uint8)
    return np.dstack((image[:, :, :3], alpha))


def overlay_image(frame, image, x, y, width, height):
    if image is None:
        return False

    resized = cv2.resize(image, (width, height), interpolation=cv2.INTER_NEAREST)
    if resized.shape[2] == 3:
        resized = ensure_alpha(resized)

    height, width = frame.shape[:2]

    x1 = max(0, x)
    y1 = max(0, y)
    x2 = min(width, x + resized.shape[1])
    y2 = min(height, y + resized.shape[0])
    if x1 >= x2 or y1 >= y2:
        return False

    image_x1 = x1 - x
    image_y1 = y1 - y
    image_x2 = image_x1 + (x2 - x1)
    image_y2 = image_y1 + (y2 - y1)
    cropped = resized[image_y1:image_y2, image_x1:image_x2]

    if cropped.shape[2] == 4:
        alpha = cropped[:, :, 3].astype(np.float32) / 255.0
        alpha = alpha[:, :, None]
        color = cropped[:, :, :3].astype(np.float32)
        background = frame[y1:y2, x1:x2].astype(np.float32)
        blended = (color * alpha) + (background * (1.0 - alpha))
        frame[y1:y2, x1:x2] = blended.astype(np.uint8)
    else:
        frame[y1:y2, x1:x2] = cropped[:, :, :3]

    return True


def draw_fallback_heart(frame, x, y, size):
    color = (60, 60, 245)
    outline = (255, 255, 255)
    radius = max(4, size // 5)
    left_center = (x + int(size * 0.36), y + int(size * 0.36))
    right_center = (x + int(size * 0.64), y + int(size * 0.36))
    triangle = np.array([
        [x + int(size * 0.18), y + int(size * 0.42)],
        [x + int(size * 0.82), y + int(size * 0.42)],
        [x + int(size * 0.50), y + int(size * 0.86)],
    ], dtype=np.int32)

    cv2.circle(frame, left_center, radius, color, -1)
    cv2.circle(frame, right_center, radius, color, -1)
    cv2.fillConvexPoly(frame, triangle, color)
    cv2.circle(frame, left_center, radius, outline, 2)
    cv2.circle(frame, right_center, radius, outline, 2)
    cv2.polylines(frame, [triangle], True, outline, 2)


class SkyscraperGame:
    def __init__(self, frame_width, frame_height, best_score=0, sound_player=None):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.best = best_score
        self.sound_player = sound_player
        self.heart_image = self.load_heart_image()
        self.building_sprites = self.load_floor_style_building_sprites()
        self.reset(best_score)

    def load_heart_image(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for relative_path in HEART_IMAGE_PATHS:
            image_path = os.path.join(base_dir, relative_path)
            image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if image is not None:
                return image
        return None

    def load_floor_style_asset(self, style_name, style_index, floor_part):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        candidates = [
            os.path.join(base_dir, BUILDING_CROPPED_DIR, filename)
            for extension in BUILDING_FLOOR_EXTENSIONS
            for filename in (
                f"{style_name}_{floor_part}_floor{extension}",
                f"building_{style_index}_{floor_part}{extension}",
            )
        ]

        for image_path in candidates:
            if not os.path.isfile(image_path):
                continue

            image = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
            if image is not None:
                return ensure_alpha(image)

        return None

    def load_floor_style_building_sprites(self):
        sprites = []

        for style_index, style_name in enumerate(BUILDING_FLOOR_STYLE_NAMES, start=1):
            sprite = {
                part: self.load_floor_style_asset(style_name, style_index, part)
                for part in ("first", "upper")
            }
            if any(image is None for image in sprite.values()):
                return []
            sprites.append(sprite)

        return sprites

    def reset(self, best_score=None):
        if best_score is not None:
            self.best = best_score

        self.tower = []
        self.hp = MAX_HP
        self.score = 0
        self.floors = 0
        self.perfect_streak = 0
        self.last_award_text = ""
        self.camera_scroll = 0
        self.pending_scroll = 0.0
        self.game_over = False
        self.message = "Pinch the building"
        self.active = self.make_block()

    def get_sprite_index_for_floor(self, floor_number):
        if not self.building_sprites:
            return 0

        style_group = max(0, floor_number - 1) // BUILDING_FLOORS_PER_STYLE
        return style_group % len(self.building_sprites)

    def get_sprite_part_for_floor(self, floor_number):
        return "first" if max(0, floor_number - 1) % BUILDING_FLOORS_PER_STYLE == 0 else "upper"

    def get_sprite_image(self, sprite_index=0, sprite_part="upper"):
        if not self.building_sprites:
            return None

        sprite = self.building_sprites[sprite_index % len(self.building_sprites)]
        for part_name in (sprite_part, "upper", "first"):
            if part_name in sprite and sprite[part_name] is not None:
                return sprite[part_name]

        return None

    def get_block_size(self, sprite_index=0, sprite_part="upper"):
        block_width = max(70, int(self.frame_width * BLOCK_WIDTH_RATIO))
        block_height = max(34, int(self.frame_height * BLOCK_HEIGHT_RATIO))

        if self.building_sprites:
            sprite_image = self.get_sprite_image(sprite_index, sprite_part)
            sprite_height, sprite_width = sprite_image.shape[:2]
            block_height = max(34, int(round(block_width * sprite_height / sprite_width)))

        return block_width, block_height

    def get_ground_y(self):
        return int(self.frame_height * (1.0 - GROUND_MARGIN_RATIO))

    def make_block(self):
        next_floor = self.floors + 1
        sprite_index = self.get_sprite_index_for_floor(next_floor)
        sprite_part = self.get_sprite_part_for_floor(next_floor)
        block_width, block_height = self.get_block_size(sprite_index, sprite_part)
        top_block = self.get_top_block()
        if top_block is not None:
            block_width = top_block["w"]

        release_zone_height = int(self.frame_height * RELEASE_ZONE_RATIO)
        center_x = int(self.frame_width * BLOCK_SPAWN_X_RATIO)
        return {
            "x": clamp(center_x - block_width // 2, 0, self.frame_width - block_width),
            "y": release_zone_height + BLOCK_SPAWN_TOP_OFFSET,
            "w": block_width,
            "h": block_height,
            "vy": 0.0,
            "mode": "waiting",
            "color": BLOCK_COLORS[self.floors % len(BLOCK_COLORS)],
            "sprite": sprite_index,
            "sprite_part": sprite_part,
        }

    def point_inside_block(self, point, block, margin=0):
        x, y = point
        return (
            block["x"] - margin <= x <= block["x"] + block["w"] + margin and
            block["y"] - margin <= y <= block["y"] + block["h"] + margin
        )

    def move_active_to_pinch(self, pinch_center):
        self.active["x"] = clamp(
            pinch_center[0] - self.active["w"] // 2,
            0,
            self.frame_width - self.active["w"],
        )
        self.active["y"] = clamp(
            pinch_center[1] - self.active["h"] // 2,
            0,
            self.frame_height - self.active["h"],
        )

    def get_top_block(self):
        return min(self.tower, key=lambda block: block["y"]) if self.tower else None

    def get_landing_target(self):
        top_block = self.get_top_block()

        if top_block is None:
            base_x = (self.frame_width - self.active["w"]) // 2
            return self.get_ground_y() - self.active["h"], base_x, self.active["w"]

        return top_block["y"] - self.active["h"], top_block["x"], top_block["w"]

    def scroll_tower_if_needed(self):
        top_block = self.get_top_block()
        if top_block is None:
            return

        scroll_line = int(self.frame_height * TOWER_SCROLL_MARGIN_RATIO)
        future_top_y = top_block["y"] + self.pending_scroll
        if future_top_y >= scroll_line:
            return

        self.pending_scroll += scroll_line - future_top_y

    def apply_pending_scroll(self):
        if self.pending_scroll <= 0.0:
            return

        step = min(
            self.pending_scroll,
            max(1.0, self.frame_height * CAMERA_SCROLL_STEP_RATIO),
        )
        self.pending_scroll -= step
        self.camera_scroll += step
        for block in self.tower:
            block["y"] += step

        if self.pending_scroll <= 0.01:
            self.pending_scroll = 0.0

        self.tower = [
            block for block in self.tower
            if block["y"] < self.frame_height + block["h"]
        ]

    def add_success_score(self, active_block, target_x):
        perfect = abs(active_block["x"] - target_x) <= PERFECT_ALIGNMENT_PIXELS
        self.floors += 1

        if perfect:
            self.perfect_streak += 1
            points = PERFECT_BASE_POINTS + ((self.perfect_streak - 1) * PERFECT_STREAK_BONUS)
        else:
            self.perfect_streak = 0
            points = SUCCESS_POINTS

        self.last_award_text = f"{'Perfect' if perfect else 'Success'} +{points}"
        self.score += points
        self.best = max(self.best, self.score)
        return perfect, points

    def lose_hp(self):
        if self.sound_player is not None:
            self.sound_player.play_effect("drop")

        self.hp = max(0, self.hp - 1)
        self.perfect_streak = 0
        self.last_award_text = "Block fell! -1 HP"

        if self.hp <= 0:
            self.game_over = True
            self.active = None
            self.message = "No HP left. Press R to restart"
        else:
            self.active = self.make_block()
            self.message = f"Block fell! {self.hp} HP left"

    def land_active_block(self):
        target_y, target_x, target_width = self.get_landing_target()
        self.active["y"] = target_y
        landed_x = self.active["x"]

        overlap = max(
            0,
            min(landed_x + self.active["w"], target_x + target_width) -
            max(landed_x, target_x),
        )
        if overlap < self.active["w"] * MIN_LANDING_OVERLAP_RATIO:
            self.lose_hp()
            return

        perfect = abs(landed_x - target_x) <= PERFECT_ALIGNMENT_PIXELS
        if perfect:
            self.active["x"] = target_x

        placed_block = self.active.copy()
        placed_block.update({
            "mode": "placed",
            "vy": 0.0,
        })
        self.tower.append(placed_block)

        score_block = placed_block.copy()
        score_block["x"] = landed_x
        perfect, _ = self.add_success_score(score_block, target_x)
        if self.sound_player is not None:
            self.sound_player.play_effect("drop-perfect" if perfect else "drop")

        self.scroll_tower_if_needed()
        self.active = self.make_block()
        if perfect:
            self.message = "Perfect! Grab the next block"
        else:
            self.message = "Success! Grab the next block"

    def update(self, pinch_center, two_fingers_detected, pinching):
        self.apply_pending_scroll()

        if self.game_over:
            return

        release_zone_height = int(self.frame_height * RELEASE_ZONE_RATIO)

        if self.active["mode"] == "waiting":
            if (
                two_fingers_detected and
                pinching and
                self.point_inside_block(pinch_center, self.active, PINCH_MARGIN_PIXELS)
            ):
                self.active["mode"] = "held"
                self.message = "Holding. Move to top, then open pinch"
            elif two_fingers_detected:
                self.message = "Pinch the building"
            else:
                self.message = "Show the blue glove"

        elif self.active["mode"] == "held":
            if two_fingers_detected:
                if (not pinching) and pinch_center[1] <= release_zone_height:
                    self.active["mode"] = "falling"
                    self.active["vy"] = 0.0
                    self.message = "Released from the top"
                elif pinch_center[1] <= release_zone_height:
                    self.move_active_to_pinch(pinch_center)
                    self.message = "Open the pinch to release"
                elif pinching:
                    self.move_active_to_pinch(pinch_center)
                    self.message = "Move to the top release zone"
                else:
                    self.message = "Pinch again to keep holding"
            else:
                self.message = "Keep the blue glove visible"

        elif self.active["mode"] == "falling":
            self.active["vy"] = min(self.active["vy"] + DROP_GRAVITY, DROP_MAX_SPEED)
            self.active["y"] += self.active["vy"]

            target_y, _, _ = self.get_landing_target()
            if self.active["y"] >= target_y:
                self.land_active_block()

    def draw_sprite_block(self, frame, block, outline_color):
        x = int(block["x"])
        y = int(block["y"])
        w = int(block["w"])
        h = int(block["h"])
        sprite = self.get_sprite_image(block.get("sprite", 0), block.get("sprite_part", "upper"))

        overlay_image(frame, sprite, x, y, w, h)
        if outline_color != (30, 30, 30):
            cv2.rectangle(frame, (x, y), (x + w, y + h), outline_color, 2)

    def draw_fallback_block(self, frame, block, outline_color):
        x = int(block["x"])
        y = int(block["y"])
        w = int(block["w"])
        h = int(block["h"])

        cv2.rectangle(frame, (x, y), (x + w, y + h), block["color"], -1)
        cv2.rectangle(frame, (x, y), (x + w, y + h), outline_color, 2)

        window_w = max(8, w // 5)
        window_h = max(8, h // 3)
        for i in range(3):
            wx = x + 10 + (i * (window_w + 8))
            wy = y + h // 3
            if wx + window_w < x + w - 6:
                cv2.rectangle(frame, (wx, wy), (wx + window_w, wy + window_h), (245, 245, 245), -1)

    def draw_block(self, frame, block, outline_color=(30, 30, 30)):
        if self.building_sprites:
            self.draw_sprite_block(frame, block, outline_color)
        else:
            self.draw_fallback_block(frame, block, outline_color)

    def draw_background_layer(self, frame, buildings, parallax_speed, repeat_height):
        height, width = frame.shape[:2]
        offset = int((self.camera_scroll * parallax_speed) % repeat_height)

        for repeat_index in range(-1, 3):
            repeat_offset = (repeat_index * repeat_height) - offset
            for x_ratio, y_ratio, w_ratio, h_ratio, color, shadow in buildings:
                x = int(width * x_ratio)
                y = int(height * y_ratio) + repeat_offset
                building_width = int(width * w_ratio)
                building_height = int(height * h_ratio)

                if y > height or y + building_height < -height:
                    continue

                cv2.rectangle(frame, (x, y), (x + building_width, y + building_height), color, -1)
                cv2.rectangle(
                    frame,
                    (x + building_width - max(6, building_width // 8), y),
                    (x + building_width, y + building_height),
                    shadow,
                    -1,
                )

                step = max(34, building_height // 8)
                for row_y in range(y + step, y + building_height - 10, step):
                    cv2.line(frame, (x + 6, row_y), (x + building_width - 8, row_y), shadow, 2)

                if building_width > 55:
                    stripe_x = x + building_width // 2
                    cv2.rectangle(
                        frame,
                        (stripe_x - 3, y),
                        (stripe_x + 4, y + building_height),
                        (199, 209, 238),
                        -1,
                    )

    def draw_city_scene(self, frame):
        frame[:] = SKY_COLOR
        height, width = frame.shape[:2]
        city_exit = smoothstep(8, CLOUD_START_FLOOR, self.floors)
        ground_top = int(height * (1.0 - GROUND_HEIGHT_RATIO) + (height * 0.55 * city_exit))

        far_buildings = [
            (0.02, 0.06, 0.12, 0.86, (193, 198, 189), (152, 158, 138)),
            (0.20, -0.02, 0.08, 0.96, (184, 199, 238), (145, 158, 199)),
            (0.42, 0.00, 0.13, 0.96, (151, 158, 184), (108, 118, 150)),
            (0.62, 0.03, 0.10, 0.88, (196, 203, 180), (150, 158, 130)),
            (0.88, 0.08, 0.10, 0.82, (166, 174, 198), (130, 138, 166)),
        ]
        near_buildings = [
            (0.00, 0.20, 0.05, 0.78, (134, 142, 166), (106, 113, 140)),
            (0.28, 0.18, 0.14, 0.72, (171, 174, 184), (142, 146, 156)),
            (0.39, 0.26, 0.14, 0.64, (135, 145, 172), (98, 108, 139)),
            (0.73, 0.20, 0.14, 0.72, (174, 177, 187), (143, 147, 158)),
            (0.96, 0.30, 0.08, 0.62, (139, 147, 174), (103, 111, 144)),
        ]

        repeat_height = max(240, int(height * 0.82))
        self.draw_background_layer(frame, far_buildings, 0.20, repeat_height)
        self.draw_background_layer(frame, near_buildings, 0.46, repeat_height)

        if ground_top < height:
            self.draw_construction_ground(frame, ground_top)

    def draw_cloud_background(self, frame):
        frame[:] = (236, 242, 251)
        height, width = frame.shape[:2]
        offset = int((self.camera_scroll * 0.26) % max(180, height // 3))

        distant_towers = [
            (0.06, 0.40, 0.10, 0.58, (188, 197, 210), (148, 158, 174)),
            (0.24, 0.18, 0.09, 0.76, (166, 176, 197), (130, 140, 162)),
            (0.44, 0.32, 0.12, 0.65, (183, 190, 203), (144, 153, 168)),
            (0.70, 0.22, 0.10, 0.72, (174, 184, 205), (136, 146, 168)),
            (0.88, 0.42, 0.08, 0.52, (196, 203, 210), (156, 164, 174)),
        ]
        self.draw_background_layer(frame, distant_towers, 0.18, max(260, int(height * 0.78)))

        clouds = [
            (-0.05, 0.18, 150, 34),
            (0.18, 0.38, 210, 44),
            (0.48, 0.23, 190, 38),
            (0.72, 0.51, 230, 48),
            (0.92, 0.30, 170, 35),
        ]
        for repeat_index in range(-1, 3):
            y_shift = repeat_index * (height // 2) - offset
            for x_ratio, y_ratio, cloud_width, cloud_height in clouds:
                x = int(width * x_ratio + ((self.camera_scroll * 0.04) % (width + cloud_width)) * 0.16)
                y = int(height * y_ratio) + y_shift
                self.draw_cloud(frame, x, y, cloud_width, cloud_height)

    def draw_cloud(self, frame, x, y, width, height):
        color = (252, 252, 248)
        shade = (220, 228, 235)
        cv2.ellipse(frame, (x + width // 4, y + height // 2), (width // 4, height // 2), 0, 0, 360, color, -1)
        cv2.ellipse(frame, (x + width // 2, y + height // 3), (width // 3, height // 2), 0, 0, 360, color, -1)
        cv2.ellipse(frame, (x + (width * 3) // 4, y + height // 2), (width // 4, height // 2), 0, 0, 360, color, -1)
        cv2.rectangle(frame, (x + width // 5, y + height // 2), (x + (width * 4) // 5, y + height), color, -1)
        cv2.line(frame, (x + width // 6, y + height), (x + (width * 5) // 6, y + height), shade, 2)

    def draw_space_background(self, frame):
        height, width = frame.shape[:2]
        frame[:] = (34, 28, 58)

        for y in range(height):
            fade = y / max(1, height - 1)
            frame[y, :] = (
                int(28 + (fade * 12)),
                int(24 + (fade * 10)),
                int(52 + (fade * 20)),
            )

        star_offset = int(self.camera_scroll * 0.55)
        for index in range(80):
            x = (index * 137 + 43) % width
            y = (index * 71 + 29 - star_offset) % height
            brightness = 160 + ((index * 37) % 90)
            cv2.circle(frame, (x, y), 1 + (index % 2), (brightness, brightness, brightness), -1)

        moon_x = int(width * 0.78)
        moon_y = int(height * 0.20 + ((self.camera_scroll * 0.08) % 80))
        cv2.circle(frame, (moon_x, moon_y), 44, (215, 218, 210), -1)
        cv2.circle(frame, (moon_x - 16, moon_y - 10), 7, (175, 178, 172), -1)
        cv2.circle(frame, (moon_x + 12, moon_y + 14), 10, (180, 183, 176), -1)

        planet_x = int(width * 0.18)
        planet_y = int(height * 0.46 - ((self.camera_scroll * 0.05) % 110))
        cv2.circle(frame, (planet_x, planet_y), 34, (94, 148, 218), -1)
        cv2.ellipse(frame, (planet_x, planet_y), (58, 12), -12, 0, 360, (210, 184, 126), 3)

        sat_x = int(width * 0.55)
        sat_y = int((height * 0.68 - (self.camera_scroll * 0.16)) % height)
        cv2.rectangle(frame, (sat_x - 16, sat_y - 8), (sat_x + 16, sat_y + 8), (170, 170, 175), -1)
        cv2.rectangle(frame, (sat_x - 48, sat_y - 6), (sat_x - 20, sat_y + 6), (80, 120, 210), -1)
        cv2.rectangle(frame, (sat_x + 20, sat_y - 6), (sat_x + 48, sat_y + 6), (80, 120, 210), -1)
        cv2.line(frame, (sat_x, sat_y + 8), (sat_x + 18, sat_y + 28), (220, 220, 220), 2)

    def draw_city_background(self, frame):
        self.draw_city_scene(frame)

        for start_floor, full_floor, draw_layer in (
            (CLOUD_START_FLOOR, CLOUD_FULL_FLOOR, self.draw_cloud_background),
            (SPACE_START_FLOOR, SPACE_FULL_FLOOR, self.draw_space_background),
        ):
            alpha = smoothstep(start_floor, full_floor, self.floors)
            if alpha > 0.0:
                layer = np.empty_like(frame)
                draw_layer(layer)
                blend_frame(frame, layer, alpha)

    def draw_construction_ground(self, frame, ground_top):
        height, width = frame.shape[:2]
        cv2.rectangle(frame, (0, ground_top), (width, height), (138, 134, 115), -1)
        cv2.rectangle(frame, (0, ground_top), (width, ground_top + 12), (196, 190, 162), -1)

        for x in range(-20, width, 26):
            cv2.line(frame, (x, ground_top + 12), (x + 42, height), (172, 172, 170), 2)
            cv2.line(frame, (x + 42, ground_top + 12), (x, height), (99, 99, 95), 2)

        for x in range(70, width, 150):
            cv2.rectangle(frame, (x, ground_top + 18), (x + 85, ground_top + 48), (180, 180, 182), -1)
            cv2.rectangle(frame, (x + 8, ground_top + 24), (x + 28, ground_top + 42), (95, 58, 52), -1)
            cv2.rectangle(frame, (x + 35, ground_top + 24), (x + 70, ground_top + 42), (210, 210, 215), -1)

        cone_x = width - 70
        cone_y = ground_top + 38
        cv2.fillConvexPoly(
            frame,
            np.array([[cone_x, cone_y + 46], [cone_x + 34, cone_y + 46], [cone_x + 17, cone_y]], dtype=np.int32),
            (60, 150, 240),
        )
        cv2.rectangle(frame, (cone_x + 5, cone_y + 27), (cone_x + 29, cone_y + 35), (255, 255, 255), -1)

    def draw_tower_base(self, frame):
        block_width, block_height = self.get_block_size(0, "first")
        ground_y = self.get_ground_y()
        base_width = int(block_width * 1.18)
        base_height = int(block_height * 0.88)
        base_x = (self.frame_width - base_width) // 2
        base_y = ground_y - base_height

        cv2.rectangle(frame, (base_x - 6, base_y + 8), (base_x + base_width + 10, ground_y + 8), (75, 69, 60), -1)
        cv2.rectangle(frame, (base_x, base_y), (base_x + base_width, ground_y), (214, 204, 172), -1)
        cv2.rectangle(frame, (base_x + 8, base_y + 12), (base_x + base_width - 8, base_y + 22), (245, 239, 220), -1)
        cv2.rectangle(frame, (base_x + 18, base_y + 26), (base_x + base_width - 18, ground_y - 8), (84, 120, 144), -1)
        cv2.rectangle(frame, (base_x + 23, base_y + 31), (base_x + base_width // 2 - 4, ground_y - 12), (170, 205, 230), -1)
        cv2.rectangle(frame, (base_x + base_width // 2 + 4, base_y + 31), (base_x + base_width - 23, ground_y - 12), (170, 205, 230), -1)
        cv2.rectangle(frame, (base_x, base_y), (base_x + base_width, ground_y), (62, 54, 48), 2)

    def draw_hearts(self, frame):
        if self.hp <= 0:
            return

        total_width = (self.hp * HEART_SIZE) + ((self.hp - 1) * HEART_SPACING)
        start_x = self.frame_width - HEART_MARGIN - total_width
        y = self.frame_height - HEART_MARGIN - HEART_SIZE

        for index in range(self.hp):
            x = start_x + index * (HEART_SIZE + HEART_SPACING)

            if overlay_image(frame, self.heart_image, x, y, HEART_SIZE, HEART_SIZE):
                continue

            draw_fallback_heart(frame, x, y, HEART_SIZE)

    def draw_floor_counter(self, frame):
        floor_text = str(max(0, self.floors))
        x = int(self.frame_width * 0.18)
        y = 58
        cv2.putText(frame, floor_text, (x + 3, y + 3), cv2.FONT_HERSHEY_SIMPLEX, 1.25, (20, 30, 80), 3)
        cv2.putText(frame, floor_text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.25, (20, 255, 255), 3)

    def draw_status_hud(self, frame, two_fingers_detected, pinching):
        self.draw_floor_counter(frame)
        self.draw_hearts(frame)

        score_text = f"{self.score:05d}"
        score_x = self.frame_width - 142
        score_y = self.frame_height - 18
        cv2.putText(frame, score_text, (score_x + 2, score_y + 2), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (60, 50, 45), 3)
        cv2.putText(frame, score_text, (score_x, score_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        status_y1 = self.frame_height - 86
        status_y2 = self.frame_height - 56
        draw_translucent_rect(frame, (12, status_y1), (min(self.frame_width - 160, 520), status_y2), (0, 0, 0), 0.38)

        gesture_text = "PINCH" if pinching else "OPEN"
        if not two_fingers_detected:
            gesture_text = "NO GLOVE"
        status_text = f"{self.message}  |  {gesture_text}"
        cv2.putText(frame, status_text, (20, self.frame_height - 64),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        if self.last_award_text:
            award_x = max(20, self.frame_width // 2 - 125)
            cv2.putText(frame, self.last_award_text, (award_x + 2, 86),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (70, 45, 40), 3)
            cv2.putText(frame, self.last_award_text, (award_x, 84),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, (80, 255, 255), 2)

    def draw(self, frame, pinch_center, two_fingers_detected, pinching, fingers):
        self.draw_city_background(frame)
        release_zone_height = int(self.frame_height * RELEASE_ZONE_RATIO)

        draw_translucent_rect(frame, (0, 0), (self.frame_width, release_zone_height), (70, 180, 90), 0.13)
        cv2.line(frame, (0, release_zone_height), (self.frame_width, release_zone_height), (40, 220, 90), 3)
        cv2.putText(frame, "TOP RELEASE ZONE", (20, release_zone_height - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 255, 120), 2)

        if not self.tower:
            self.draw_tower_base(frame)

        for block in self.tower:
            self.draw_block(frame, block)

        if self.active is not None:
            outline = (255, 255, 255) if self.active["mode"] == "held" else (30, 30, 30)
            self.draw_block(frame, self.active, outline)

        for finger in fingers:
            cv2.circle(frame, finger, 9, (255, 0, 0), -1)
            cv2.circle(frame, finger, 14, (255, 255, 255), 2)

        if len(fingers) >= 2:
            line_color = (0, 255, 0) if pinching else (0, 180, 255)
            cv2.line(frame, fingers[0], fingers[1], line_color, 2)

        if two_fingers_detected:
            cursor_color = (0, 255, 0) if pinching else (0, 180, 255)
            cv2.circle(frame, pinch_center, 8, cursor_color, -1)
            cv2.circle(frame, pinch_center, 18, (255, 255, 255), 2)

        self.draw_status_hud(frame, two_fingers_detected, pinching)

        if self.game_over:
            draw_translucent_rect(frame, (0, self.frame_height // 2 - 50),
                                  (self.frame_width, self.frame_height // 2 + 50), (0, 0, 0), 0.55)
            cv2.putText(frame, "GAME OVER", (self.frame_width // 2 - 105, self.frame_height // 2 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 80, 255), 3)
            cv2.putText(frame, "Press R to restart", (self.frame_width // 2 - 125, self.frame_height // 2 + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, WINDOW_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, WINDOW_HEIGHT)
    cv2.namedWindow("Skyscraper", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Skyscraper", WINDOW_WIDTH, WINDOW_HEIGHT)
    cv2.namedWindow("BLUE MASK", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("BLUE MASK", WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)
    sound_player = SoundPlayer()
    sound_player.play_bgm()
    tracker = BlueTracker()
    game = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame = cv2.resize(frame, (WINDOW_WIDTH, WINDOW_HEIGHT), interpolation=cv2.INTER_LINEAR)
        height, width = frame.shape[:2]

        if game is None:
            game = SkyscraperGame(width, height, sound_player=sound_player)

        detection = tracker.detect(frame)
        if detection["contours"]:
            cv2.drawContours(frame, detection["contours"], -1, (255, 0, 0), 2)

        game.update(
            detection["center"],
            detection["two_fingers_detected"],
            detection["pinching"],
        )
        game.draw(
            frame,
            detection["center"],
            detection["two_fingers_detected"],
            detection["pinching"],
            detection["fingers"],
        )

        cv2.imshow("Skyscraper", frame)
        cv2.imshow("BLUE MASK", detection["mask"])

        key = cv2.waitKey(1) & 0xFF
        if key == ord("r"):
            game.reset(game.best)
            tracker.reset()
        if key == ord("q"):
            break

    cap.release()
    sound_player.stop_all()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
