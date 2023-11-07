import face_recognition
import json
from PIL import Image
import numpy as np
import mss
import tkinter as tk
from ctypes import windll
import time
import os
from tkinter.font import Font
from collections import defaultdict
import argparse

# Create the parser and add arguments / not currently working
parser = argparse.ArgumentParser()
parser.add_argument('--landmarks', action='store_true', help='Draw facial landmarks on the detected faces')
parser.add_argument('--landmarklines', action='store_true', help='Draw lines between facial landmarks')

# Parse the arguments
args = parser.parse_args()

# Global variable to keep track of the drawn windows
drawn_windows = []
previous_screenshot = None

# Initialize Tkinter and font globally, so it's not destroyed until the program ends
root = tk.Tk()
root.withdraw()  # Hide the main window
font = Font(family="Helvetica", size=10)  # Adjust font family and size as needed

def get_text_width(text):
    return font.measure(text)

# Function to capture the screen
def capture_screen():
    user32 = windll.user32
    user32.SetProcessDPIAware()  # Set process DPI aware for correct scaling
    with mss.mss() as sct:
        monitor_number = 3  # Adjust as per your setup (to focus on which monitor)
        monitor = sct.monitors[monitor_number]

        monitor_info = {
            "top": monitor["top"], "left": monitor["left"],
            "width": monitor["width"], "height": monitor["height"],
            "mon": monitor_number
        }
        sct_img = sct.grab(monitor_info)
        scale_factor = monitor['width'] / sct_img.width
        return Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX'), scale_factor

def is_different_enough(current, previous, threshold=10000000):
    if previous is None:
        return True
    # Compute the sum of absolute differences
    diff = np.sum(np.abs(np.array(current) - np.array(previous)))
    return diff > threshold

