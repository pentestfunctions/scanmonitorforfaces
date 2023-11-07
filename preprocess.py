import face_recognition
import os
import json
import glob
from PIL import UnidentifiedImageError
from multiprocessing import Pool

# Function to get all image files from a directory and its subdirectories
def get_image_files(folder):
    image_types = ('*.jpg', '*.jpeg', '*.png', '*.gif', '*.bmp')  # Add or remove image types if needed
    files_grabbed = []
    for files in image_types:
        path_pattern = os.path.join(folder, '**', files)
        files_grabbed.extend(glob.glob(path_pattern, recursive=True))
    return files_grabbed

def process_image(image_file):
    print(f"Processing {image_file}...")
    encodings, name = encode_faces(image_file)
    if encodings:
        encodings_list = [encoding.tolist() for encoding in encodings]
        return image_file, {"encodings": encodings_list, "name": name}
    else:
        print(f"Skipping {image_file} due to error.")
        return image_file, None

# Function to encode faces in an image and get the name
def encode_faces(image_path, default_name='unknown'):
    try:
        image = face_recognition.load_image_file(image_path)
        face_encodings = face_recognition.face_encodings(image)
        # Extract person's name from the image path or use default name
        name = os.path.basename(os.path.dirname(image_path)) or default_name
        return face_encodings, name
    except UnidentifiedImageError:
        print(f"Cannot identify image file {image_path}. It may be corrupted or in an unsupported format.")
        return [], default_name
    
def main(folder, save_file):
    image_files = get_image_files(folder)
    face_data = {}

    with Pool() as pool:
        results = pool.map(process_image, image_files)
    
    for image_file, data in results:
        if data:
            face_data[image_file] = data

    with open(save_file, 'w') as f:
        json.dump(face_data, f)

    print(f"Data saved to {save_file}")

if __name__ == "__main__":
    folder_path = 'faces'
    save_path = 'face_encodings.json'
    main(folder_path, save_path)
