import cv2
import numpy as np


BLUE_HUE_MIN = 90
BLUE_HUE_MAX = 130
BLUE_SATURATION_MIN = 70
BLUE_VALUE_MIN = 50
BLUE_OVER_GREEN_MIN = 20
BLUE_OVER_RED_MIN = 35
MIN_BLUE_AREA = 2500
MAX_BLUE_AREA_RATIO = 0.30
OPEN_KERNEL_SIZE = 5
CLOSE_KERNEL_SIZE = 3
CENTER_SMOOTHING_ALPHA = 0.45
FAST_CENTER_SMOOTHING_ALPHA = 0.80
RADIUS_SMOOTHING_ALPHA = 0.35
CENTER_DEADZONE_PIXELS = 5
FAST_MOVEMENT_PIXELS = 35
MAX_MISSING_FRAMES = 10


def manual_erode(binary_mask, kernel_size):
    """Erosi biner manual memakai operasi array NumPy."""
    binary = binary_mask > 0
    height, width = binary.shape
    pad = kernel_size // 2
    padded = np.pad(binary, pad, mode="constant", constant_values=False)

    result = np.ones((height, width), dtype=bool)
    for y in range(kernel_size):
        for x in range(kernel_size):
            result &= padded[y:y + height, x:x + width]

    return result.astype(np.uint8) * 255


def manual_dilate(binary_mask, kernel_size):
    """Dilasi biner manual memakai operasi array NumPy."""
    binary = binary_mask > 0
    height, width = binary.shape
    pad = kernel_size // 2
    padded = np.pad(binary, pad, mode="constant", constant_values=False)

    result = np.zeros((height, width), dtype=bool)
    for y in range(kernel_size):
        for x in range(kernel_size):
            result |= padded[y:y + height, x:x + width]

    return result.astype(np.uint8) * 255


def manual_opening(binary_mask, kernel_size):
    return manual_dilate(manual_erode(binary_mask, kernel_size), kernel_size)


def manual_closing(binary_mask, kernel_size):
    return manual_erode(manual_dilate(binary_mask, kernel_size), kernel_size)


def create_blue_mask(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv)
    blue, green, red = cv2.split(frame)

    red_i = red.astype(np.int16)
    green_i = green.astype(np.int16)
    blue_i = blue.astype(np.int16)

    # Masking warna biru dari seluruh frame kamera.
    blue_hsv_pixels = (
        (hue >= BLUE_HUE_MIN) &
        (hue <= BLUE_HUE_MAX) &
        (saturation >= BLUE_SATURATION_MIN) &
        (value >= BLUE_VALUE_MIN)
    )
    strong_blue_pixels = (
        ((blue_i - green_i) >= BLUE_OVER_GREEN_MIN) &
        ((blue_i - red_i) >= BLUE_OVER_RED_MIN)
    )
    blue_pixels = blue_hsv_pixels & strong_blue_pixels
    raw_mask = np.where(blue_pixels, 255, 0).astype(np.uint8)

    cleaned_mask = manual_opening(raw_mask, OPEN_KERNEL_SIZE)
    cleaned_mask = manual_closing(cleaned_mask, CLOSE_KERNEL_SIZE)
    return cleaned_mask


def smooth_center(new_center, previous_center):
    if previous_center is None:
        return (float(new_center[0]), float(new_center[1]))

    dx = new_center[0] - previous_center[0]
    dy = new_center[1] - previous_center[1]
    distance = np.hypot(dx, dy)
    if distance < CENTER_DEADZONE_PIXELS:
        return previous_center

    alpha = CENTER_SMOOTHING_ALPHA
    if distance > FAST_MOVEMENT_PIXELS:
        alpha = FAST_CENTER_SMOOTHING_ALPHA

    smooth_x = previous_center[0] + (dx * alpha)
    smooth_y = previous_center[1] + (dy * alpha)
    return (smooth_x, smooth_y)


def smooth_value(new_value, previous_value, alpha):
    if previous_value is None:
        return float(new_value)
    return previous_value + ((new_value - previous_value) * alpha)


class BlueTracker:
    def __init__(self):
        self.stable_center = None
        self.stable_radius = None
        self.missing_frames = 0

    def reset(self):
        self.stable_center = None
        self.stable_radius = None
        self.missing_frames = 0

    def detect(self, frame):
        mask = create_blue_mask(frame)
        height, width = frame.shape[:2]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        result = {
            "detected": False,
            "center": None,
            "radius": 0,
            "contour": None,
            "mask": mask,
        }

        if contours:
            max_blue_area = height * width * MAX_BLUE_AREA_RATIO
            blue_contours = [
                contour for contour in contours
                if MIN_BLUE_AREA < cv2.contourArea(contour) < max_blue_area
            ]

            if blue_contours:
                contour = max(blue_contours, key=cv2.contourArea)
                selected_mask = np.zeros_like(mask)
                cv2.drawContours(selected_mask, [contour], -1, 255, -1)
                mask = np.where((mask > 0) & (selected_mask > 0), 255, 0).astype(np.uint8)

                dist_transform = cv2.distanceTransform(selected_mask, cv2.DIST_L2, 5)
                _, max_val, _, max_loc = cv2.minMaxLoc(dist_transform)

                self.stable_center = smooth_center(max_loc, self.stable_center)
                self.stable_radius = smooth_value(max_val, self.stable_radius, RADIUS_SMOOTHING_ALPHA)
                self.missing_frames = 0

                center = (
                    int(round(self.stable_center[0])),
                    int(round(self.stable_center[1])),
                )

                result.update({
                    "detected": True,
                    "center": center,
                    "radius": int(round(self.stable_radius)),
                    "contour": contour,
                    "mask": mask,
                })
                return result

        self.missing_frames += 1
        if self.missing_frames > MAX_MISSING_FRAMES:
            self.reset()

        return result
