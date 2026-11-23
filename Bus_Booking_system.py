
# IMPORT MODULES
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.uic import loadUi
from datetime import datetime
from PyQt5.QtGui import QTextDocument
from PyQt5.QtPrintSupport import QPrinter, QPrintDialog


import sys
import sqlite3
import os
import re
import uuid
import hashlib
import traceback

# DATABASE CONNECTION
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "BusBooking.db")

db = sqlite3.connect(DB_PATH)
db.execute("PRAGMA foreign_keys = ON")

cur = db.cursor()



# CREATE DATABASE TABLES

cur.executescript('''

CREATE TABLE IF NOT EXISTS Routes (
    RouteID INTEGER PRIMARY KEY AUTOINCREMENT,
    Origin TEXT NOT NULL,
    Destination TEXT NOT NULL,
    Distance REAL
);

CREATE TABLE IF NOT EXISTS Buses (
    BusID INTEGER PRIMARY KEY AUTOINCREMENT,
    RegistrationNumber TEXT UNIQUE NOT NULL,
    BusName TEXT,
    Capacity INTEGER NOT NULL CHECK(Capacity > 0)
);

CREATE TABLE IF NOT EXISTS Passengers (
    PassengerID INTEGER PRIMARY KEY AUTOINCREMENT,
    FullName TEXT NOT NULL,
    Email TEXT UNIQUE NOT NULL,
    PasswordHash TEXT NOT NULL,
    PhoneNumber TEXT
);

CREATE TABLE IF NOT EXISTS Admins (
    AdminID INTEGER PRIMARY KEY AUTOINCREMENT,
    FullName TEXT NOT NULL,
    Email TEXT UNIQUE NOT NULL,
    PasswordHash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS Schedules (
    ScheduleID INTEGER PRIMARY KEY AUTOINCREMENT,
    RouteID INTEGER NOT NULL,
    BusID INTEGER NOT NULL,
    DepartureTime TEXT NOT NULL,
    ArrivalTime TEXT NOT NULL,
    Fare REAL NOT NULL CHECK(Fare >= 0),

    FOREIGN KEY(RouteID) REFERENCES Routes(RouteID),
    FOREIGN KEY(BusID) REFERENCES Buses(BusID)
);

CREATE TABLE IF NOT EXISTS Bookings (
    BookingID INTEGER PRIMARY KEY AUTOINCREMENT,
    PassengerID INTEGER NOT NULL,
    ScheduleID INTEGER NOT NULL,
    SeatNumber TEXT NOT NULL,
    BookingStatus TEXT NOT NULL DEFAULT 'Confirmed'
        CHECK(BookingStatus IN ('Pending', 'Confirmed', 'Cancelled')),

    FOREIGN KEY(PassengerID) REFERENCES Passengers(PassengerID),
    FOREIGN KEY(ScheduleID) REFERENCES Schedules(ScheduleID)
);

CREATE TABLE IF NOT EXISTS Tickets (
    TicketID INTEGER PRIMARY KEY AUTOINCREMENT,
    BookingID INTEGER UNIQUE NOT NULL,
    ReferenceCode TEXT UNIQUE NOT NULL,
    IssueDate TEXT NOT NULL,

    FOREIGN KEY(BookingID) REFERENCES Bookings(BookingID)
);

CREATE UNIQUE INDEX IF NOT EXISTS UniqueActiveSeat
ON Bookings(ScheduleID, SeatNumber)
WHERE BookingStatus IN ('Pending', 'Confirmed');

''')

db.commit()

# ADD STATUS COLUMNS TO EXISTING TABLES

cur.execute("PRAGMA table_info(Routes)")
route_columns = [column[1] for column in cur.fetchall()]

if "Status" not in route_columns:
    cur.execute("""
        ALTER TABLE Routes
        ADD COLUMN Status TEXT NOT NULL DEFAULT 'Active'
    """)


cur.execute("PRAGMA table_info(Schedules)")
schedule_columns = [column[1] for column in cur.fetchall()]

if "ScheduleStatus" not in schedule_columns:
    cur.execute("""
        ALTER TABLE Schedules
        ADD COLUMN ScheduleStatus TEXT NOT NULL DEFAULT 'Active'
    """)

db.commit()
cur.execute("PRAGMA table_info(Buses)")
bus_columns = [column[1] for column in cur.fetchall()]

if "BusType" not in bus_columns:
    cur.execute("""
        ALTER TABLE Buses
        ADD COLUMN BusType TEXT NOT NULL DEFAULT 'Standard'
    """)

if "Status" not in bus_columns:
    cur.execute("""
        ALTER TABLE Buses
        ADD COLUMN Status TEXT NOT NULL DEFAULT 'Active'
    """)

db.commit()
# SAMPLE ROUTES
routes = [
    ("Abuja", "Lagos", 750),
    ("Lagos", "Ibadan", 130),
    ("Abuja", "Kaduna", 190)
]

for origin, destination, distance in routes:
    cur.execute("""
        INSERT INTO Routes (Origin, Destination, Distance)
        SELECT ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM Routes
            WHERE Origin = ? AND Destination = ?
        )
    """, (origin, destination, distance, origin, destination))

db.commit()

# SAMPLE BUSES
buses = [
    ("ABC-001", "BLUEBUS Executive", 40),
    ("ABC-002", "BLUEBUS Standard", 30),
    ("ABC-003", "BLUEBUS Premium", 20)
]

for registration, name, capacity in buses:
    cur.execute("""
        INSERT INTO Buses (RegistrationNumber, BusName, Capacity)
        VALUES (?, ?, ?)
        ON CONFLICT(RegistrationNumber) DO NOTHING
    """, (registration, name, capacity))

db.commit()

# SAMPLE SCHEDULES

schedules = [
    ("Abuja", "Lagos", "ABC-001",
     "2026-11-15 08:00:00", "2026-11-15 18:00:00", 45000),

    ("Lagos", "Ibadan", "ABC-002",
     "2026-11-15 09:00:00", "2026-11-15 11:00:00", 12000),

    ("Abuja", "Kaduna", "ABC-003",
     "2026-11-16 08:00:00", "2026-11-16 11:00:00", 15000)
]

