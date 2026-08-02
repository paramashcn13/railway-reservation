from flask import Flask, render_template, request, jsonify
import mysql.connector
from mysql.connector import Error
from datetime import date, datetime, timedelta
import decimal

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "student",
    "database": "railway_reservation"
}

def get_db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error:
        return None

def clean(row):
    if not row:
        return row
    out = {}
    for k, v in row.items():
        if isinstance(v, (date, datetime)):
            out[k] = v.strftime("%Y-%m-%d")
        elif isinstance(v, timedelta):
            total = int(v.total_seconds())
            out[k] = f"{total//3600:02d}:{(total%3600)//60:02d}"
        elif isinstance(v, decimal.Decimal):
            out[k] = float(v)
        else:
            out[k] = v
    return out

@app.route("/")
def index():
    return render_template("index.html")

# ── STATS ──
@app.route("/api/stats")
def stats():
    conn = get_db()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) AS cnt FROM train")
    trains = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM passenger")
    passengers = cur.fetchone()["cnt"]
    cur.execute("SELECT COUNT(*) AS cnt FROM reservation")
    bookings = cur.fetchone()["cnt"]
    cur.execute("SELECT COALESCE(SUM(Amount), 0) AS total FROM payment")
    revenue = float(cur.fetchone()["total"])
    conn.close()
    return jsonify({"trains": trains, "passengers": passengers, "bookings": bookings, "revenue": revenue})

