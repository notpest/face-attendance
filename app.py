from flask import Flask, render_template, request, Response, redirect, url_for, flash, jsonify, session
import psycopg2
from psycopg2 import Error
import base64
import cv2
import numpy as np
import face_recognition as face
from datetime import datetime
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.secret_key = 'nitins_secret_key'
# Database connection details
DB_HOST = "localhost"
DB_NAME = "face_attendance"
DB_USER = "postgres"
DB_PASS = "admin"

def get_db_connection():
    conn = psycopg2.connect(host=DB_HOST, database=DB_NAME, user=DB_USER, password=DB_PASS)
    return conn

image = []
encode = []
u = []

def grab():
    try:
        # Connect to the PostgreSQL database
        connection = psycopg2.connect(user="postgres",
                                      password="admin",
                                      host="localhost",
                                      port="5432",
                                      database="face_attendance")

        cursor = connection.cursor()
        dd = []

        # Insert data into the encoder table
        cursor.execute("SELECT content FROM public.encoder")
        records = cursor.fetchall()
        for encodes in records:
            cursor.execute('''SELECT (user_id) FROM public.resources INNER JOIN public.encoder ON 
                           resources.id = encoder.resource_id WHERE encoder.content = (%s)''',(encodes,))
            d = cursor.fetchall()
            u.append(d[0])
            cursor.execute('''SELECT (name) FROM public.user WHERE id = (%s)''',(d[0],))
            d = cursor.fetchall()
            dd.append(d[0])

        # Return the fetched records
        return records, dd
    except (Exception, Error) as error:
        print("Error:", error)
    finally:
        # Close database connection
        if connection:
            cursor.close()
            connection.close()
            print("PostgreSQL connection is closed")