def load_saved_data(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def get_name_from_path(path):
    parts = path.split(os.sep)
    if len(parts) >= 2:
        parent_dir = parts[-2]
        # If the parent directory is numeric, it is likely an ID which means no name is set for the facial recognition
        if parent_dir.isdigit():
            # If 'faces' or a number is the parent directory, return the grandparent directory name
            if len(parts) >= 3:
                grandparent_dir = parts[-3]
                # Check if the grandparent directory name is not 'faces'
                if grandparent_dir.lower() != "faces":
                    return grandparent_dir
                else:
                    # If the grandparent directory is also 'faces', then return the great grandparent directory if available
                    if len(parts) >= 4:
                        great_grandparent_dir = parts[-4]
                        return great_grandparent_dir
                    else:
                        # Default to 'Unknown' if the great grandparent directory doesn't exist
                        return "Unknown"
            else:
                # Default to 'Unknown' if the grandparent directory doesn't exist
                return "Unknown"
        else:
            # If the parent directory is not numeric and not 'faces', assume it is the name
            return parent_dir
    else:
        # Default to 'Unknown' or any generic placeholder if path structure is not as expected
        return "Unknown"
    
def find_matching_faces(known_encodings, face_to_check, tolerance=0.485):
    known_encodings = [np.array(encoding) if isinstance(encoding, list) else encoding for encoding in known_encodings]
    for encoding in known_encodings:
        if isinstance(encoding, str):
            print("Encoding is a string, which is not expected:", encoding)
            encoding = np.array(json.loads(encoding.replace('\'', '"')))
    face_distances = face_recognition.face_distance(known_encodings, face_to_check)
    matches = []
    for i, face_distance in enumerate(face_distances):
        if face_distance < tolerance:
            matches.append((i, face_distance))
    return matches

saved_encodings_path = 'face_encodings.json'
saved_encodings = load_saved_data(saved_encodings_path)

all_saved_encodings = []
saved_names = []
image_paths = []
saved_names_with_paths = []

for path, info in saved_encodings.items():
    all_saved_encodings.extend(info['encodings'])
    name_from_path = get_name_from_path(path)
    # Store a tuple of name from path and path for each encoding
    saved_names_with_paths.extend([(name_from_path, path)] * len(info['encodings']))

# Working on this to create lines between landmarks for that argument. Currently not working
def draw_landmark_lines(canvas, face_landmarks, scale_factor, offset_left, offset_top):
    print("Drawing landmark lines...")
    feature_connections = {
        'chin': [(i, i+1) for i in range(16)],
        'left_eyebrow': [(i, i+1) for i in range(17, 21)],
        'right_eyebrow': [(i, i+1) for i in range(22, 26)],
        'nose_bridge': [(i, i+1) for i in range(27, 30)],
        'nose_tip': [(i, i+1) for i in range(31, 35)],
        'left_eye': [(i, i+1) for i in range(36, 41)] + [(41, 36)],
        'right_eye': [(i, i+1) for i in range(42, 47)] + [(47, 42)],
        'top_lip': [(i, i+1) for i in range(48, 54)] + [(54, 48)],
        'bottom_lip': [(i, i+1) for i in range(54, 59)] + [(59, 54)],
    }

    # Iterate over the features
    for feature, connections in feature_connections.items():
        points = face_landmarks[feature]
        for (start, end) in connections:
            x1, y1 = points[start]
            x2, y2 = points[end]

            # Scale the points
            x1_scaled = int(x1 * scale_factor) - offset_left
            y1_scaled = int(y1 * scale_factor) - offset_top
            x2_scaled = int(x2 * scale_factor) - offset_left
            y2_scaled = int(y2 * scale_factor) - offset_top

            # Draw the line on the canvas
            canvas.create_line(x1_scaled, y1_scaled, x2_scaled, y2_scaled, fill='blue')
                    
def draw_box(boxes, names_with_paths, scale_factor, face_landmarks_list=None, args=None):
    name_groups = defaultdict(lambda: {
        "boxes": [], "paths": [], "is_categorized": False, "is_uncategorized": False
    })

    for i, (box, (name, path)) in enumerate(zip(boxes, names_with_paths)):
        # Special case for numbered names which should be treated as "Unknown"
        if name.isdigit():
            name = "Unknown"
        name_groups[name]["boxes"].append((box, i))
        name_groups[name]["paths"].append(path)
        # Check if the path represents a categorized name or an 'Unknown' (uncategorized)
        if name.lower() == "unknown":
            name_groups[name]["is_uncategorized"] = True
        else:
            name_groups[name]["is_categorized"] = True

    for name, group in name_groups.items():
        # Skip the 'Unknown' label if this name has also been categorized
        if name.lower() == "unknown" and any(group["is_categorized"] for name, group in name_groups.items() if name.lower() != "unknown"):
            continue  # Skip labeling as 'Unknown' if there's also a known name
        # If both categorized and uncategorized matches are found for this name, display name with '(Unknown)'
        elif group["is_categorized"] and group["is_uncategorized"]:
            name_to_display = f"{name} (Unknown)"
        # If the name is categorized and not 'Unknown', check if the name appears multiple times
        elif group["is_categorized"]:
            possibly = " possibly" if len(group["boxes"]) > 1 else ""
            name_to_display = f"{name}{possibly}"
        else:
            # Default case, just use the name as it is
            name_to_display = name

        # Draw boxes and text for each name
        for box, index in group["boxes"]:
            top, right, bottom, left = box
            left = int(left * scale_factor)
            top = int(top * scale_factor)
            right = int(right * scale_factor)
            bottom = int(bottom * scale_factor)
            height = bottom - top

            # Calculate text width using the global font object
            text_width = get_text_width(name_to_display)

            # Ensure the window is at least as wide as the text
            width = max(right - left, text_width + 10)  # Add some padding

            window = tk.Toplevel(root)  # Use Toplevel window
            window.attributes("-transparentcolor", "white")
            window.attributes('-topmost', True)
            window.overrideredirect(True)
            window.geometry(f'{width}x{height+30}+{left}+{top}')

            canvas = tk.Canvas(window, width=width, height=height+30)
            canvas.pack()
            canvas.create_rectangle(0, 0, width, height, outline='green', fill="white")

            # Place text in the center, use the calculated text_width
            text_id = canvas.create_text(width / 2, height + 15, text=name_to_display, fill="green", anchor=tk.CENTER)

            # Draw facial landmarks if available
            if face_landmarks_list:
                landmarks = face_landmarks_list[index]  # Make sure this index aligns with the correct face.
        
                # If landmarklines argument is passed, draw lines between landmarks
                if args and args.landmarklines:
                    draw_landmark_lines(canvas, landmarks, scale_factor, left, top)
        
                # If landmarks argument is passed, draw small circles for each facial feature point
                if args and args.landmarks:
                    for facial_feature in landmarks.keys():
                        points = landmarks[facial_feature]
                        for point in points:
                            # Scale the landmark points as well
                            x, y = point
                            x_scaled = int(x * scale_factor) - left  # Offset by the face box's left coordinate
                            y_scaled = int(y * scale_factor) - top  # Offset by the face box's top coordinate

                            # Make sure that the landmark points are within the bounds of the drawn box
                            if 0 <= x_scaled <= width and 0 <= y_scaled <= (height + 30):
                                canvas.create_oval(x_scaled-2, y_scaled-2, x_scaled+2, y_scaled+2, outline='blue', fill='blue')
            
            drawn_windows.append(window)


    for window in drawn_windows:
        window.update()


def destroy_drawn_windows():
    global drawn_windows
    for window in drawn_windows:
        try:
            window.destroy()
        except tk.TclError as e:
            print("Window already destroyed:", e)
    drawn_windows = []

try:
    while True:
        screenshot_image, scale_factor = capture_screen()
        if is_different_enough(screenshot_image, previous_screenshot):
            previous_screenshot = screenshot_image
            destroy_drawn_windows()  # Destroy the boxes from the previous loop iteration

            # Convert PIL image to numpy array
            screenshot_array = np.array(screenshot_image)

            face_locations = face_recognition.face_locations(screenshot_array)
            face_encodings = face_recognition.face_encodings(screenshot_array, face_locations)

            # Calculate face landmarks for all detected faces
            face_landmarks_list = face_recognition.face_landmarks(screenshot_array, face_locations)

            for i, encoding in enumerate(face_encodings):
                matches = find_matching_faces(all_saved_encodings, encoding)
                if matches:
                    print("Matches found:")
                    boxes_to_draw = [face_locations[i] for match_index, _ in matches]
                    # Gather names and paths of matching faces
                    names_with_paths_to_draw = [saved_names_with_paths[match_index] for match_index, _ in matches]
            
                    # Directly pass the names with paths and the relevant face_landmarks to the draw_box function
                    # Filter landmarks for the faces that have a match
                    matched_landmarks = [face_landmarks_list[i] for match_index, _ in matches]
                    draw_box(boxes_to_draw, names_with_paths_to_draw, scale_factor, matched_landmarks if args.landmarks else [])

                    for match_index, face_distance in matches:
                        matched_name, matched_path = saved_names_with_paths[match_index]
                        print(f"- {matched_name} with a distance of {face_distance}, file: {matched_path}")
                else:
                    print("No matches found.")

          # Small step counter to not over throttle until we make it truly live vision.
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Program terminated by user.")
    destroy_drawn_windows()
