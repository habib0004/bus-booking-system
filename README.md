# bus-booking-system
Python-based bus transportation booking and management system built with PyQt5 and SQLite.
# Bus Transportation Booking Management System

A desktop-based bus transportation booking and management application developed using Python, PyQt5, Qt Designer and SQLite.

## Project Overview

The Bus Transportation Booking Management System is designed to simplify bus transportation operations by providing a platform where passengers can search for available journeys, select seats and manage their bookings, while administrators can manage the transportation company's operations.

The application features separate interfaces for passengers and administrators.

## Key Features

### Passenger Features
- Create a passenger account.
- Log in securely.
- Browse available routes and schedules.
- View bus journey information and fares.
- Select seats using a visual seat-selection interface.
- Make and manage bus bookings.
- View booking and ticket information.
- Receive a unique ticket reference.

### Administrator Features
- Access the administration dashboard.
- Add, edit and manage buses.
- Create and manage transportation routes.
- Create and manage bus schedules.
- Manage bookings.
- Monitor bus occupancy and booking information.
- Track booking revenue.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Application programming language |
| PyQt5 | Desktop application interface |
| Qt Designer | Interface design |
| SQLite | Database management |
| SQL | Database queries and operations |

## Database

The application uses SQLite for persistent data storage.

The database is organised around six main entities:

- Passengers
- Buses
- Routes
- Schedules
- Bookings
- Tickets

These entities manage passenger information, transportation resources, journey schedules and ticket bookings.

## Application Structure

The application uses a graphical user interface built with PyQt5 and Qt Designer.

The main Python file handles application logic, including:
- User authentication.
- Database operations.
- Passenger and administrator functionality.
- Booking management.
- Seat availability and selection.
- Input validation.

The Qt Designer `.ui` files provide the different application screens.

## Installation and Setup

### Requirements
- Python 3.x
- PyQt5

SQLite is included in Python's standard library.

### Installation

1. Clone or download this repository.

2. Install PyQt5:

```bash
pip install PyQt5
```

3. Navigate to the project directory.

4. Run the application:

```bash
python Bus_Booking_system.py
```

**Note:** The application may require its original image resources to be restored and their paths configured before all interface visuals display correctly. The Forgot Password functionality is not yet implemented.

## Project Purpose

This project was developed as a practical demonstration of Python programming, object-oriented programming, database management, desktop application development and graphical user interface design.

It provided an opportunity to apply programming concepts to a real-world transportation booking scenario.

## Author

**Habeeb Okanlawon**

Python Developer

GitHub: [habib0004](https://github.com/habib0004)