cap  = cv2.VideoCapture(0)
# Function to access the webcam
def get_frame():
    # Access the webcam
    while True:
        success, img = cap.read()
        if not success:
            break
        else:
            success, buffer1 = cv2.imencode('.jpg', img)
            frame = buffer1.tobytes()
            yield (b'--frame\r\n'b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def verify(img):
    tests, imagep = grab()
    for x in tests:
        arr = x[0]
        b = np.fromstring(arr.strip('[]'), sep=' ')
        encode.append(b.reshape(128,))
    # Yield the frame in byte format
    imgS = cv2.resize(img, (0,0), None, 0.25,0.25)
    imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
    faces_in_frame = face.face_locations(imgS)
    if len(faces_in_frame)==0:
        return "Face not in frame"
    encoded_faces = face.face_encodings(imgS, faces_in_frame)
    for encode_face, faceloc in zip(encoded_faces,faces_in_frame):
        matches = face.compare_faces(encode, encode_face)
        faceDist = face.face_distance(encode, encode_face)
        matchIndex = np.argmin(faceDist)
        if matches[matchIndex]:
            name = imagep[matchIndex]
            mark_attendance(u[matchIndex])

            # Get the current timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            name = str(name)
            name = name[2:len(name)-3]

            # Return the customized greeting message
            return f"Welcome {name}, attendance marked at {timestamp}"
        else:
            return "Unrecognised"

def mark_attendance(name):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Insert data into the table
        cursor.execute("INSERT INTO attendance (user_id) VALUES (%s)", (name,))

        # Commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        print("Row inserted successfully!")
    except (Exception, Error) as error:
        print("Error:", error)

@app.route('/')
def welcome():
    # Render the HTML template
    return render_template('welcome.html')

@app.route('/user_login')
def user_login():
    return render_template('user.html')

@app.route('/video_feed')
def video_feed():
    # Return the response generated along with the specific media type (mime type)
    return Response(get_frame(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/admin_login')
def admin_login():
    return render_template('admin.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, hashed_password FROM admin WHERE username = %s",
        (username,)
    )
    admin = cursor.fetchone()

    if admin and check_password_hash(admin[1], password):
        session['admin_id'] = admin[0]
        cursor.execute(
            "INSERT INTO public.login_history (admin_id, login_time) VALUES (%s, CURRENT_TIMESTAMP)",
            (admin[0],)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return redirect(url_for('dashboard'))
    else:
        cursor.close()
        conn.close()
        flash('Invalid username or password. Please try again.', 'danger')
        return redirect(url_for('admin_login'))
    
@app.route('/dashboard')
def dashboard():
    users = show_users()
    return render_template('dashboard.html', users=users)

def show_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch data from both tables using a JOIN
    query = """
        SELECT u.id, u.register_no, u.name, ct.class_name, r.content
        FROM public.user u
        LEFT JOIN public.user_class uc ON u.id = uc.user_id
        LEFT JOIN public.class_type ct ON uc.class_id = ct.id
        LEFT JOIN public.resources r ON u.id = r.user_id::uuid
    """
    cursor.execute(query)
    users = cursor.fetchall()

    users_with_images = []
    for user in users:
        user_id, register_no, name, class_name, content = user
        # Check if content (image) exists for the user
        if content:
            # Encode the image data as base64
            image_base64 = base64.b64encode(content).decode('utf-8')
            user_data = {
                "id": user_id,
                "register_no": register_no,
                "name": name,
                "class_name": class_name,
                "image_base64": image_base64
            }
        else:
            user_data = {
                "id": user_id,
                "register_no": register_no,
                "name": name,
                "class_name": class_name,
                "image_base64": None
            }
        users_with_images.append(user_data)

    cursor.close()
    conn.close()
    return users_with_images

@app.route('/add_user', methods=['POST'])
def add_user():
    try:
        data = request.get_json()
        
        register_no = data.get('register_no')
        name = data.get('name')
        class_name = data.get('class_name') 
        image_base64 = data.get('image')
        image_data = base64.b64decode(image_base64)
        admin_id = session.get('admin_id')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO public.user (register_no, name, created_by, updated_by) VALUES (%s, %s, %s, %s) RETURNING id",
            (register_no, name, admin_id, admin_id)
        )
        user_id = cursor.fetchone()[0]
        cursor.execute(
            "SELECT id FROM public.class_type WHERE class_name = (%s)",
            (class_name,)
        )
        class_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT INTO public.user_class (class_id, user_id, created_by, updated_by) VALUES (%s, %s, %s, %s)",
            (class_id, user_id, admin_id, admin_id)
        )
        cursor.execute(
            "INSERT INTO resources (user_id, content, type, created_by, updated_by) VALUES (%s, %s, 'registered_user', %s, %s) RETURNING id",
            (user_id, psycopg2.Binary(image_data), admin_id, admin_id)
        )

        resource_id = cursor.fetchone()[0]
        np_array = np.frombuffer(image_data, dtype=np.uint8)
        image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
        ef = face.face_encodings(image)[0]
        x = np.array_str(ef)

        cursor.execute("INSERT INTO public.encoder (resource_id, content, type, created_by, updated_by) VALUES (%s,%s,'array', %s, %s)",(resource_id,x, admin_id, admin_id))
        conn.commit()
        cursor.close()
        conn.close()

        print("User added successfully!")  # Debugging
        return jsonify({"message": "User added successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to add user."}), 500

@app.route('/dashboard_data', methods=['GET'])
def dashboard_data():
    users = show_users()
    users_with_images = [(user[0], user[1], user[2]) for user in users] 
    return jsonify({"users": users_with_images})

# Route to update user data
@app.route('/update_user_data', methods=['POST'])
def update_user_data():
    try:
        # Extract updated user data from the request
        user_id = request.form['id']
        register_no = request.form['register_no']
        name = request.form['name']
        class_name = request.form['class_name']
        content = request.form.get('content')  # Get base64-encoded image content if available
        admin_id = session.get('admin_id')

        # Update the user table
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE public.user SET register_no = %s, name = %s, updated_by = %s WHERE id = %s",
            (register_no, name, admin_id, user_id)
        )
        cursor.execute(
            "SELECT id FROM public.class_type WHERE class_name = (%s)",
            (class_name,)
        )
        class_id = cursor.fetchone()[0]
        cursor.execute(
            "UPDATE public.user_class SET class_id = %s, updated_by = %s WHERE user_id = %s",
            (class_id, admin_id, user_id)
        )

        # Update the resources table with the base64-encoded image content if available
        if content:
            # Decode the base64-encoded content
            image_data = base64.b64decode(content)
            cursor.execute(
                "UPDATE public.resources SET content = %s, updated_by = %s WHERE user_id = %s RETURNING id",
                (image_data, admin_id, user_id)
            )
            resource_id = cursor.fetchone()[0]
            np_array = np.frombuffer(image_data, dtype=np.uint8)
            image = cv2.imdecode(np_array, cv2.IMREAD_COLOR)
            ef = face.face_encodings(image)[0]
            x = np.array_str(ef)

            cursor.execute("UPDATE public.encoder SET content = %s, updated_by = %s WHERE resource_id = %s",
                           (x, admin_id, resource_id))

        # Commit the changes
        conn.commit()
        cursor.close()
        conn.close()

        print("User data updated successfully!")  # Debugging
        return jsonify({"message": "User data updated successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to update user data."}), 500
    
# Route to fetch user data by register number
@app.route('/get_user_data_by_register_no/<register_no>', methods=['GET'])
def get_user_data_by_register_no(register_no):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch user data by register number
        cursor.execute(
            "SELECT u.id, u.register_no, u.name, r.content " +
            "FROM public.user u " +
            "JOIN public.resources r ON u.id = r.user_id " +
            "WHERE u.register_no = %s",
            (register_no,)
        )
        user_data = cursor.fetchone()
        cursor.execute(
            "SELECT ct.class_name " +
            "FROM public.class_type ct " +
            "JOIN public.user_class uc ON ct.id = uc.class_id " +
            "JOIN public.user u ON u.id = uc.user_id"
        )
        class_name = cursor.fetchone()
        cursor.close()
        conn.close()
        if user_data:
            # Convert binary data (content) to base64 encoding
            content_base64 = base64.b64encode(user_data[3]).decode('utf-8')

            # Return the user data with content as base64 string
            return jsonify({
                'id': str(user_data[0]),
                'register_no': user_data[1],
                'name': user_data[2],
                'class': class_name,
                'content': content_base64
            })
        else:
            return jsonify({'message': 'User not found'}), 404

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to fetch user data."}), 500
    
# Route to delete user data
@app.route('/delete_user_data', methods=['POST'])
def delete_user_data():
    try:
        # Extract user ID from the request
        register_no = request.form['id']

        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete user data from both tables
        cursor.execute(
            "DELETE FROM public.user WHERE register_no = %s RETURNING id",
            (register_no,)
        )
        user_id = cursor.fetchone()[0]
        cursor.execute(
            "DELETE FROM public.resources WHERE user_id = %s RETURNING id",
            (user_id,)
        )
        resource_id = cursor.fetchone()[0]
        cursor.execute(
            "DELETE FROM public.user_class WHERE user_id = %s",
            (user_id,)
        )
        cursor.execute(
            "DELETE FROM encoder WHERE resource_id = %s",
            (resource_id,)
        )   

        cursor.execute(
            "DELETE FROM public.attendance WHERE user_id = %s",
            (user_id,)
        )

        conn.commit()
        cursor.close()
        conn.close()

        print("User data deleted successfully!")  # Debugging
        return jsonify({"message": "User data deleted successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to delete user data."}), 500

@app.route('/classm')
def classm():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Fetch classes from the database
    cursor.execute("SELECT id, class_name FROM public.class_type")
    classes = cursor.fetchall()

    classes_array = []
    for classs in classes:
        class_id, class_name = classs
        class_data = {
            "id": class_id,
            "class_name": class_name
        }
        classes_array.append(class_data)

    cursor.close()
    conn.close()
    return render_template('classm.html', classes=classes_array)

@app.route('/add_class', methods=['POST'])
def add_class():
    try:
        class_name = request.form['class_name']
        admin_id = session.get('admin_id')

        # Insert the new class into the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO class_type (class_name, created_by, updated_by) VALUES (%s, %s, %s)",
            (class_name, admin_id, admin_id)
        )
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"class_name": class_name}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to add class."}), 500