for origin, destination, registration, departure, arrival, fare in schedules:

    cur.execute("""
        SELECT RouteID FROM Routes
        WHERE Origin = ? AND Destination = ?
    """, (origin, destination))

    route_id = cur.fetchone()[0]

    cur.execute("""
        SELECT BusID FROM Buses
        WHERE RegistrationNumber = ?
    """, (registration,))

    bus_id = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO Schedules
        (RouteID, BusID, DepartureTime, ArrivalTime, Fare)
        SELECT ?, ?, ?, ?, ?
        WHERE NOT EXISTS (
            SELECT 1 FROM Schedules
            WHERE RouteID = ?
            AND BusID = ?
            AND DepartureTime = ?
        )
    """, (
        route_id, bus_id, departure, arrival, fare,
        route_id, bus_id, departure
    ))

db.commit()



# PASSWORD SECURITY
def hash_password(password):
    salt = os.urandom(16)

    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    )

    return salt.hex() + ":" + password_hash.hex()

def create_admin_account():


    full_name = "Habib Olaolu"
    email = "habib2004@gmail.com"

    cur.execute(
        "SELECT AdminID FROM Admins WHERE Email = ?",
        (email,)
    )

    if cur.fetchone():
        print("Admin account already exists.")
        return

    password = input("Enter admin password: ")

    password_hash = hash_password(password)

    cur.execute("""
        INSERT INTO Admins (FullName, Email, PasswordHash)
        VALUES (?, ?, ?)
    """, (full_name, email, password_hash))

    db.commit()

    print("Admin account created successfully.")


# PASSWORD VERIFICATION

def verify_password(password, stored_hash):
    salt, original_hash = stored_hash.split(":")

    password_hash = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        bytes.fromhex(salt),
        100000
    )

    return password_hash.hex() == original_hash
# PASSENGER REGISTRATION CLASS

class RegisterPassenger(QDialog):
    def __init__(self):
        print("Register button clicked")
        super(RegisterPassenger, self).__init__()
        loadUi(os.path.join(BASE_DIR, "registerpage.ui"), self)
        self.registerButton.clicked.connect(self.register)

    def register(self):

        fullname = self.fullname.text().strip()
        email = self.email.text().strip().lower()
        phone = self.phone.text().strip()
        password = self.password.text()
        confirm_password = self.confirmPassword.text()

        if not fullname or not email or not phone or not password or not confirm_password:
            self.errorLabel.setText("Please fill in all fields")

        elif not re.match(r'^[\w.+-]+@[\w-]+\.[\w.-]+$', email):
            self.errorLabel.setText("Enter a valid email address")

        elif len(password) < 8:
            self.errorLabel.setText("Password must be at least 8 characters")

        elif password != confirm_password:
            self.errorLabel.setText("Passwords do not match")

        else:
            try:
                password_hash = hash_password(password)

                cur.execute('''
                    INSERT INTO Passengers
                    (FullName, Email, PasswordHash, PhoneNumber)
                    VALUES (?, ?, ?, ?)
                ''', (fullname, email, password_hash, phone))

                db.commit()

                self.errorLabel.setText("Registration successful!")

                self.fullname.clear()
                self.email.clear()
                self.phone.clear()
                self.password.clear()
                self.confirmPassword.clear()

            except sqlite3.IntegrityError:
                db.rollback()
                self.errorLabel.setText("Email address already exists")

            except sqlite3.Error:
                db.rollback()
                self.errorLabel.setText("Database error. Please try again.")


# PASSENGER LOGIN CLASS
class LoginWindow(QDialog):
    def __init__(self):
        super(LoginWindow, self).__init__()
        loadUi(os.path.join(BASE_DIR, "loginpage.ui"), self)

        self.loginButton.clicked.connect(self.login)
        self.registerButton.clicked.connect(self.open_register)


    def login(self):
        email = self.email.text().strip().lower()
        password = self.password.text()

        if not email or not password:
            self.errorLabel.setText(
                "Please enter your email and password"
            )
            return

        # CHECK PASSENGER ACCOUNT
        cur.execute(
            "SELECT PassengerID, PasswordHash FROM Passengers WHERE Email = ?",
            (email,)
        )

        passenger = cur.fetchone()

        if passenger:
            passenger_id = passenger[0]
            stored_hash = passenger[1]

            if verify_password(password, stored_hash):
                self.errorLabel.setText("")

                try:
                    self.dashboard = PassengerDashboard(
                        passenger_id, self
                    )
                    self.dashboard.show()
                    self.hide()

                except Exception:
                    QMessageBox.critical(
                        self,
                        "Dashboard Error",
                        traceback.format_exc()
                    )

            else:
                self.errorLabel.setText(
                    "Incorrect email or password"
                )

            return

        # CHECK ADMIN ACCOUNT
        cur.execute(
            "SELECT AdminID, PasswordHash FROM Admins WHERE Email = ?",
            (email,)
        )

        admin = cur.fetchone()

        if admin:
            admin_id = admin[0]
            stored_hash = admin[1]

            if verify_password(password, stored_hash):
                self.errorLabel.setText("")

                try:
                    self.dashboard = AdminDashboard(self)
                    self.dashboard.show()
                    self.hide()

                except Exception:
                    QMessageBox.critical(
                        self,
                        "Admin Dashboard Error",
                        traceback.format_exc()
                    )

            else:
                self.errorLabel.setText(
                    "Incorrect email or password"
                )

        else:
            self.errorLabel.setText(
                "Incorrect email or password"
            )


    def open_register(self):
        self.register_window = RegisterPassenger()
        self.register_window.backButton.clicked.connect(self.back_to_login)
        self.register_window.show()
        self.hide()

    def back_to_login(self):
        self.register_window.close()
        self.show()


class PassengerDashboard(QWidget):
    def __init__(self, passenger_id, login_window):
        super(PassengerDashboard, self).__init__()

        loadUi(os.path.join(BASE_DIR, "PassengerDashboard.ui"), self)
        self.recentBookingsTable.setColumnWidth(0, 100)
        self.recentBookingsTable.setColumnWidth(1, 190)
        self.recentBookingsTable.setColumnWidth(2, 160)
        self.recentBookingsTable.setColumnWidth(3, 90)
        self.recentBookingsTable.setColumnWidth(4, 120)

        self.passenger_id = passenger_id
        cur.execute(
            "SELECT FullName FROM Passengers WHERE PassengerID = ?",
            (self.passenger_id,)
        )

        passenger = cur.fetchone()


        if passenger:
            self.welcomeLabel.setText(f"Welcome back, {passenger[0]}!")
# upcoming trips counter
        cur.execute("""
            SELECT COUNT(*)
            FROM Bookings b
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            WHERE b.PassengerID = ?
            AND b.BookingStatus = 'Confirmed'
            AND datetime(s.DepartureTime) > datetime('now', 'localtime')
        """, (self.passenger_id,))

        upcoming_trips = cur.fetchone()[0]
        self.upcomingCount.setText(str(upcoming_trips))

        # Completed trips counter
        cur.execute("""
            SELECT COUNT(*)
            FROM Bookings b
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            WHERE b.PassengerID = ?
            AND b.BookingStatus = 'Confirmed'
            AND datetime(s.DepartureTime) < datetime('now', 'localtime')
        """, (self.passenger_id,))

        completed_trips = cur.fetchone()[0]
        self.completedCount.setText(str(completed_trips))

        # Total bookings counter
        cur.execute("""
            SELECT COUNT(*)
            FROM Bookings
            WHERE PassengerID = ?
        """, (self.passenger_id,))

        total_bookings = cur.fetchone()[0]
        self.bookingsCount.setText(str(total_bookings))

        # Recent bookings
        cur.execute("""
            SELECT
                b.BookingID,
                r.Origin || ' - ' || r.Destination,
                s.DepartureTime,
                b.SeatNumber,
                b.BookingStatus
            FROM Bookings b
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            JOIN Routes r ON s.RouteID = r.RouteID
            WHERE b.PassengerID = ?
            ORDER BY b.BookingID DESC
            LIMIT 5
        """, (self.passenger_id,))

        bookings = cur.fetchall()

        self.recentBookingsTable.setRowCount(len(bookings))

        for row_index, booking in enumerate(bookings):
            for column_index, value in enumerate(booking):
                item = QTableWidgetItem(str(value))
                self.recentBookingsTable.setItem(
                    row_index, column_index, item
                )

        self.login_window = login_window
        self.logoutButton.clicked.connect(self.logout)
        self.bookBusButton.clicked.connect(self.open_book_bus)
        self.myBookingsButton.clicked.connect(self.open_my_bookings)
        self.myTicketsButton.clicked.connect(self.open_my_tickets)
        self.myProfileButton.clicked.connect(self.open_my_profile)
        # Set departure date to today's date


    def logout(self):
        self.close()
        self.login_window.show()

    def open_book_bus(self):
        self.book_bus_window = BookBusPage(self.passenger_id, self)
        self.book_bus_window.show()
        self.hide()


    def open_my_bookings(self):
        try:
            self.my_bookings_window = MyBookingsPage(
                self.passenger_id, self
            )
            self.my_bookings_window.show()
            self.hide()

        except Exception:
            QMessageBox.critical(
                self,
                "My Bookings Error",
                traceback.format_exc()
            )

    def open_my_tickets(self):
        try:
            self.my_tickets_window = MyTicketsPage(
                self.passenger_id, self
            )
            self.my_tickets_window.show()
            self.hide()

        except Exception:
            QMessageBox.critical(
                self,
                "My Tickets Error",
                traceback.format_exc()
            )

    def open_my_profile(self):
        try:
            self.my_profile_window = MyProfilePage(
                self.passenger_id, self
            )
            self.my_profile_window.show()
            self.hide()

        except Exception:
            QMessageBox.critical(
                self, "My Profile Error", traceback.format_exc()
            )

class BookBusPage(QWidget):
    def __init__(self, passenger_id, dashboard):
        super(BookBusPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "BookBusPage.ui"), self)

        self.passenger_id = passenger_id
        self.dashboard = dashboard

        self.backButton.clicked.connect(self.go_back)
        self.load_routes()

    def go_back(self):
        self.close()
        self.dashboard.show()

    def load_routes(self):
        cur.execute("SELECT DISTINCT Origin FROM Routes")
        origins = cur.fetchall()

        self.originCombo.clear()

        for origin in origins:
            self.originCombo.addItem(origin[0])

        self.originCombo.currentTextChanged.connect(self.load_destinations)

        self.load_destinations()
        self.searchBusButton.clicked.connect(self.search_buses)

    def load_destinations(self):
        origin = self.originCombo.currentText()

        cur.execute("""
            SELECT Destination FROM Routes
            WHERE Origin = ?
        """, (origin,))

        destinations = cur.fetchall()

        self.destinationCombo.clear()

        for destination in destinations:
            self.destinationCombo.addItem(destination[0])

    def search_buses(self):
        origin = self.originCombo.currentText()
        destination = self.destinationCombo.currentText()
        travel_date = self.travelDate.date().toString("yyyy-MM-dd")

        cur.execute("""
            SELECT
                s.ScheduleID,
                b.BusName,
                s.DepartureTime,
                s.ArrivalTime,
                s.Fare,
                b.Capacity
            FROM Schedules s
            JOIN Routes r ON s.RouteID = r.RouteID
            JOIN Buses b ON s.BusID = b.BusID
            WHERE r.Origin = ?
            AND r.Destination = ?
            AND r.Status = 'Active'
            AND s.ScheduleStatus = 'Active'
            AND b.Status = 'Active'
            AND DATE(s.DepartureTime) = ?
            AND s.DepartureTime > datetime('now', 'localtime')
            ORDER BY s.DepartureTime
        """, (origin, destination, travel_date))
        buses = cur.fetchall()
        self.availableBusesTable.setRowCount(len(buses))

        for row_index, bus in enumerate(buses):
            schedule_id = bus[0]
            bus_name = bus[1]
            departure = bus[2]
            arrival = bus[3]
            fare = bus[4]
            departure_time = datetime.strptime(departure, "%Y-%m-%d %H:%M:%S")
            arrival_time = datetime.strptime(arrival, "%Y-%m-%d %H:%M:%S")

            duration = arrival_time - departure_time
            hours = duration.seconds // 3600
            minutes = (duration.seconds % 3600) // 60

            duration_text = f"{hours}h {minutes}m"

            self.availableBusesTable.setItem(
                row_index, 0, QTableWidgetItem(bus_name)
            )

            self.availableBusesTable.setItem(
                row_index, 1, QTableWidgetItem(departure)
            )

            self.availableBusesTable.setItem(
                row_index, 2, QTableWidgetItem(arrival)
            )

            self.availableBusesTable.setItem(
                row_index, 3, QTableWidgetItem(duration_text)
            )

            self.availableBusesTable.setItem(
                row_index, 4, QTableWidgetItem(f"₦{fare:,.2f}")
            )
            book_button = QPushButton("Book")

            book_button.setStyleSheet("""
                QPushButton {
                    background-color: #16A6A1;
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 6px 14px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #128781;
                }
            """)

            self.availableBusesTable.setCellWidget(row_index, 5, book_button)
            book_button.clicked.connect(
                lambda checked, sid=schedule_id: self.open_seat_selection(sid)
            )

    def open_seat_selection(self, schedule_id):
        self.seat_selection_window = SeatSelectionPage(
            schedule_id, self.passenger_id, self
        )
        self.seat_selection_window.show()
        self.hide()

class SeatSelectionPage(QWidget):
    def __init__(self, schedule_id, passenger_id, book_bus_page):
        super(SeatSelectionPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "SeatSelectionPage.ui"), self)

        self.schedule_id = schedule_id
        self.passenger_id = passenger_id
        self.book_bus_page = book_bus_page

        self.backButton.clicked.connect(self.go_back)
        self.confirmBookingButton.clicked.connect(self.confirm_booking)
        self.load_trip_details()

    def go_back(self):
        self.close()
        self.book_bus_page.show()

    def load_trip_details(self):
        cur.execute("""
            SELECT
                r.Origin,
                r.Destination,
                b.BusName,
                s.DepartureTime,
                s.ArrivalTime,
                s.Fare,
                b.Capacity
            FROM Schedules s
            JOIN Routes r ON s.RouteID = r.RouteID
            JOIN Buses b ON s.BusID = b.BusID
            WHERE s.ScheduleID = ?
        """, (self.schedule_id,))

        trip = cur.fetchone()

        if trip:
            origin = trip[0]
            destination = trip[1]
            bus_name = trip[2]
            departure = trip[3]
            arrival = trip[4]
            fare = trip[5]
            capacity = trip[6]
            self.capacity = capacity
            self.fare = fare
            self.selected_seat = None
            self.seat_buttons = {}

            self.pageTitle.setText("Select Your Seat")
            self.routeLabel.setText(f"{origin} → {destination}")
            self.busLabel.setText(bus_name)
            self.departureLabel.setText(departure)
            self.dateLabel.setText(departure[:10])
            self.fareLabel.setText(f"₦{fare:,.2f}")
            self.generate_seats()

    def generate_seats(self):
        layout = QGridLayout(self.seatGridWidget)

        layout.setContentsMargins(15, 15, 15, 15)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        layout.setColumnMinimumWidth(2, 25)

        seat_letters = ["A", "B", "C", "D"]
        seat_columns = [0, 1, 3, 4]

        # Retrieve booked seats once
        cur.execute("""
            SELECT SeatNumber
            FROM Bookings
            WHERE ScheduleID = ?
            AND BookingStatus IN ('Pending', 'Confirmed')
        """, (self.schedule_id,))

        self.booked_seats = {seat[0] for seat in cur.fetchall()}

        for i in range(self.capacity):
            row = i // 4
            column = i % 4

            seat_number = f"{row + 1}{seat_letters[column]}"

            seat_button = QPushButton(seat_number)
            seat_button.setFixedSize(65, 40)

            if seat_number in self.booked_seats:
                seat_button.setStyleSheet("""
                    QPushButton {
                        background-color: #D9DEE5;
                        color: #777777;
                        border: 1px solid #AAB2BD;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                """)

                seat_button.setEnabled(False)

            else:
                seat_button.setStyleSheet("""
                    QPushButton {
                        background-color: #E8F5F4;
                        color: #142D4E;
                        border: 1px solid #16A6A1;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                    QPushButton:hover {
                        background-color: #C5E9E7;
                    }
                """)

                seat_button.clicked.connect(
                    lambda checked, seat=seat_number: self.select_seat(seat)
                )

            self.seat_buttons[seat_number] = seat_button

            layout.addWidget(
                seat_button, row, seat_columns[column]
            )

    def select_seat(self, seat_number):
        self.selected_seat = seat_number

        for seat, button in self.seat_buttons.items():

            if seat in self.booked_seats:
                continue

            if seat == seat_number:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #16A6A1;
                        color: white;
                        border: 1px solid #128781;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                """)

            else:
                button.setStyleSheet("""
                    QPushButton {
                        background-color: #E8F5F4;
                        color: #142D4E;
                        border: 1px solid #16A6A1;
                        border-radius: 6px;
                        font-weight: bold;
                    }
                """)

        self.selectedSeatLabel.setText(
            f"Selected Seat: {seat_number}"
        )

        self.totalFareLabel.setText(
            f"Total Fare: ₦{self.fare:,.2f}"
        )

    def confirm_booking(self):
        if not self.selected_seat:
            QMessageBox.warning(
                self, "No Seat Selected",
                "Please select a seat before confirming your booking."
            )
            return

        seat_number = self.selected_seat
        # Confirm that the selected seat belongs to this bus
        seat_letters = ["A", "B", "C", "D"]

        try:
            seat_row = int(seat_number[:-1])
            seat_letter = seat_number[-1]

            seat_position = (seat_row - 1) * 4 + seat_letters.index(seat_letter) + 1

        except (ValueError, IndexError):
            seat_position = 0

        if seat_position < 1 or seat_position > self.capacity:
            QMessageBox.warning(
                self,
                "Invalid Seat",
                "The selected seat is not valid for this bus."
            )
            return

        try:
            # Start a database transaction
            db.execute("BEGIN IMMEDIATE")
            # Check whether the schedule and route are still active
            cur.execute("""
                SELECT
                    Schedules.ScheduleStatus,
                    Routes.Status,
                    Buses.Status,
                    Schedules.DepartureTime
                FROM Schedules
                JOIN Routes ON Schedules.RouteID = Routes.RouteID
                JOIN Buses ON Schedules.BusID = Buses.BusID
                WHERE Schedules.ScheduleID = ?
            """, (self.schedule_id,))

            schedule_status = cur.fetchone()

            if (
                    schedule_status is None
                    or schedule_status[0] != 'Active'
                    or schedule_status[1] != 'Active'
                    or schedule_status[2] != 'Active'
                    or schedule_status[3] <= datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ):
                db.rollback()

                QMessageBox.warning(
                    self,
                    "Schedule Unavailable",
                    "Sorry, this route, schedule, or bus is no longer available. "
                    "Please search for another bus."
                )
                self.close()
                self.book_bus_page.show()
                return
            # Check whether the passenger still exists
            cur.execute("""
                SELECT PassengerID
                FROM Passengers
                WHERE PassengerID = ?
            """, (self.passenger_id,))

            if cur.fetchone() is None:
                db.rollback()

                QMessageBox.warning(
                    self,
                    "Passenger Not Found",
                    "Your passenger account could not be found. Please log in again."
                )
                self.close()
                self.book_bus_page.show()
                return
            # Check whether the seat is still available
            cur.execute("""
                SELECT BookingID
                FROM Bookings
                WHERE ScheduleID = ?
                AND SeatNumber = ?
                AND BookingStatus IN ('Pending', 'Confirmed')
            """, (self.schedule_id, seat_number))

            if cur.fetchone():
                db.rollback()

                QMessageBox.warning(
                    self, "Seat Unavailable",
                    "This seat has already been booked. Please select another seat."
                )
                return

            # Create the booking
            cur.execute("""
                INSERT INTO Bookings
                (PassengerID, ScheduleID, SeatNumber, BookingStatus)
                VALUES (?, ?, ?, 'Confirmed')
            """, (self.passenger_id, self.schedule_id, seat_number))

            booking_id = cur.lastrowid

            # Generate a unique ticket reference
            reference = "BB-" + uuid.uuid4().hex[:10].upper()

            issue_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Create the ticket
            cur.execute("""
                INSERT INTO Tickets
                (BookingID, ReferenceCode, IssueDate)
                VALUES (?, ?, ?)
            """, (booking_id, reference, issue_date))

            db.commit()

            QMessageBox.information(
                self,
                "Booking Successful",
                f"Your booking has been confirmed!\n\n"
                f"Booking ID: {booking_id}\n"
                f"Seat: {seat_number}\n"
                f"Ticket Reference: {reference}\n"
                f"Total Fare: ₦{self.fare:,.2f}"
            )

            self.close()
            self.book_bus_page.show()

        except sqlite3.IntegrityError:
            db.rollback()

            QMessageBox.warning(
                self, "Booking Error",
                "This seat is no longer available. Please select another seat."
            )

        except sqlite3.Error as error:
            db.rollback()

            QMessageBox.critical(
                self, "Database Error",
                f"Could not complete your booking.\n{error}"
            )

class MyBookingsPage(QWidget):
    def __init__(self, passenger_id, dashboard):
        super(MyBookingsPage, self).__init__()
        loadUi(os.path.join(BASE_DIR, "MyBookingsPage.ui"), self)

        self.bookingsTable.setColumnWidth(0, 85)
        self.bookingsTable.setColumnWidth(1, 150)
        self.bookingsTable.setColumnWidth(2, 105)
        self.bookingsTable.setColumnWidth(3, 100)
        self.bookingsTable.setColumnWidth(4, 65)
        self.bookingsTable.setColumnWidth(5, 110)
        self.bookingsTable.setColumnWidth(6, 90)
        self.bookingsTable.setColumnWidth(7, 100)

        self.passenger_id = passenger_id
        self.dashboard = dashboard

        self.backButton.clicked.connect(self.go_back)
        self.load_bookings()

    def go_back(self):
        self.close()
        self.dashboard.show()

    def load_bookings(self):
        cur.execute("""
            SELECT
                b.BookingID,
                r.Origin || ' - ' || r.Destination,
                s.DepartureTime,
                b.SeatNumber,
                s.Fare,
                b.BookingStatus
            FROM Bookings b
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            JOIN Routes r ON s.RouteID = r.RouteID
            WHERE b.PassengerID = ?
            ORDER BY b.BookingID DESC
        """, (self.passenger_id,))

        bookings = cur.fetchall()

        self.bookingsTable.setRowCount(len(bookings))

        for row_index, booking in enumerate(bookings):
            booking_id = booking[0]
            route = booking[1]
            departure = datetime.strptime(
                booking[2], "%Y-%m-%d %H:%M:%S"
            )
            seat = booking[3]
            fare = booking[4]
            status = booking[5]

            values = [
                booking_id,
                route,
                departure.strftime("%d/%m/%Y"),
                departure.strftime("%I:%M %p"),
                seat,
                f"₦{fare:,.2f}",
                status
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.bookingsTable.setItem(
                    row_index, column_index, item
                )
            cancel_button = QPushButton("Cancel")

            if status == "Confirmed" and departure > datetime.now():
                cancel_button.setStyleSheet("""
                                QPushButton {
                                    background-color: #FCE8E8;
                                    color: #C0392B;
                                    border: none;
                                    border-radius: 5px;
                                    padding: 6px;
                                    font-weight: bold;
                                }
                                QPushButton:hover {
                                    background-color: #F5CCCC;
                                }
                            """)

                cancel_button.clicked.connect(
                    lambda checked, bid=booking_id: self.cancel_booking(bid)
                )

            else:
                cancel_button.setText("—")
                cancel_button.setEnabled(False)

            self.bookingsTable.setCellWidget(
                row_index, 7, cancel_button
            )

    def cancel_booking(self, booking_id):
        reply = QMessageBox.question(
            self,
            "Cancel Booking",
            "Are you sure you want to cancel this booking?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.No:
            return

        try:
            cur.execute("""
                UPDATE Bookings
                SET BookingStatus = 'Cancelled'
                WHERE BookingID = ?
                AND PassengerID = ?
                AND BookingStatus = 'Confirmed'
                AND ScheduleID IN (
                    SELECT ScheduleID
                    FROM Schedules
                    WHERE DepartureTime > datetime('now', 'localtime')
                    AND ScheduleStatus = 'Active'
                )
            """, (booking_id, self.passenger_id))

            if cur.rowcount == 0:
                db.rollback()
                QMessageBox.warning(
                    self,
                    "Cancellation Failed",
                    "This booking cannot be cancelled."
                )
                return

            db.commit()

            QMessageBox.information(
                self,
                "Booking Cancelled",
                "Your booking has been cancelled successfully."
            )

            self.load_bookings()

        except sqlite3.Error as error:
            db.rollback()
            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not cancel booking.\n{error}"
            )


class MyTicketsPage(QWidget):
    def __init__(self, passenger_id, dashboard):
        super(MyTicketsPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "MyTicketsPage.ui"), self)

        self.passenger_id = passenger_id
        self.dashboard = dashboard

        self.ticketsTable.setColumnWidth(0, 75)
        self.ticketsTable.setColumnWidth(1, 145)
        self.ticketsTable.setColumnWidth(2, 155)
        self.ticketsTable.setColumnWidth(3, 105)
        self.ticketsTable.setColumnWidth(4, 100)
        self.ticketsTable.setColumnWidth(5, 65)
        self.ticketsTable.setColumnWidth(6, 90)

        self.backButton.clicked.connect(self.go_back)
        self.load_tickets()

    def go_back(self):
        self.close()
        self.dashboard.show()

    def load_tickets(self):
        cur.execute("""
            SELECT
                t.TicketID,
                t.ReferenceCode,
                r.Origin || ' - ' || r.Destination,
                s.DepartureTime,
                b.SeatNumber,
                b.BookingStatus
            FROM Tickets t
            JOIN Bookings b ON t.BookingID = b.BookingID
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            JOIN Routes r ON s.RouteID = r.RouteID
            WHERE b.PassengerID = ?
            ORDER BY t.TicketID DESC
        """, (self.passenger_id,))

        tickets = cur.fetchall()

        self.ticketsTable.setRowCount(len(tickets))

        for row_index, ticket in enumerate(tickets):
            ticket_id = ticket[0]
            reference = ticket[1]
            route = ticket[2]

            departure = datetime.strptime(
                ticket[3], "%Y-%m-%d %H:%M:%S"
            )

            seat = ticket[4]
            status = ticket[5]

            values = [
                ticket_id,
                reference,
                route,
                departure.strftime("%d/%m/%Y"),
                departure.strftime("%I:%M %p"),
                seat,
                status
            ]

            for column_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.ticketsTable.setItem(
                    row_index, column_index, item
                )
            view_button = QPushButton("View")
            print_button = QPushButton("Print")

            view_button.clicked.connect(
                lambda checked, tid=ticket_id: self.view_ticket(tid)
            )

            print_button.clicked.connect(
                lambda checked, tid=ticket_id: self.print_ticket(tid)
            )

            button_widget = QWidget()
            button_layout = QHBoxLayout(button_widget)

            button_layout.setContentsMargins(2, 2, 2, 2)
            button_layout.setSpacing(5)

            button_layout.addWidget(view_button)
            button_layout.addWidget(print_button)

            self.ticketsTable.setCellWidget(
                row_index, 7, button_widget
            )
    def view_ticket(self, ticket_id):
        cur.execute("""
            SELECT
                t.ReferenceCode,
                r.Origin,
                r.Destination,
                s.DepartureTime,
                b.SeatNumber,
                s.Fare,
                b.BookingStatus
            FROM Tickets t
            JOIN Bookings b ON t.BookingID = b.BookingID
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            JOIN Routes r ON s.RouteID = r.RouteID
            WHERE t.TicketID = ?
            AND b.PassengerID = ?
        """, (ticket_id, self.passenger_id))

        ticket = cur.fetchone()

        if ticket is None:
            QMessageBox.warning(
                self, "Ticket Not Found",
                "Could not find this ticket."
            )
            return

        reference, origin, destination, departure_time, seat, fare, status = ticket

        departure = datetime.strptime(
            departure_time, "%Y-%m-%d %H:%M:%S"
        )

        QMessageBox.information(
            self,
            "Ticket Details",
            f"""
            TICKET DETAILS

            Reference: {reference}
            Passenger ID: {self.passenger_id}
            Route: {origin} - {destination}
            Travel Date: {departure.strftime("%d/%m/%Y")}
            Departure: {departure.strftime("%I:%M %p")}
            Seat: {seat}
            Fare: ₦{fare:,.2f}
            Status: {status}
            """
        )

    def print_ticket(self, ticket_id):
        cur.execute("""
            SELECT
                t.ReferenceCode,
                p.FullName,
                p.PhoneNumber,
                r.Origin,
                r.Destination,
                s.DepartureTime,
                b.SeatNumber,
                s.Fare,
                b.BookingStatus
            FROM Tickets t
            JOIN Bookings b ON t.BookingID = b.BookingID
            JOIN Passengers p ON b.PassengerID = p.PassengerID
            JOIN Schedules s ON b.ScheduleID = s.ScheduleID
            JOIN Routes r ON s.RouteID = r.RouteID
            WHERE t.TicketID = ?
            AND b.PassengerID = ?
        """, (ticket_id, self.passenger_id))

        ticket = cur.fetchone()

        if ticket is None:
            QMessageBox.warning(
                self, "Ticket Not Found",
                "Could not find this ticket."
            )
            return

        reference, name, phone, origin, destination, departure_time, seat, fare, status = ticket

        departure = datetime.strptime(
            departure_time, "%Y-%m-%d %H:%M:%S"
        )

        document = QTextDocument()

        html = f"""
        <html>
        <body>
            <div style="text-align:center;">
                <h1 style="color:#142D4E;">BLUEBUS</h1>
                <h3>PASSENGER TRAVEL TICKET</h3>
            </div>

            <hr>

            <h2 style="color:#16A6A1;">{origin} → {destination}</h2>

            <p><b>Ticket Reference:</b> {reference}</p>
            <p><b>Passenger:</b> {name}</p>
            <p><b>Phone:</b> {phone}</p>
            <p><b>Travel Date:</b> {departure.strftime("%d/%m/%Y")}</p>
            <p><b>Departure Time:</b> {departure.strftime("%I:%M %p")}</p>
            <p><b>Seat Number:</b> {seat}</p>
            <p><b>Fare:</b> ₦{fare:,.2f}</p>
            <p><b>Booking Status:</b> {status}</p>

            <hr>

            <p style="text-align:center;">
                Thank you for travelling with BLUEBUS.
            </p>
        </body>
        </html>
        """

        document.setHtml(html)

        printer = QPrinter(QPrinter.HighResolution)
        print_dialog = QPrintDialog(printer, self)

        if print_dialog.exec_() == QPrintDialog.Accepted:
            document.print_(printer)

class MyProfilePage(QWidget):
    def __init__(self, passenger_id, dashboard):
        super(MyProfilePage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "MyProfilePage.ui"), self)

        self.passenger_id = passenger_id
        self.dashboard = dashboard

        self.backButton.clicked.connect(self.go_back)
        self.load_profile()
        self.updateProfileButton.clicked.connect(self.update_profile)
        self.changePasswordButton.clicked.connect(
            self.change_password
        )


    def go_back(self):
        self.close()
        self.dashboard.show()

    def load_profile(self):
        cur.execute("""
            SELECT FullName, Email, PhoneNumber
            FROM Passengers
            WHERE PassengerID = ?
        """, (self.passenger_id,))

        passenger = cur.fetchone()

        if passenger:
            self.fullNameInput.setText(passenger[0])
            self.emailInput.setText(passenger[1])
            self.phoneInput.setText(passenger[2] or "")

    def update_profile(self):
        full_name = self.fullNameInput.text().strip()
        phone = self.phoneInput.text().strip()

        if not full_name or not phone:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please enter your full name and phone number."
            )
            return

        try:
            cur.execute("""
                UPDATE Passengers
                SET FullName = ?, PhoneNumber = ?
                WHERE PassengerID = ?
            """, (full_name, phone, self.passenger_id))

            db.commit()

            QMessageBox.information(
                self,
                "Profile Updated",
                "Your profile has been updated successfully."
            )

        except sqlite3.Error as error:
            db.rollback()

            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not update your profile.\n{error}"
            )

    def change_password(self):
        current_password = self.currentPasswordInput.text()
        new_password = self.newPasswordInput.text()
        confirm_password = self.confirmPasswordInput.text()

        if not current_password or not new_password or not confirm_password:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in all password fields."
            )
            return

        if not verify_password(current_password, self.get_stored_password()):
            QMessageBox.warning(
                self,
                "Incorrect Password",
                "Your current password is incorrect."
            )
            return

        if len(new_password) < 8:
            QMessageBox.warning(
                self,
                "Weak Password",
                "Your new password must be at least 8 characters."
            )
            return

        if new_password != confirm_password:
            QMessageBox.warning(
                self,
                "Password Mismatch",
                "The new passwords do not match."
            )
            return

        try:
            new_hash = hash_password(new_password)

            cur.execute("""
                UPDATE Passengers
                SET PasswordHash = ?
                WHERE PassengerID = ?
            """, (new_hash, self.passenger_id))

            db.commit()

            QMessageBox.information(
                self,
                "Password Changed",
                "Your password has been changed successfully."
            )

            self.currentPasswordInput.clear()
            self.newPasswordInput.clear()
            self.confirmPasswordInput.clear()

        except sqlite3.Error as error:
            db.rollback()
            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not change password.\n{error}"
            )

    def test_change_password(self):
        try:
            self.change_password()

        except Exception:
            QMessageBox.critical(
                self,
                "Password Error",
                traceback.format_exc()
            )

    def get_stored_password(self):
        cur.execute("""
            SELECT PasswordHash
            FROM Passengers
            WHERE PassengerID = ?
        """, (self.passenger_id,))

        result = cur.fetchone()

        if result:
            return result[0]

        return None

