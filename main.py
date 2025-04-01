# main.py
import cv2
import mediapipe as mp
import pyautogui
import time
from gesture_control import detect_gestures, reset_gesture_states

screen_width, screen_height = pyautogui.size()

mphands = mp.solutions.hands
hands = mphands.Hands(
    static_image_mode=False,
    model_complexity=1,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.5,
    max_num_hands=1,
)

def main():
    global screen_width, screen_height
    cap = cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
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
            reset_gesture_states()

        cv2.rectangle(frame, (off_x, off_y), (off_x + ctrl_w, off_y + ctrl_h), (255,255,255), 2)
        cv2.imshow('Virtual Mouse', frame)

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