# ══ TRAINS ══
@app.route("/api/trains", methods=["GET"])
def get_trains():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT Train_ID AS train_id, Train_Name AS train_name, Train_Type AS train_type, Total_Seats AS total_seats FROM train")
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/trains", methods=["POST"])
def add_train():
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO train (Train_ID, Train_Name, Train_Type, Total_Seats) VALUES (%s,%s,%s,%s)",
            (d["train_id"], d["train_name"], d["train_type"], d["total_seats"])
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Train added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/trains/<train_id>", methods=["PUT"])
def update_train(train_id):
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE train SET Train_Name=%s, Train_Type=%s, Total_Seats=%s WHERE Train_ID=%s",
            (d["train_name"], d["train_type"], d["total_seats"], train_id)
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Train updated"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/trains/<train_id>", methods=["DELETE"])
def delete_train(train_id):
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM train WHERE Train_ID=%s", (train_id,))
        conn.commit(); conn.close()
        return jsonify({"message": "Train deleted"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# ══ PASSENGERS ══
@app.route("/api/passengers", methods=["GET"])
def get_passengers():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT Passenger_ID AS passenger_id, Name AS name, Age AS age, Gender AS gender, Phone AS phone, Email AS email FROM passenger")
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/passengers", methods=["POST"])
def add_passenger():
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO passenger (Passenger_ID, Name, Age, Gender, Phone, Email) VALUES (%s,%s,%s,%s,%s,%s)",
            (d["passenger_id"], d["name"], d["age"], d["gender"], d["phone"], d["email"])
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Passenger added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/passengers/<passenger_id>", methods=["PUT"])
def update_passenger(passenger_id):
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE passenger SET Name=%s, Age=%s, Gender=%s, Phone=%s, Email=%s WHERE Passenger_ID=%s",
            (d["name"], d["age"], d["gender"], d["phone"], d["email"], passenger_id)
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Passenger updated"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/passengers/<passenger_id>", methods=["DELETE"])
def delete_passenger(passenger_id):
    conn = get_db()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT Reservation_ID FROM reservation WHERE Passenger_ID=%s", (passenger_id,))
        reservations = cur.fetchall()
        for r in reservations:
            rid = r[0]
            cur.execute("DELETE FROM payment WHERE Reservation_ID=%s", (rid,))
            cur.execute("DELETE FROM ticket WHERE Reservation_ID=%s", (rid,))
            cur.execute("DELETE FROM reservation WHERE Reservation_ID=%s", (rid,))
        cur.execute("DELETE FROM passenger WHERE Passenger_ID=%s", (passenger_id,))
        conn.commit(); conn.close()
        return jsonify({"message": "Passenger deleted"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# ══ RESERVATIONS ══
@app.route("/api/bookings", methods=["GET"])
def get_bookings():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT r.Reservation_ID AS booking_id, r.Reservation_Date AS booking_date,
               r.Status AS status, r.Passenger_ID AS passenger_id, r.Schedule_ID AS schedule_id,
               p.Name AS passenger_name, s.Journey_Date AS journey_date,
               s.Departure_Time AS departure_time, s.Arrival_Time AS arrival_time,
               s.Train_ID AS train_id, t.Train_Name AS train_name,
               tk.Seat_No AS seat_number, tk.Class AS class_type, tk.Fare AS fare
        FROM reservation r
        JOIN passenger p  ON r.Passenger_ID = p.Passenger_ID
        JOIN schedule  s  ON r.Schedule_ID  = s.Schedule_ID
        JOIN train     t  ON s.Train_ID     = t.Train_ID
        LEFT JOIN ticket tk ON tk.Reservation_ID = r.Reservation_ID
        ORDER BY r.Reservation_ID
    """)
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/bookings", methods=["POST"])
def add_booking():
    d = request.json
    conn = get_db()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        required = ["booking_id", "booking_date", "status", "passenger_id", "schedule_id",
                    "seat_no", "class_type", "fare", "payment_mode"]
        missing = [f for f in required if f not in d or d[f] == ""]
        if missing:
            return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400
        # Get train_id from schedule
        cur.execute("SELECT Train_ID FROM schedule WHERE Schedule_ID=%s", (d["schedule_id"],))
        train_id = cur.fetchone()[0]
        cur.execute("SELECT Total_Seats FROM train WHERE Train_ID=%s", (train_id,))
        seats = cur.fetchone()[0]

        if seats <= 0:
            return jsonify({"error": "No seats available"}), 400
        
        cur.execute(
            "INSERT INTO reservation (Reservation_ID, Reservation_Date, Status, Passenger_ID, Schedule_ID) VALUES (%s,%s,%s,%s,%s)",
            (d["booking_id"], d["booking_date"], d["status"], d["passenger_id"], d["schedule_id"])
        )
        cur.execute(
            "INSERT INTO ticket (Seat_No, Class, Fare, Reservation_ID) VALUES (%s,%s,%s,%s)",
            ( d["seat_no"], d["class_type"], d["fare"], d["booking_id"])
        )
        cur.execute(
            "INSERT INTO payment (Amount, Payment_Date, Payment_Mode, Reservation_ID) VALUES (%s,%s,%s,%s)",
            (d["fare"], d["booking_date"], d["payment_mode"], d["booking_id"])
        )
        # 🔥 STEP 3 — Reduce seat count
        cur.execute("""
                        UPDATE train
                        SET Total_Seats = Total_Seats - 1
                        WHERE Train_ID = %s
        """, (train_id,))
        conn.commit(); conn.close()
        return jsonify({"message": "Reservation + Ticket + Payment added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/bookings/<booking_id>", methods=["PUT"])
def update_booking(booking_id):
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("UPDATE reservation SET Status=%s WHERE Reservation_ID=%s", (d["status"], booking_id))
        conn.commit(); conn.close()
        return jsonify({"message": "Reservation updated"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/bookings/<booking_id>", methods=["DELETE"])
def delete_booking(booking_id):
    conn = get_db()
    if not conn:
        return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM payment WHERE Reservation_ID=%s", (booking_id,))
        cur.execute("DELETE FROM ticket WHERE Reservation_ID=%s", (booking_id,))
        cur.execute("DELETE FROM reservation WHERE Reservation_ID=%s", (booking_id,))
        conn.commit(); conn.close()
        return jsonify({"message": "Deleted successfully"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# ══ SCHEDULES ══
@app.route("/api/schedules", methods=["GET"])
def get_schedules():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT s.Schedule_ID AS schedule_id, s.Journey_Date AS journey_date,
               s.Departure_Time AS departure_time, s.Arrival_Time AS arrival_time,
               s.Train_ID AS train_id, t.Train_Name AS train_name
        FROM schedule s JOIN train t ON s.Train_ID = t.Train_ID
        ORDER BY s.Schedule_ID
    """)
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/schedules", methods=["POST"])
def add_schedule():
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO schedule (Schedule_ID, Journey_Date, Departure_Time, Arrival_Time, Train_ID) VALUES (%s,%s,%s,%s,%s)",
            (d["schedule_id"], d["journey_date"], d["departure_time"], d["arrival_time"], d["train_id"])
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Schedule added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/schedules/<schedule_id>", methods=["DELETE"])
def delete_schedule(schedule_id):
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("SELECT Reservation_ID FROM reservation WHERE Schedule_ID=%s", (schedule_id,))
        reservations = cur.fetchall()
        for r in reservations:
            rid = r[0]
            cur.execute("DELETE FROM payment WHERE Reservation_ID=%s", (rid,))
            cur.execute("DELETE FROM ticket WHERE Reservation_ID=%s", (rid,))
            cur.execute("DELETE FROM reservation WHERE Reservation_ID=%s", (rid,))
        cur.execute("DELETE FROM schedule WHERE Schedule_ID=%s", (schedule_id,))
        conn.commit(); conn.close()
        return jsonify({"message": "Schedule deleted"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# ══ STATIONS ══
@app.route("/api/stations", methods=["GET"])
def get_stations():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("SELECT Station_ID AS station_id, Station_Name AS station_name, Station_Code AS station_code FROM station ORDER BY Station_ID")
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/stations", methods=["POST"])
def add_station():
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO station (Station_ID, Station_Name, Station_Code) VALUES (%s,%s,%s)",
            (d["station_id"], d["station_name"], d["station_code"])
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Station added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/stations/<station_id>", methods=["DELETE"])
def delete_station(station_id):
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM station WHERE Station_ID=%s", (station_id,))
        conn.commit(); conn.close()
        return jsonify({"message": "Station deleted"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# ══ TRAIN ROUTES (train_station junction table) ══
@app.route("/api/train_stations", methods=["GET"])
def get_train_stations():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT ts.Train_ID AS train_id, t.Train_Name AS train_name,
               ts.Station_ID AS station_id, s.Station_Name AS station_name,
               s.Station_Code AS station_code,
               ts.Stop_Order AS stop_order,
               ts.Arrival_Time AS arrival_time,
               ts.Departure_Time AS departure_time
        FROM train_station ts
        JOIN train   t ON ts.Train_ID   = t.Train_ID
        JOIN station s ON ts.Station_ID = s.Station_ID
        ORDER BY ts.Train_ID, ts.Stop_Order
    """)
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/train_stations", methods=["POST"])
def add_train_station():
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO train_station (Train_ID, Station_ID, Stop_Order, Arrival_Time, Departure_Time) VALUES (%s,%s,%s,%s,%s)",
            (d["train_id"], d["station_id"], d["stop_order"], d.get("arrival_time") or None, d.get("departure_time") or None)
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Stop added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/train_stations/<train_id>/<station_id>", methods=["PUT"])
def update_train_station(train_id, station_id):
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE train_station SET Stop_Order=%s, Arrival_Time=%s, Departure_Time=%s WHERE Train_ID=%s AND Station_ID=%s",
            (d["stop_order"], d.get("arrival_time") or None, d.get("departure_time") or None, train_id, station_id)
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Stop updated"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

@app.route("/api/train_stations/<train_id>/<station_id>", methods=["DELETE"])
def delete_train_station(train_id, station_id):
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM train_station WHERE Train_ID=%s AND Station_ID=%s", (train_id, station_id))
        conn.commit(); conn.close()
        return jsonify({"message": "Stop deleted"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

# ══ PAYMENTS ══
@app.route("/api/payments", methods=["GET"])
def get_payments():
    conn = get_db()
    if not conn: return jsonify([])
    cur = conn.cursor(dictionary=True)
    cur.execute("""
        SELECT Payment_ID AS payment_id, Reservation_ID AS reservation_id,
               Payment_Date AS payment_date, Payment_Mode AS payment_mode, Amount AS amount
        FROM payment ORDER BY Payment_ID
    """)
    data = [clean(r) for r in cur.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/api/payments", methods=["POST"])
def add_payment():
    d = request.json
    conn = get_db()
    if not conn: return jsonify({"error": "DB connection failed"}), 500
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO payment (Payment_ID, Amount, Payment_Date, Payment_Mode, Reservation_ID) VALUES (%s,%s,%s,%s,%s)",
            (d["payment_id"], d["amount"], d["payment_date"], d["payment_mode"], d["reservation_id"])
        )
        conn.commit(); conn.close()
        return jsonify({"message": "Payment added"})
    except Error as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':
    app.run(debug=True)