@app.route('/update_class', methods=['POST'])
def update_class():
    try:
        class_id = request.form['id']
        class_name = request.form['class_name']
        admin_id = session.get('admin_id')
        # Update the class in the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE class_type SET class_name = %s, updated_by = %s WHERE id = %s",
            (class_name, admin_id, class_id)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Class updated successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to update class."}), 500

@app.route('/delete_class', methods=['POST'])
def delete_class():
    try:
        class_name = request.form['class_name']

        # Delete the class from the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM public.class_type WHERE class_name = %s RETURNING id",
            (class_name,)
        )
        class_id = cursor.fetchone()[0]
        cursor.execute(
            "DELETE FROM public.user_class WHERE class_id = %s",
            (class_id,)
        )
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({"message": "Class deleted successfully!"}), 200

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to delete class."}), 500

@app.route('/get_class_names')
def get_class_names():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT class_name FROM class_type")
        class_names = [row[0] for row in cursor.fetchall()]

        cursor.close()
        conn.close()

        return jsonify(class_names), 200
    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({"message": "Failed to fetch class names."}), 500

@app.route('/save_image', methods=['GET'])
def save_image():
    _,buffers = cap.read()
    if buffers is not None:
        m = verify(buffers)
        return jsonify({'message': m})
    else:
        return jsonify({'message': 'No frame available'})
    