class AdminDashboard(QWidget):
    def __init__(self, login_window):
        super(AdminDashboard, self).__init__()

        loadUi(os.path.join(BASE_DIR, "AdminDashboard.ui"), self)

        self.login_window = login_window
        self.load_dashboard_stats()
        self.load_recent_bookings()
        self.logoutButton.clicked.connect(self.logout)
        self.manageRoutesButton.clicked.connect(self.open_manage_routes)
        self.manageBusesButton.clicked.connect(self.open_manage_buses)
        self.manageSchedulesButton.clicked.connect(self.open_manage_schedules)
        self.manageBookingsButton.clicked.connect(self.open_manage_bookings)

    def load_dashboard_stats(self):

        cur.execute("SELECT COUNT(*) FROM Passengers")
        self.passengersCount.setText(str(cur.fetchone()[0]))

        cur.execute("SELECT COUNT(*) FROM Buses")
        self.busesCount.setText(str(cur.fetchone()[0]))

        cur.execute("""
            SELECT COUNT(*)
            FROM Buses
            WHERE Status = 'Active'
        """)
        self.activeBusesCount.setText(str(cur.fetchone()[0]))

        cur.execute("SELECT COUNT(*) FROM Routes")
        self.routesCount.setText(str(cur.fetchone()[0]))

        cur.execute("SELECT COUNT(*) FROM Bookings")
        self.bookingsCount.setText(str(cur.fetchone()[0]))

        cur.execute("""
            SELECT COUNT(*)
            FROM Schedules
            WHERE ScheduleStatus = 'Active'
            AND DepartureTime > datetime('now', 'localtime')
        """)
        self.upcomingSchedulesCount.setText(str(cur.fetchone()[0]))

    def load_recent_bookings(self):

        cur.execute("""
            SELECT
                Bookings.BookingID,
                Passengers.FullName,
                Routes.Origin || ' - ' || Routes.Destination,
                Schedules.DepartureTime,
                Bookings.SeatNumber,
                Bookings.BookingStatus

            FROM Bookings

            JOIN Passengers
                ON Bookings.PassengerID = Passengers.PassengerID

            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID

            JOIN Routes
                ON Schedules.RouteID = Routes.RouteID

            ORDER BY Bookings.BookingID DESC

            LIMIT 10
        """)

        bookings = cur.fetchall()

        self.recentBookingsTable.setRowCount(len(bookings))

        for row_index, booking in enumerate(bookings):

            for column_index, value in enumerate(booking):

                if column_index == 3:
                    formatted_date = datetime.strptime(
                        value, "%Y-%m-%d %H:%M:%S"
                    ).strftime("%d/%m/%Y %I:%M %p")

                    item = QTableWidgetItem(formatted_date)

                else:
                    item = QTableWidgetItem(str(value))

                self.recentBookingsTable.setItem(
                    row_index,
                    column_index,
                    item
                )

    def refresh_dashboard(self):
        self.load_dashboard_stats()
        self.load_recent_bookings()
    def logout(self):
        self.close()
        self.login_window.show()

    def open_manage_routes(self):
        self.manage_routes_window = ManageRoutesPage(self)
        self.manage_routes_window.show()
        self.hide()

    def open_manage_buses(self):
        self.manage_buses_window = ManageBusesPage(self)
        self.manage_buses_window.show()
        self.hide()

    def open_manage_schedules(self):
        try:
            self.manage_schedules_window = ManageSchedulesPage(self)
            self.manage_schedules_window.show()
            self.hide()

        except Exception:
            error_message = traceback.format_exc()

            QMessageBox.critical(
                self,
                "Manage Schedules Error",
                error_message
            )

    def open_manage_bookings(self):
        self.manage_bookings_window = ManageBookingsPage(self)
        self.manage_bookings_window.show()
        self.hide()
