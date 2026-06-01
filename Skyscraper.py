import cv2

from tracking import BlueTracker


RELEASE_ZONE_RATIO = 0.18
GROUND_MARGIN_RATIO = 0.10
BLOCK_WIDTH_RATIO = 0.16
BLOCK_HEIGHT_RATIO = 0.08
PINCH_MARGIN_PIXELS = 24
MIN_LANDING_OVERLAP_RATIO = 0.45
DROP_GRAVITY = 1.6
DROP_MAX_SPEED = 24.0
TOWER_SCROLL_MARGIN_RATIO = 0.38

BLOCK_COLORS = [
    (40, 180, 255),
    (80, 220, 130),
    (240, 170, 80),
    (210, 120, 230),
    (90, 210, 230),
]


def clamp(value, min_value, max_value):
    return max(min_value, min(value, max_value))


def draw_translucent_rect(frame, top_left, bottom_right, color, alpha):
    overlay = frame.copy()
    cv2.rectangle(overlay, top_left, bottom_right, color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


class SkyscraperGame:
    def __init__(self, frame_width, frame_height, best_score=0):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.best = best_score
        self.reset(best_score)

    def reset(self, best_score=None):
        if best_score is not None:
            self.best = best_score

        self.tower = []
        self.score = 0
        self.game_over = False
        self.message = "Touch the block with the blue marker"
        self.active = self.make_block()

    def get_block_size(self):
        block_width = max(70, int(self.frame_width * BLOCK_WIDTH_RATIO))
        block_height = max(34, int(self.frame_height * BLOCK_HEIGHT_RATIO))
        return block_width, block_height

    def get_ground_y(self):
        return int(self.frame_height * (1.0 - GROUND_MARGIN_RATIO))

    def make_block(self):
        block_width, block_height = self.get_block_size()
        ground_y = self.get_ground_y()
        return {
            "x": int(self.frame_width * 0.07),
            "y": ground_y - block_height - 8,
            "w": block_width,
            "h": block_height,
            "vy": 0.0,
            "mode": "waiting",
            "color": BLOCK_COLORS[self.score % len(BLOCK_COLORS)],
        }

    def point_inside_block(self, point, block, margin=0):
        x, y = point
        return (
            block["x"] - margin <= x <= block["x"] + block["w"] + margin and
            block["y"] - margin <= y <= block["y"] + block["h"] + margin
        )

    def get_top_block(self):
        if not self.tower:
            return None
        return min(self.tower, key=lambda block: block["y"])

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
        if top_block["y"] >= scroll_line:
            return

        distance = scroll_line - top_block["y"]
        for block in self.tower:
            block["y"] += distance

        self.tower = [
            block for block in self.tower
            if block["y"] < self.frame_height + block["h"]
        ]

    def update(self, blue_center, blue_detected):
        if self.game_over:
            return

        release_zone_height = int(self.frame_height * RELEASE_ZONE_RATIO)

        if self.active["mode"] == "waiting":
            if blue_detected and self.point_inside_block(blue_center, self.active, PINCH_MARGIN_PIXELS):
                self.active["mode"] = "held"
                self.message = "Pinched. Move to the top release zone"
            else:
                self.message = "Touch the block with the blue marker"

        elif self.active["mode"] == "held":
            if blue_detected:
                self.active["x"] = clamp(
                    blue_center[0] - self.active["w"] // 2,
                    0,
                    self.frame_width - self.active["w"],
                )
                self.active["y"] = clamp(
                    blue_center[1] - self.active["h"] // 2,
                    0,
                    self.frame_height - self.active["h"],
                )

                if blue_center[1] <= release_zone_height:
                    self.active["mode"] = "falling"
                    self.active["vy"] = 0.0
                    self.message = "Released from the top"
            else:
                self.message = "Keep the blue marker visible"

        elif self.active["mode"] == "falling":
            self.active["vy"] = min(self.active["vy"] + DROP_GRAVITY, DROP_MAX_SPEED)
            self.active["y"] += self.active["vy"]

            target_y, target_x, target_width = self.get_landing_target()
            if self.active["y"] >= target_y:
                self.active["y"] = target_y
                overlap = self.horizontal_overlap(
                    self.active["x"],
                    self.active["w"],
                    target_x,
                    target_width,
                )

                if overlap >= self.active["w"] * MIN_LANDING_OVERLAP_RATIO:
                    placed_block = self.active.copy()
                    placed_block["mode"] = "placed"
                    self.tower.append(placed_block)
                    self.score += 1
                    self.best = max(self.best, self.score)
                    self.scroll_tower_if_needed()
                    self.active = self.make_block()
                    self.message = "Stacked. Grab the next block"
                else:
                    self.game_over = True
                    self.message = "Game over. Press R to restart"

    def draw_block(self, frame, block, outline_color=(30, 30, 30)):
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

    def draw(self, frame, blue_center, blue_detected):
        release_zone_height = int(self.frame_height * RELEASE_ZONE_RATIO)
        ground_y = self.get_ground_y()
        block_width, _ = self.get_block_size()

        draw_translucent_rect(frame, (0, 0), (self.frame_width, release_zone_height), (40, 170, 70), 0.22)
        cv2.line(frame, (0, release_zone_height), (self.frame_width, release_zone_height), (40, 220, 90), 3)
        cv2.putText(frame, "TOP RELEASE ZONE", (20, release_zone_height - 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 255, 120), 2)

        base_x = (self.frame_width - block_width) // 2
        cv2.rectangle(frame, (base_x, ground_y), (base_x + block_width, ground_y + 12), (70, 70, 70), -1)

        for block in self.tower:
            self.draw_block(frame, block)

        if self.active is not None:
            outline = (255, 255, 255) if self.active["mode"] == "held" else (30, 30, 30)
            self.draw_block(frame, self.active, outline)

        if blue_detected:
            cv2.circle(frame, blue_center, 9, (255, 0, 0), -1)
            cv2.circle(frame, blue_center, 16, (255, 255, 255), 2)

        cv2.putText(frame, f"Height: {self.score}  Best: {self.best}", (20, self.frame_height - 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, (255, 255, 255), 2)
        cv2.putText(frame, self.message, (20, self.frame_height - 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)

        if self.game_over:
            draw_translucent_rect(frame, (0, self.frame_height // 2 - 50),
                                  (self.frame_width, self.frame_height // 2 + 50), (0, 0, 0), 0.55)
            cv2.putText(frame, "GAME OVER", (self.frame_width // 2 - 105, self.frame_height // 2 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 80, 255), 3)
            cv2.putText(frame, "Press R to restart", (self.frame_width // 2 - 125, self.frame_height // 2 + 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    @staticmethod
    def horizontal_overlap(x1, w1, x2, w2):
        left = max(x1, x2)
        right = min(x1 + w1, x2 + w2)
        return max(0, right - left)


def main():
    cap = cv2.VideoCapture(0)
    tracker = BlueTracker()
    game = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        height, width = frame.shape[:2]

        if game is None:
            game = SkyscraperGame(width, height)

        detection = tracker.detect(frame)
        if detection["detected"]:
            cv2.drawContours(frame, [detection["contour"]], -1, (255, 0, 0), 2)
            cv2.circle(
                frame,
                detection["center"],
                max(10, detection["radius"]),
                (0, 255, 0),
                2,
            )

        game.update(detection["center"], detection["detected"])
        game.draw(frame, detection["center"], detection["detected"])

        cv2.imshow("Skyscraper", frame)
        cv2.imshow("BLUE MASK", detection["mask"])

        key = cv2.waitKey(1) & 0xFF
        if key == ord("r"):
            game.reset(game.best)
            tracker.reset()
        if key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