@app.route('/get_user_attendance/<register_no>', methods=['GET'])
def get_user_attendance(register_no):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Fetch attendance dates for the user by register number
        cursor.execute(
            """
            SELECT a.date
            FROM public.user u
            JOIN public.attendance a ON u.id = a.user_id
            WHERE u.register_no = %s
            """, (register_no,)
        )
        attendance_records = cursor.fetchall()

        cursor.close()
        conn.close()

        if attendance_records:
            attendance_dates = [record[0].strftime('%Y-%m-%d') for record in attendance_records]
            return jsonify({'success': True, 'attendance': attendance_dates})
        else:
            return jsonify({'success': False, 'message': 'No attendance records found'}), 404

    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({'success': False, 'message': 'Failed to fetch user attendance data.'}), 500
    
@app.route('/fetch_attendance_data')
def fetch_attendance_data():
    try:
        class_id = request.args.get('class_id')
        date = request.args.get('date')

        conn = get_db_connection()
        cursor = conn.cursor()

        # Query to get users and their attendance for the specified class and date
        cursor.execute("""
            SELECT u.register_no, u.name, 
                CASE WHEN a.date IS NOT NULL THEN TRUE ELSE FALSE END AS attendance
            FROM public.user u
            JOIN public.user_class uc ON u.id = uc.user_id
            LEFT JOIN public.attendance a ON u.id = a.user_id AND DATE(a.date) = DATE(%s)
            WHERE uc.class_id = %s
        """, (date, class_id))

        attendance_data = cursor.fetchall()
        print("Attendance data:", attendance_data)
        cursor.close()
        conn.close()

        # Convert data to a list of dictionaries for easy JSON serialization
        attendance_list = [
            {'register_no': row[0], 'name': row[1], 'attendance': row[2]}
        for row in attendance_data]

        return jsonify(attendance_list)
    except Exception as e:
        print(f"Error occurred: {e}")  # Debugging
        return jsonify({'success': False, 'message': 'Failed to fetch attendance data.'}), 500
    

@app.route('/logout', methods=['POST'])
def logout():
    admin_id = session.get('admin_id')
    if admin_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE public.login_history SET signout_time = CURRENT_TIMESTAMP WHERE admin_id = %s AND signout_time IS NULL",
            (admin_id,)
        )
        conn.commit()
        cursor.close()
        conn.close()
        session.pop('admin_id', None)  # Remove admin_id from session
        return jsonify({"message": "Logged out successfully!"}), 200
    else:
        return jsonify({"message": "No active session found."}), 400

if __name__ == '__main__':
    app.run(debug=True)