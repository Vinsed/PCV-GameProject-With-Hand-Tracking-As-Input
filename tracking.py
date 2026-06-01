import cv2
import numpy as np


BLUE_HUE_MIN = 90
BLUE_HUE_MAX = 130
BLUE_SATURATION_MIN = 70
BLUE_VALUE_MIN = 50
BLUE_OVER_GREEN_MIN = 20
BLUE_OVER_RED_MIN = 35
MIN_BLUE_AREA = 2500
MAX_BLUE_AREA_RATIO = 0.35
OPEN_KERNEL_SIZE = 5
CLOSE_KERNEL_SIZE = 3
CENTER_SMOOTHING_ALPHA = 0.45
FAST_CENTER_SMOOTHING_ALPHA = 0.80
CENTER_DEADZONE_PIXELS = 5
FAST_MOVEMENT_PIXELS = 35
MAX_MISSING_FRAMES = 10
OPEN_GAP_SCAN_WIDTH_RATIO = 0.68
OPEN_GAP_COLUMN_RATIO = 0.08
OPEN_GAP_MIN_HEIGHT_RATIO = 0.16
OPEN_GAP_MIN_RUN_HEIGHT_RATIO = 0.08
OPEN_GAP_ROW_GAP_FILL_PIXELS = 5
PINCH_FRONT_SCAN_WIDTH_RATIO = 0.38
PINCH_FRONT_BAND_WIDTH_RATIO = 0.12


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


class BlueTracker:
    def __init__(self):
        self.stable_center = None
        self.last_open_gap_offset = None
        self.missing_frames = 0

    def reset(self):
        self.stable_center = None
        self.last_open_gap_offset = None
        self.missing_frames = 0

    def get_contour_center(self, contour, mask):
        selected_mask = np.zeros_like(mask)
        cv2.drawContours(selected_mask, [contour], -1, 255, -1)
        dist_transform = cv2.distanceTransform(selected_mask, cv2.DIST_L2, 5)
        _, _, _, max_loc = cv2.minMaxLoc(dist_transform)
        return max_loc, selected_mask

    def fill_small_false_gaps(self, values, max_gap_size):
        filled = values.copy()
        index = 0

        while index < len(filled):
            if filled[index]:
                index += 1
                continue

            start = index
            while index < len(filled) and not filled[index]:
                index += 1
            end = index

            left_is_filled = start > 0 and filled[start - 1]
            right_is_filled = end < len(filled) and filled[end]
            if left_is_filled and right_is_filled and (end - start) <= max_gap_size:
                filled[start:end] = True

        return filled

    def get_true_runs(self, values, min_run_size):
        runs = []
        index = 0

        while index < len(values):
            if not values[index]:
                index += 1
                continue

            start = index
            while index < len(values) and values[index]:
                index += 1
            end = index

            if (end - start) >= min_run_size:
                runs.append((start, end))

        return runs

    def get_open_gap_points(self, selected_mask, contour):
        x, y, width, height = cv2.boundingRect(contour)
        scan_width = max(1, int(width * OPEN_GAP_SCAN_WIDTH_RATIO))
        region = selected_mask[y:y + height, x:x + scan_width] > 0

        if region.size == 0:
            return []

        min_run_height = max(5, int(height * OPEN_GAP_MIN_RUN_HEIGHT_RATIO))
        min_gap_height = max(10, int(height * OPEN_GAP_MIN_HEIGHT_RATIO))
        min_gap_columns = max(5, int(scan_width * OPEN_GAP_COLUMN_RATIO))
        gap_points = []

        for column_index in range(region.shape[1]):
            column = self.fill_small_false_gaps(
                region[:, column_index],
                OPEN_GAP_ROW_GAP_FILL_PIXELS,
            )
            runs = self.get_true_runs(column, min_run_height)

            if len(runs) < 2:
                continue

            best_gap = 0
            best_gap_center = None
            for run_index in range(len(runs) - 1):
                gap_start = runs[run_index][1]
                gap_end = runs[run_index + 1][0]
                gap_height = gap_end - gap_start
                gap_center = (gap_start + gap_end) / 2.0

                if gap_height > best_gap:
                    best_gap = gap_height
                    best_gap_center = gap_center

            if best_gap_center is None:
                continue

            in_middle_band = (height * 0.18) <= best_gap_center <= (height * 0.82)
            if best_gap >= min_gap_height and in_middle_band:
                gap_points.append((x + column_index, y + int(round(best_gap_center))))

        if len(gap_points) < min_gap_columns:
            return []

        return gap_points

    def get_front_pinch_point(self, selected_mask, contour, fallback_center):
        x, y, width, height = cv2.boundingRect(contour)
        scan_width = max(1, int(width * PINCH_FRONT_SCAN_WIDTH_RATIO))
        region = selected_mask[y:y + height, x:x + scan_width] > 0

        if region.size == 0:
            return fallback_center

        filled_columns = np.where(np.any(region, axis=0))[0]
        if len(filled_columns) == 0:
            return fallback_center

        front_column = int(filled_columns[0])
        band_width = max(4, int(width * PINCH_FRONT_BAND_WIDTH_RATIO))
        band_end = min(region.shape[1], front_column + band_width)
        band = region[:, front_column:band_end]
        rows, cols = np.where(band)

        if len(rows) == 0:
            return fallback_center

        return (
            float(x + front_column + np.mean(cols)),
            float(y + np.mean(rows)),
        )

    def detect(self, frame):
        mask = create_blue_mask(frame)
        height, width = frame.shape[:2]
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        result = {
            "center": None,
            "contours": [],
            "fingers": [],
            "two_fingers_detected": False,
            "pinching": False,
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
                palm_center, selected_mask = self.get_contour_center(contour, mask)
                mask = np.where((mask > 0) & (selected_mask > 0), 255, 0).astype(np.uint8)
                self.missing_frames = 0

                gap_points = self.get_open_gap_points(selected_mask, contour)
                open_gesture = len(gap_points) > 0
                if open_gesture:
                    raw_center = (
                        float(np.mean([point[0] for point in gap_points])),
                        float(np.mean([point[1] for point in gap_points])),
                    )
                    x, y, width, height = cv2.boundingRect(contour)
                    self.last_open_gap_offset = (
                        (raw_center[0] - x) / max(1, width),
                        (raw_center[1] - y) / max(1, height),
                    )
                    gesture_points = [gap_points[0], gap_points[-1]]
                elif self.last_open_gap_offset is not None:
                    x, y, width, height = cv2.boundingRect(contour)
                    raw_center = (
                        float(x + self.last_open_gap_offset[0] * width),
                        float(y + self.last_open_gap_offset[1] * height),
                    )
                    gesture_points = [(int(round(raw_center[0])), int(round(raw_center[1])))]
                else:
                    raw_center = self.get_front_pinch_point(selected_mask, contour, palm_center)
                    gesture_points = [(int(round(raw_center[0])), int(round(raw_center[1])))]

                self.stable_center = smooth_center(raw_center, self.stable_center)
                center = (
                    int(round(self.stable_center[0])),
                    int(round(self.stable_center[1])),
                )

                pinching = not open_gesture

                result.update({
                    "center": center,
                    "contours": [contour],
                    "fingers": gesture_points,
                    "two_fingers_detected": True,
                    "pinching": pinching,
                    "mask": mask,
                })
                return result

        self.missing_frames += 1
        if self.missing_frames > MAX_MISSING_FRAMES:
            self.reset()

        return result