class ManageRoutesPage(QWidget):
    def __init__(self, admin_dashboard):
        super(ManageRoutesPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "ManageRoutesPage.ui"), self)

        self.admin_dashboard = admin_dashboard
        self.load_routes()
        self.backButton.clicked.connect(self.go_back)
        self.addRouteButton.clicked.connect(self.add_route)
        self.editRouteButton.clicked.connect(self.edit_route)
        self.deleteRouteButton.clicked.connect(self.delete_route)

    def load_routes(self):

        cur.execute("""
           SELECT RouteID, Origin, Destination, Distance, Status
        FROM Routes
        ORDER BY RouteID DESC
        """)

        routes = cur.fetchall()

        self.routesTable.setRowCount(len(routes))

        for row_index, route in enumerate(routes):

            for column_index, value in enumerate(route):

                item = QTableWidgetItem(str(value))

                self.routesTable.setItem(
                    row_index,
                    column_index,
                    item
                )

    def add_route(self):

        origin = self.originInput.text().strip()
        destination = self.destinationInput.text().strip()
        distance = self.distanceInput.text().strip()

        if not origin or not destination or not distance:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in all route fields."
            )
            return

        if origin.lower() == destination.lower():
            QMessageBox.warning(
                self,
                "Invalid Route",
                "Origin and destination cannot be the same."
            )
            return

        try:
            distance = float(distance)

            if distance <= 0:
                QMessageBox.warning(
                    self,
                    "Invalid Distance",
                    "Distance must be greater than zero."
                )
                return

        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Distance",
                "Please enter a valid numeric distance."
            )
            return

        is_editing = hasattr(self, "editing_route_id")

        try:

            if is_editing:

                route_id = self.editing_route_id

                # Check whether this route has any bookings
                cur.execute("""
                    SELECT COUNT(*)
                    FROM Bookings
                    JOIN Schedules
                        ON Bookings.ScheduleID = Schedules.ScheduleID
                    WHERE Schedules.RouteID = ?
                """, (route_id,))

                if cur.fetchone()[0] > 0:
                    QMessageBox.warning(
                        self,
                        "Route Cannot Be Edited",
                        "This route has existing bookings. "
                        "To protect passenger booking and ticket records, "
                        "it cannot be edited."
                    )
                    return

                cur.execute("""
                    UPDATE Routes
                    SET Origin = ?, Destination = ?, Distance = ?
                    WHERE RouteID = ?
                    AND Status = 'Active'
                """, (
                    origin,
                    destination,
                    distance,
                    route_id
                ))

                if cur.rowcount == 0:
                    db.rollback()
                    QMessageBox.warning(
                        self,
                        "Route Unavailable",
                        "This route is no longer available for editing."
                    )
                    return

                del self.editing_route_id
                self.addRouteButton.setText("+ Add Route")

            else:

                cur.execute("""
                    INSERT INTO Routes (Origin, Destination, Distance)
                    VALUES (?, ?, ?)
                """, (origin, destination, distance))

            db.commit()

            QMessageBox.information(
                self,
                "Success",
                "Route updated successfully." if is_editing
                else "The new route has been added successfully."
            )

            self.originInput.clear()
            self.destinationInput.clear()
            self.distanceInput.clear()

            self.load_routes()
            self.admin_dashboard.load_dashboard_stats()

        except sqlite3.IntegrityError:
            db.rollback()

            QMessageBox.warning(
                self,
                "Route Error",
                "Could not save this route."
            )

        except sqlite3.Error as error:
            db.rollback()

            QMessageBox.critical(
                self,
                "Database Error",
                str(error)
            )

    def edit_route(self):

        selected_row = self.routesTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Route Selected",
                "Please select a route you want to edit."
            )
            return

        route_id = self.routesTable.item(selected_row, 0).text()

        cur.execute("""
            SELECT Origin, Destination, Distance
            FROM Routes
            WHERE RouteID = ?
            AND Status = 'Active'
        """, (route_id,))

        route = cur.fetchone()

        if route is None:
            QMessageBox.warning(
                self,
                "Route Unavailable",
                "This route is inactive or no longer exists."
            )
            return

        # Check whether the route has existing bookings
        cur.execute("""
            SELECT COUNT(*)
            FROM Bookings
            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID
            WHERE Schedules.RouteID = ?
        """, (route_id,))

        if cur.fetchone()[0] > 0:
            QMessageBox.warning(
                self,
                "Route Cannot Be Edited",
                "This route has existing bookings. "
                "To protect passenger booking and ticket records, "
                "it cannot be edited."
            )
            return

        self.originInput.setText(route[0])
        self.destinationInput.setText(route[1])
        self.distanceInput.setText(str(route[2]))

        self.editing_route_id = route_id

        self.addRouteButton.setText("Save Changes")

    def delete_route(self):

        selected_row = self.routesTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Route Selected",
                "Please select a route you want to deactivate."
            )
            return

        route_id = self.routesTable.item(selected_row, 0).text()
        cur.execute("""
            SELECT Status
            FROM Routes
            WHERE RouteID = ?
        """, (route_id,))

        result = cur.fetchone()

        if result is None:
            QMessageBox.warning(
                self,
                "Route Not Found",
                "This route could not be found."
            )
            return

        if result[0] == "Inactive":
            QMessageBox.information(
                self,
                "Already Inactive",
                "This route is already inactive."
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Confirm Route Deactivation",
            "Are you sure you want to deactivate this route?\n\n"
            "Schedules without bookings will be deleted.\n"
            "Schedules with bookings will be cancelled.\n"
            "Existing bookings and tickets will be preserved.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirmation == QMessageBox.No:
            return

        try:
            # Find schedules belonging to this route
            cur.execute("""
                SELECT ScheduleID
                FROM Schedules
                WHERE RouteID = ?
            """, (route_id,))

            schedules = cur.fetchall()

            for schedule in schedules:

                schedule_id = schedule[0]

                # Check whether the schedule has bookings
                cur.execute("""
                    SELECT COUNT(*)
                    FROM Bookings
                    WHERE ScheduleID = ?
                """, (schedule_id,))

                booking_count = cur.fetchone()[0]

                if booking_count > 0:

                    # Preserve bookings and cancel the schedule
                    cur.execute("""
                        UPDATE Schedules
                        SET ScheduleStatus = 'Cancelled'
                        WHERE ScheduleID = ?
                    """, (schedule_id,))

                else:

                    # No bookings: safely delete the schedule
                    cur.execute("""
                        DELETE FROM Schedules
                        WHERE ScheduleID = ?
                    """, (schedule_id,))

            # Deactivate the route instead of deleting it
            cur.execute("""
                UPDATE Routes
                SET Status = 'Inactive'
                WHERE RouteID = ?
            """, (route_id,))

            db.commit()

            QMessageBox.information(
                self,
                "Route Deactivated",
                "The route has been deactivated successfully."
            )

            self.load_routes()
            self.admin_dashboard.load_dashboard_stats()

        except sqlite3.Error as error:

            db.rollback()

            QMessageBox.critical(
                self,
                "Database Error",
                str(error)
            )

    def go_back(self):
        self.close()
        self.admin_dashboard.refresh_dashboard()
        self.admin_dashboard.show()

class ManageSchedulesPage(QWidget):
    def __init__(self, admin_dashboard):
        super(ManageSchedulesPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "ManageSchedulesPage.ui"), self)

        self.admin_dashboard = admin_dashboard
        self.load_routes()
        self.load_buses()
        self.load_schedules()

        self.backButton.clicked.connect(self.go_back)
        self.addScheduleButton.clicked.connect(self.test_add_schedule)
        self.editScheduleButton.clicked.connect(self.edit_schedule)
        self.cancelScheduleButton.clicked.connect(self.cancel_schedule)

    def go_back(self):
        self.close()
        self.admin_dashboard.refresh_dashboard()
        self.admin_dashboard.show()

    def load_routes(self):
        self.routeComboBox.clear()

        cur.execute("""
            SELECT RouteID, Origin, Destination
            FROM Routes
            WHERE Status = 'Active'
            ORDER BY Origin
        """)

        routes = cur.fetchall()

        for route in routes:
            route_id = route[0]
            origin = route[1]
            destination = route[2]

            self.routeComboBox.addItem(
                f"{origin} → {destination}",
                route_id
            )

    def load_buses(self):

        self.busComboBox.clear()

        cur.execute("""
            SELECT BusID, RegistrationNumber, BusName, Capacity
            FROM Buses
            WHERE Status = 'Active'
            ORDER BY BusName
        """)

        buses = cur.fetchall()

        for bus in buses:
            bus_id = bus[0]
            registration = bus[1]
            bus_name = bus[2]
            capacity = bus[3]

            self.busComboBox.addItem(
                f"{bus_name} ({registration}) - {capacity} seats",
                bus_id
            )

    def add_schedule(self):

        route_id = self.routeComboBox.currentData()
        bus_id = self.busComboBox.currentData()

        departure = self.departureDateTime.dateTime().toString(
            "yyyy-MM-dd HH:mm:ss"
        )

        arrival = self.arrivalDateTime.dateTime().toString(
            "yyyy-MM-dd HH:mm:ss"
        )

        fare = self.fareInput.text().strip()

        if route_id is None or bus_id is None:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please select a route and a bus."
            )
            return

        try:
            fare = float(fare)

            if fare <= 0:
                QMessageBox.warning(
                    self,
                    "Invalid Fare",
                    "Ticket fare must be greater than zero."
                )
                return

        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Fare",
                "Please enter a valid ticket fare."
            )
            return

        departure_datetime = self.departureDateTime.dateTime().toPyDateTime()
        arrival_datetime = self.arrivalDateTime.dateTime().toPyDateTime()

        if departure_datetime <= datetime.now():
            QMessageBox.warning(
                self,
                "Invalid Departure",
                "Departure must be in the future."
            )
            return

        if arrival_datetime <= departure_datetime:
            QMessageBox.warning(
                self,
                "Invalid Arrival",
                "Arrival must be after departure."
            )
            return

        try:

            # Check whether this bus has an overlapping active schedule
            editing_schedule_id = getattr(self, "editing_schedule_id", None)

            cur.execute("""
                SELECT COUNT(*)
                FROM Schedules
                WHERE BusID = ?
                AND ScheduleStatus = 'Active'
                AND DepartureTime < ?
                AND ArrivalTime > ?
                AND (? IS NULL OR ScheduleID != ?)
            """, (
                bus_id,
                arrival,
                departure,
                editing_schedule_id,
                editing_schedule_id
            ))

            if cur.fetchone()[0] > 0:
                QMessageBox.warning(
                    self,
                    "Bus Already Scheduled",
                    "This bus already has another active schedule "
                    "during this time period. Please choose another time or bus."
                )
                return

            if hasattr(self, "editing_schedule_id"):

                cur.execute("""
                    UPDATE Schedules
                    SET RouteID = ?,
                        BusID = ?,
                        DepartureTime = ?,
                        ArrivalTime = ?,
                        Fare = ?
                    WHERE ScheduleID = ?
                """, (
                    route_id,
                    bus_id,
                    departure,
                    arrival,
                    fare,
                    self.editing_schedule_id
                ))

                del self.editing_schedule_id

                self.addScheduleButton.setText("+ Add Schedule")

                message = "The bus schedule has been updated successfully."
                title = "Schedule Updated"

            else:

                cur.execute("""
                    INSERT INTO Schedules
                    (RouteID, BusID, DepartureTime, ArrivalTime, Fare)
                    VALUES (?, ?, ?, ?, ?)
                """, (route_id, bus_id, departure, arrival, fare))

                message = "The bus schedule has been added successfully."
                title = "Schedule Added"

            db.commit()

            QMessageBox.information(self, title, message)

            self.fareInput.clear()
            self.load_schedules()

        except sqlite3.Error as error:

            db.rollback()

            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not save schedule.\n{error}"
            )

    def load_schedules(self):

        cur.execute("""
            SELECT
                Schedules.ScheduleID,
                Routes.Origin || ' → ' || Routes.Destination,
                Buses.BusName,
                Schedules.DepartureTime,
                Schedules.ArrivalTime,
                Schedules.Fare,
                Schedules.ScheduleStatus
            FROM Schedules
            JOIN Routes ON Schedules.RouteID = Routes.RouteID
            JOIN Buses ON Schedules.BusID = Buses.BusID
            ORDER BY Schedules.ScheduleID DESC
        """)

        schedules = cur.fetchall()

        self.schedulesTable.setRowCount(len(schedules))

        for row_index, schedule in enumerate(schedules):

            for column_index, value in enumerate(schedule):

                if column_index in (3, 4):
                    formatted_date = datetime.strptime(
                        value, "%Y-%m-%d %H:%M:%S"
                    ).strftime("%d/%m/%Y %I:%M %p")

                    item = QTableWidgetItem(formatted_date)

                elif column_index == 5:
                    item = QTableWidgetItem(f"₦{value:,.2f}")

                else:
                    item = QTableWidgetItem(str(value))

                self.schedulesTable.setItem(
                    row_index,
                    column_index,
                    item
                )

    def test_add_schedule(self):
        try:
            self.add_schedule()

        except Exception:
            QMessageBox.critical(
                self,
                "Error",
                traceback.format_exc()
            )

    def edit_schedule(self):

        selected_row = self.schedulesTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Schedule Selected",
                "Please select a schedule you want to edit."
            )
            return

        schedule_id = self.schedulesTable.item(selected_row, 0).text()
        cur.execute("""
            SELECT COUNT(*)
            FROM Bookings
            WHERE ScheduleID = ?
        """, (schedule_id,))

        booking_count = cur.fetchone()[0]

        if booking_count > 0:
            QMessageBox.warning(
                self,
                "Schedule Cannot Be Edited",
                "This schedule already has bookings. "
                "To protect existing passenger bookings and tickets, "
                "it cannot be edited."
            )
            return

        cur.execute("""
            SELECT RouteID, BusID, DepartureTime, ArrivalTime, Fare
            FROM Schedules
            WHERE ScheduleID = ?
        """, (schedule_id,))

        schedule = cur.fetchone()

        if schedule:
            route_id = schedule[0]
            bus_id = schedule[1]

            self.routeComboBox.setCurrentIndex(
                self.routeComboBox.findData(route_id)
            )

            self.busComboBox.setCurrentIndex(
                self.busComboBox.findData(bus_id)
            )

            departure = datetime.strptime(
                schedule[2], "%Y-%m-%d %H:%M:%S"
            )

            arrival = datetime.strptime(
                schedule[3], "%Y-%m-%d %H:%M:%S"
            )

            self.departureDateTime.setDateTime(departure)
            self.arrivalDateTime.setDateTime(arrival)

            self.fareInput.setText(str(schedule[4]))

            self.editing_schedule_id = schedule_id

            self.addScheduleButton.setText("Save Changes")

    def cancel_schedule(self):

        selected_row = self.schedulesTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Schedule Selected",
                "Please select a schedule you want to cancel."
            )
            return

        schedule_id = self.schedulesTable.item(selected_row, 0).text()

        cur.execute("""
            SELECT ScheduleStatus, DepartureTime
            FROM Schedules
            WHERE ScheduleID = ?
        """, (schedule_id,))

        result = cur.fetchone()

        if result is None:
            QMessageBox.warning(
                self,
                "Schedule Not Found",
                "This schedule could not be found."
            )
            return

        if result[0] == "Cancelled":
            QMessageBox.information(
                self,
                "Already Cancelled",
                "This schedule has already been cancelled."
            )
            return

        # Check whether departure time has passed
        departure_time = datetime.strptime(
            result[1],
            "%Y-%m-%d %H:%M:%S"
        )

        if departure_time <= datetime.now():
            QMessageBox.warning(
                self,
                "Cancellation Not Allowed",
                "This schedule has already departed."
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Confirm Cancellation",
            "Are you sure you want to cancel this schedule?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirmation == QMessageBox.Yes:

            try:
                cur.execute("""
                    UPDATE Schedules
                    SET ScheduleStatus = 'Cancelled'
                    WHERE ScheduleID = ?
                    AND ScheduleStatus = 'Active'
                """, (schedule_id,))

                if cur.rowcount == 0:
                    db.rollback()
                    QMessageBox.warning(
                        self,
                        "Cancellation Failed",
                        "This schedule can no longer be cancelled."
                    )
                    return

                db.commit()

                QMessageBox.information(
                    self,
                    "Schedule Cancelled",
                    "The schedule has been cancelled successfully."
                )

                self.load_schedules()

            except sqlite3.Error as error:
                db.rollback()

                QMessageBox.critical(
                    self,
                    "Database Error",
                    f"Could not cancel schedule.\n{error}"
                )


class ManageBusesPage(QWidget):
    def __init__(self, admin_dashboard):
        super(ManageBusesPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "ManageBusespage.ui"), self)

        self.admin_dashboard = admin_dashboard
        self.load_buses()

        self.backButton.clicked.connect(self.go_back)
        self.addBusButton.clicked.connect(self.add_bus)
        self.editBusButton.clicked.connect(self.edit_bus)
        self.deactivateBusButton.clicked.connect(self.deactivate_bus)

    def go_back(self):
        self.close()
        self.admin_dashboard.refresh_dashboard()
        self.admin_dashboard.show()
    def load_buses(self):

        cur.execute("""
            SELECT
                BusID,
                RegistrationNumber,
                BusName,
                Capacity,
                BusType,
                Status
            FROM Buses
            ORDER BY BusID DESC
        """)

        buses = cur.fetchall()

        self.busesTable.setRowCount(len(buses))

        for row_index, bus in enumerate(buses):

            for column_index, value in enumerate(bus):
                item = QTableWidgetItem(str(value))

                self.busesTable.setItem(
                    row_index,
                    column_index,
                    item
                )

    def add_bus(self):

        registration = self.registrationInput.text().strip().upper()
        bus_name = self.busNameInput.text().strip()
        capacity = self.capacityInput.text().strip()
        bus_type = self.busTypeComboBox.currentText()

        if not registration or not bus_name or not capacity:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please fill in all fields."
            )
            return

        try:
            capacity = int(capacity)

            if capacity <= 0:
                QMessageBox.warning(
                    self,
                    "Invalid Capacity",
                    "Seat capacity must be greater than zero."
                )
                return

        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid Capacity",
                "Please enter a valid whole number for capacity."
            )
            return

        try:

            if hasattr(self, "editing_bus_id"):

                cur.execute("""
                    UPDATE Buses
                    SET RegistrationNumber = ?,
                        BusName = ?,
                        Capacity = ?,
                        BusType = ?
                    WHERE BusID = ?
                """, (
                    registration,
                    bus_name,
                    capacity,
                    bus_type,
                    self.editing_bus_id
                ))

                del self.editing_bus_id

                self.addBusButton.setText("+ Add Bus")

                title = "Bus Updated"
                message = "The bus details have been updated successfully."

            else:

                cur.execute("""
                    INSERT INTO Buses
                    (RegistrationNumber, BusName, Capacity, BusType)
                    VALUES (?, ?, ?, ?)
                """, (registration, bus_name, capacity, bus_type))

                title = "Bus Added"
                message = "The bus has been added successfully."

            db.commit()

            QMessageBox.information(self, title, message)

            self.registrationInput.clear()
            self.busNameInput.clear()
            self.capacityInput.clear()

            self.load_buses()

        except sqlite3.IntegrityError:
            db.rollback()

            QMessageBox.warning(
                self,
                "Duplicate Registration",
                "A bus with this registration number already exists."
            )

        except sqlite3.Error as error:
            db.rollback()

            QMessageBox.critical(
                self,
                "Database Error",
                f"Could not save bus.\n{error}"
            )

    def edit_bus(self):

        selected_row = self.busesTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Bus Selected",
                "Please select a bus you want to edit."
            )
            return

        bus_id = self.busesTable.item(selected_row, 0).text()

        cur.execute("""
            SELECT RegistrationNumber, BusName, Capacity, BusType, Status
            FROM Buses
            WHERE BusID = ?
        """, (bus_id,))

        bus = cur.fetchone()

        if bus:
            self.registrationInput.setText(bus[0])
            self.busNameInput.setText(bus[1])
            self.capacityInput.setText(str(bus[2]))

            self.busTypeComboBox.setCurrentText(bus[3])

            self.editing_bus_id = bus_id

            self.addBusButton.setText("Save Changes")




    def deactivate_bus(self):

        selected_row = self.busesTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Bus Selected",
                "Please select a bus you want to deactivate."
            )
            return

        bus_id = self.busesTable.item(selected_row, 0).text()

        cur.execute("""
            SELECT Status
            FROM Buses
            WHERE BusID = ?
        """, (bus_id,))

        result = cur.fetchone()

        if result is None:
            QMessageBox.warning(
                self,
                "Bus Not Found",
                "This bus could not be found."
            )
            return

        if result[0] == "Inactive":
            QMessageBox.information(
                self,
                "Already Inactive",
                "This bus is already inactive."
            )
            return

        # Check for upcoming active schedules
        cur.execute("""
            SELECT COUNT(*)
            FROM Schedules
            WHERE BusID = ?
            AND ScheduleStatus = 'Active'
            AND DepartureTime > datetime('now', 'localtime')
        """, (bus_id,))

        if cur.fetchone()[0] > 0:
            QMessageBox.warning(
                self,
                "Upcoming Schedules",
                "This bus has upcoming active schedules. "
                "Cancel or reassign those schedules before deactivating the bus."
            )
            return

        confirmation = QMessageBox.question(
            self,
            "Confirm Deactivation",
            "Are you sure you want to deactivate this bus?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if confirmation == QMessageBox.Yes:

            try:
                cur.execute("""
                    UPDATE Buses
                    SET Status = 'Inactive'
                    WHERE BusID = ?
                    AND Status = 'Active'
                """, (bus_id,))

                if cur.rowcount == 0:
                    db.rollback()
                    QMessageBox.warning(
                        self,
                        "Deactivation Failed",
                        "This bus can no longer be deactivated."
                    )
                    return

                db.commit()

                QMessageBox.information(
                    self,
                    "Bus Deactivated",
                    "The bus has been deactivated successfully."
                )

                self.load_buses()

            except sqlite3.Error as error:
                db.rollback()

                QMessageBox.critical(
                    self,
                    "Database Error",
                    f"Could not deactivate bus.\n{error}"
                )


class ManageBookingsPage(QWidget):
    def __init__(self, admin_dashboard):
        super(ManageBookingsPage, self).__init__()

        loadUi(os.path.join(BASE_DIR, "ManageBookingsPage.ui"), self)

        self.admin_dashboard = admin_dashboard
        self.load_bookings()

        self.backButton.clicked.connect(self.go_back)
        self.searchInput.textChanged.connect(self.filter_bookings)
        self.statusFilterComboBox.currentTextChanged.connect(
            self.filter_bookings
        )
        self.refreshButton.clicked.connect(self.refresh_bookings)
        self.viewBookingButton.clicked.connect(self.view_booking)
        self.cancelBookingButton.clicked.connect(self.cancel_booking)

    def go_back(self):
        self.close()
        self.admin_dashboard.refresh_dashboard()
        self.admin_dashboard.show()

    def load_bookings(self):
        cur.execute("""
            SELECT
                Bookings.BookingID,
                Passengers.FullName,
                Passengers.Email,
                Routes.Origin || ' → ' || Routes.Destination,
                DATE(Schedules.DepartureTime),
                TIME(Schedules.DepartureTime),
                Bookings.SeatNumber,
                Schedules.Fare,
                Bookings.BookingStatus
            FROM Bookings
            JOIN Passengers
                ON Bookings.PassengerID = Passengers.PassengerID
            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID
            JOIN Routes
                ON Schedules.RouteID = Routes.RouteID
            ORDER BY Bookings.BookingID DESC
        """)

        bookings = cur.fetchall()

        self.bookingsTable.setRowCount(len(bookings))

        for row_index, booking in enumerate(bookings):
            for column_index, value in enumerate(booking):

                if column_index == 7:
                    value = f"₦{value:,.2f}"

                item = QTableWidgetItem(str(value))
                self.bookingsTable.setItem(
                    row_index,
                    column_index,
                    item
                )

    def search_bookings(self):
        search_text = self.searchInput.text().strip()

        cur.execute("""
            SELECT
                Bookings.BookingID,
                Passengers.FullName,
                Passengers.Email,
                Routes.Origin || ' → ' || Routes.Destination,
                DATE(Schedules.DepartureTime),
                TIME(Schedules.DepartureTime),
                Bookings.SeatNumber,
                Schedules.Fare,
                Bookings.BookingStatus
            FROM Bookings
            JOIN Passengers
                ON Bookings.PassengerID = Passengers.PassengerID
            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID
            JOIN Routes
                ON Schedules.RouteID = Routes.RouteID
            WHERE
                CAST(Bookings.BookingID AS TEXT) LIKE ?
                OR Passengers.FullName LIKE ?
                OR Passengers.Email LIKE ?
            ORDER BY Bookings.BookingID DESC
        """, (
            f"%{search_text}%",
            f"%{search_text}%",
            f"%{search_text}%"
        ))

        bookings = cur.fetchall()

        self.bookingsTable.setRowCount(len(bookings))

        for row_index, booking in enumerate(bookings):
            for column_index, value in enumerate(booking):

                if column_index == 7:
                    value = f"₦{value:,.2f}"

                item = QTableWidgetItem(str(value))
                self.bookingsTable.setItem(row_index, column_index, item)

    def filter_bookings(self):
        search_text = self.searchInput.text().strip()
        status = self.statusFilterComboBox.currentText()

        query = """
            SELECT
                Bookings.BookingID,
                Passengers.FullName,
                Passengers.Email,
                Routes.Origin || ' → ' || Routes.Destination,
                DATE(Schedules.DepartureTime),
                TIME(Schedules.DepartureTime),
                Bookings.SeatNumber,
                Schedules.Fare,
                Bookings.BookingStatus
            FROM Bookings
            JOIN Passengers
                ON Bookings.PassengerID = Passengers.PassengerID
            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID
            JOIN Routes
                ON Schedules.RouteID = Routes.RouteID
            WHERE (
                CAST(Bookings.BookingID AS TEXT) LIKE ?
                OR Passengers.FullName LIKE ?
                OR Passengers.Email LIKE ?
            )
        """

        parameters = [
            f"%{search_text}%",
            f"%{search_text}%",
            f"%{search_text}%"
        ]

        if status != "All Bookings":
            query += " AND Bookings.BookingStatus = ?"
            parameters.append(status)

        query += " ORDER BY Bookings.BookingID DESC"

        cur.execute(query, parameters)
        bookings = cur.fetchall()

        self.bookingsTable.setRowCount(len(bookings))

        for row_index, booking in enumerate(bookings):
            for column_index, value in enumerate(booking):

                if column_index == 7:
                    value = f"₦{value:,.2f}"

                item = QTableWidgetItem(str(value))
                self.bookingsTable.setItem(row_index, column_index, item)

    def refresh_bookings(self):
        self.searchInput.clear()
        self.statusFilterComboBox.setCurrentIndex(0)
        self.load_bookings()

    def view_booking(self):
        selected_row = self.bookingsTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Booking Selected",
                "Please select a booking you want to view."
            )
            return

        booking_id = self.bookingsTable.item(selected_row, 0).text()

        cur.execute("""
            SELECT
                Bookings.BookingID,
                Passengers.FullName,
                Passengers.Email,
                Passengers.PhoneNumber,
                Routes.Origin,
                Routes.Destination,
                Schedules.DepartureTime,
                Schedules.ArrivalTime,
                Bookings.SeatNumber,
                Schedules.Fare,
                Bookings.BookingStatus,
                Tickets.ReferenceCode,
                Tickets.IssueDate
            FROM Bookings
            JOIN Passengers
                ON Bookings.PassengerID = Passengers.PassengerID
            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID
            JOIN Routes
                ON Schedules.RouteID = Routes.RouteID
            LEFT JOIN Tickets
                ON Bookings.BookingID = Tickets.BookingID
            WHERE Bookings.BookingID = ?
        """, (booking_id,))

        booking = cur.fetchone()

        if booking is None:
            QMessageBox.warning(
                self,
                "Booking Not Found",
                "The selected booking could not be found."
            )
            return

        details = (
            f"Booking ID: {booking[0]}\n"
            f"Passenger: {booking[1]}\n"
            f"Email: {booking[2]}\n"
            f"Phone: {booking[3] or 'Not provided'}\n\n"
            f"Origin: {booking[4]}\n"
            f"Destination: {booking[5]}\n"
            f"Departure: {booking[6]}\n"
            f"Arrival: {booking[7]}\n"
            f"Seat: {booking[8]}\n"
            f"Fare: ₦{booking[9]:,.2f}\n"
            f"Status: {booking[10]}\n\n"
            f"Ticket Reference: {booking[11] or 'Not issued'}\n"
            f"Issue Date: {booking[12] or 'Not available'}"
        )

        QMessageBox.information(
            self,
            "Booking Details",
            details
        )

    def cancel_booking(self):
        selected_row = self.bookingsTable.currentRow()

        if selected_row < 0:
            QMessageBox.warning(
                self,
                "No Booking Selected",
                "Please select a booking you want to cancel."
            )
            return

        booking_id = self.bookingsTable.item(selected_row, 0).text()

        cur.execute("""
            SELECT
                Bookings.BookingStatus,
                Schedules.DepartureTime
            FROM Bookings
            JOIN Schedules
                ON Bookings.ScheduleID = Schedules.ScheduleID
            WHERE Bookings.BookingID = ?
        """, (booking_id,))

        booking = cur.fetchone()

        if booking is None:
            QMessageBox.warning(
                self,
                "Booking Not Found",
                "The selected booking could not be found."
            )
            return

        if booking[0] == "Cancelled":
            QMessageBox.information(
                self,
                "Already Cancelled",
                "This booking has already been cancelled."
            )
            return
        departure_time = datetime.strptime(
            booking[1],
            "%Y-%m-%d %H:%M:%S"
        )

        if departure_time <= datetime.now():
            QMessageBox.warning(
                self,
                "Cancellation Not Allowed",
                "This booking cannot be cancelled because the departure time has passed."
            )
            return

        reply = QMessageBox.question(
            self,
            "Confirm Cancellation",
            f"Are you sure you want to cancel booking #{booking_id}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            cur.execute("""
                UPDATE Bookings
                SET BookingStatus = 'Cancelled'
                WHERE BookingID = ?
                AND BookingStatus = 'Confirmed'
            """, (booking_id,))
            if cur.rowcount == 0:
                db.rollback()
                QMessageBox.warning(
                    self,
                    "Cancellation Failed",
                    "This booking can no longer be cancelled."
                )
                return

            db.commit()

            QMessageBox.information(
                self,
                "Booking Cancelled",
                "The booking has been cancelled successfully."
            )

            self.filter_bookings()
# APPLICATION STARTUP
if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = LoginWindow()
    window.show()
    sys.exit(app.exec_())
    

