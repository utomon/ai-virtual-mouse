import cv2
import mediapipe as mp
import pyautogui
import util
import time

# --- Global state ---
screen_width, screen_height = pyautogui.size()
current_mode = "mouse"  # Modes: mouse, drag

# Cooldowns
last_left_click_time = 0
last_right_click_time = 0
click_cooldown = 0.5
left_click_cooldown = 0.3
mode_switch_cooldown = 1.0
last_mode_switch_time = 0
mode_lock_time = 0
mode_lock_duration = 0.5

# Double click
double_click_threshold = 0.5
left_click_count = 0
left_click_pending = False
pending_click_time = 0

# Drag
dragging = False
drag_start_time = 0
last_cursor_pos = (0, 0)

# Smoothing
smooth_pos = pyautogui.position()
alpha = 0.7
move_threshold = 3
last_move_time = 0
move_update_delay = 0.01

# Finger state tracking
prev_index_up = True
prev_middle_up = True

mphands = mp.solutions.hands
hands = mphands.Hands(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5,
    max_num_hands=1,
)

def fingers_extended(landmarks):
    def is_up(tip, pip): return landmarks[tip][1] < landmarks[pip][1]
    index = is_up(8, 6)
    middle = is_up(12, 10)
    ring = is_up(16, 14)
    pinky = is_up(20, 18)
    thumb = landmarks[4][0] < landmarks[3][0]
    return index, middle, ring, pinky, thumb

def detect_gestures(frame, landmarks, control_w, control_h, offset_x, offset_y, x_scale, y_scale):
    global last_left_click_time, last_right_click_time
    global left_click_count, left_click_pending, pending_click_time
    global screen_width, screen_height, dragging, current_mode, last_mode_switch_time, mode_lock_time
    global drag_start_time, last_cursor_pos, smooth_pos, last_move_time
    global prev_index_up, prev_middle_up

    h, w, _ = frame.shape
    to_px = lambda lm: (int(lm[0]*w), int(lm[1]*h))

    index_tip = to_px(landmarks[8])
    index_pip = to_px(landmarks[6])
    middle_tip = to_px(landmarks[12])
    middle_pip = to_px(landmarks[10])
    thumb_tip = to_px(landmarks[4])

    index_up, middle_up, ring_up, pinky_up, thumb_up = fingers_extended(landmarks)
    current_time = time.time()

    # --- Mode toggle gesture ---
    if current_time - last_mode_switch_time > mode_switch_cooldown:
        if index_up and middle_up and ring_up and not pinky_up:
            if current_mode != "drag":
                print("Switched to DRAG mode")
                current_mode = "drag"
                last_mode_switch_time = current_time
                mode_lock_time = current_time
        elif index_up and middle_up and not ring_up and not pinky_up:
            if current_mode != "mouse":
                print("Switched to MOUSE mode")
                current_mode = "mouse"
                last_mode_switch_time = current_time
                mode_lock_time = current_time
                if dragging:
                    pyautogui.mouseUp()
                    dragging = False

    if current_time - mode_lock_time < mode_lock_duration:
        return

    # --- Auto screen resize ---
    screen_width, screen_height = pyautogui.size()

    # --- Cursor control ---
    if current_mode == "mouse" and not thumb_up:
        rel_x = max(0, min(index_tip[0] - offset_x, control_w))
        rel_y = max(0, min(index_tip[1] - offset_y, control_h))
        target_x = int(rel_x * x_scale)
        target_y = int(rel_y * y_scale)

        new_x = int(alpha * smooth_pos[0] + (1 - alpha) * target_x)
        new_y = int(alpha * smooth_pos[1] + (1 - alpha) * target_y)
        smooth_pos = (new_x, new_y)

        if (abs(new_x - pyautogui.position().x) > move_threshold or
            abs(new_y - pyautogui.position().y) > move_threshold) and \
                (current_time - last_move_time > move_update_delay):
            pyautogui.moveTo(new_x, new_y)
            last_move_time = current_time

        cv2.putText(frame, "Mouse Mode", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,255,0), 2)

    elif current_mode == "drag":
        if not dragging:
            drag_start_time = current_time
            last_cursor_pos = pyautogui.position()
            dragging = True

        if current_time - drag_start_time > 0.3:
            pyautogui.mouseDown()
            pyautogui.moveTo(index_tip[0] * x_scale, index_tip[1] * y_scale)
            cv2.putText(frame, "Drag Mode", (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255,0,0), 2)
    else:
        if dragging:
            pyautogui.mouseUp()
            dragging = False

    # --- Left/Right Clicks ---
    if current_mode == "mouse":
        # Left Click (index down event)
        if not index_up and prev_index_up and (current_time - last_left_click_time > left_click_cooldown):
            if current_time - last_left_click_time < double_click_threshold:
                left_click_count += 1
            else:
                left_click_count = 1
            last_left_click_time = current_time

            if left_click_count == 2:
                pyautogui.click(button='left', clicks=2, interval=0.1)
                print("Double Click")
                left_click_count = 0
                left_click_pending = False
            else:
                left_click_pending = True
                pending_click_time = current_time

        # Finalize single click if second click never came
        if left_click_pending and (current_time - pending_click_time > double_click_threshold):
            pyautogui.click(button='left')
            print("Left Click")
            left_click_pending = False
            left_click_count = 0

        # Right Click (middle finger down event)
        if not middle_up and prev_middle_up and (current_time - last_right_click_time > click_cooldown):
            pyautogui.click(button='right')
            print("Right Click")
            last_right_click_time = current_time

    # --- Update previous finger states ---
    prev_index_up = index_up
    prev_middle_up = middle_up

def main():
    global screen_width, screen_height
    cap = cv2.VideoCapture(0)
    draw = mp.solutions.drawing_utils

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(frame_rgb)

        h, w, _ = frame.shape
        ctrl_w, ctrl_h = int(w * 0.6), int(h * 0.6)
        off_x, off_y = (w - ctrl_w)//2, (h - ctrl_h)//2
        x_scale = screen_width / ctrl_w
        y_scale = screen_height / ctrl_h

        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            draw.draw_landmarks(frame, hand, mphands.HAND_CONNECTIONS)
            landmarks = [(lm.x, lm.y, lm.z) for lm in hand.landmark]
            detect_gestures(frame, landmarks, ctrl_w, ctrl_h, off_x, off_y, x_scale, y_scale)
        else:
            # Reset gesture states
            global left_click_count, left_click_pending, dragging
            left_click_count = 0
            left_click_pending = False
            if dragging:
                pyautogui.mouseUp()
                dragging = False

        cv2.rectangle(frame, (off_x, off_y), (off_x + ctrl_w, off_y + ctrl_h), (255,255,255), 2)
        cv2.imshow('Virtual Mouse', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
