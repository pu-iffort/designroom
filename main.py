import os
from flask import Flask, render_template, request, jsonify
import ezdxf
from shapely.geometry import Polygon
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Path to store uploaded DXF files
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Minimum area threshold to filter out small shapes
MIN_AREA_THRESHOLD = 100.0

# Route to render the frontend template
@app.route('/')
def index():
    return render_template('index1.html')

# Route to process the uploaded DXF file
@app.route('/process_dxf', methods=['POST'])
def process_dxf():
    # Check if a file is part of the request
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    if file and file.filename.endswith('.dxf'):
        # Save the file to the server
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(file_path)

        # Process the DXF file
        return process_file(file_path)
    else:
        return jsonify({'error': 'Invalid file format. Please upload a DXF file.'})


def process_file(dxf_file_path):
    # Load the DXF file
    doc = ezdxf.readfile(dxf_file_path)
    msp = doc.modelspace()

    # Initialize total area and list to store dimensions of rooms
    total_area = 0.0
    room_dimensions = []

    # Loop through all entities in the model space
    for entity in msp:
        if entity.dxftype() == 'LWPOLYLINE' and entity.closed:
            points = [point[:2] for point in entity.get_points()]
            polygon = Polygon(points)
            area = polygon.area

            # Filter out small polylines based on area threshold
            if area < MIN_AREA_THRESHOLD:
                continue  # Skip small areas

            bounds = polygon.bounds
            width = bounds[2] - bounds[0]
            height = bounds[3] - bounds[1]

            room_dimensions.append({
                "room_id": len(room_dimensions) + 1,
                "width": width,
                "height": height,
                "area": area,
                "polygon": list(polygon.exterior.coords)  # Serialize the polygon to a list of coordinates
            })
            total_area += area

    # Handle case where no valid rooms are found
    if not room_dimensions:
        return jsonify({'error': 'No valid rooms found in the DXF file.'})

    # Identify and remove the room with the largest area
    largest_room = max(room_dimensions, key=lambda room: room['area'])
    room_dimensions.remove(largest_room)

    # Generate ceiling designs using OpenAI
    ceiling_images = []
    for room in room_dimensions:
        image_url = generate_ceiling_image(room)
        ceiling_images.append({
            "room_id": room['room_id'],
            "image_url": image_url
        })

    # Return the JSON response
    return jsonify({
        'total_area': total_area,
        'room_dimensions': room_dimensions,
        'ceiling_images': ceiling_images
    })


def generate_ceiling_image(room):
    # Generate a textual prompt for the room ceiling design
    prompt = (f"Design a ceiling for a room with the following dimensions: "
              f"Width: {room['width']} units, Height: {room['height']} units. "
              "The design should be proportional to the room size with modern decor, lighting, and an artistic style. Put more focus on light arragement")
    
    # Request the image generation from OpenAI
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1
    )
    
    image_url = response.data[0].url
    return image_url

if __name__ == '__main__':
    app.run(debug=True,host="0.0.0.0",port=4000)
