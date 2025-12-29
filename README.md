The Smart Silo Monitoring System is an Engineering Lab (EL) group project designed to address common challenges in traditional grain storage systems—specifically the lack of real-time inventory visibility and environmental monitoring.

The system provides a desktop-based monitoring solution that tracks silo fill levels along with internal temperature and humidity, enabling informed decision-making and reducing the risk of spoilage and post-harvest losses.

🎯 Problem Statement

Conventional grain silos do not provide:

Real-time information about remaining grain quantity

Continuous monitoring of temperature and humidity

Historical data to analyze trends and storage conditions

This often leads to delayed interventions, inefficient inventory management, and potential grain spoilage.

⚙️ System Description

The system integrates sensor data acquisition with a Python-based graphical interface:

An ultrasonic sensor measures the distance to the grain surface to estimate silo fill level.

DHT11 sensors monitor internal temperature and humidity.

Sensor readings are processed and displayed in real time on a desktop application.

Data is stored in an SQLite database for logging and analysis.

Matplotlib graphs visualize historical trends.

Threshold-based alerts notify the user when environmental limits are exceeded.

The application is designed to be simple, visual, and suitable for low-connectivity environments.

🛠️ Tech Stack

Programming Language: Python

GUI: Tkinter

Database: SQLite

Visualization: Matplotlib

Hardware: ESP32, Ultrasonic Sensor (HC-SR04), DHT11

👥 Team & Contribution

This project was developed as a group Engineering Lab project.
My contributions focused on:

Designing and implementing the Python desktop application

Creating the database schema and data logging logic

Developing real-time visualizations and alert mechanisms

Integrating sensor data with the software workflow

🚀 Future Scope

Integration of additional sensors (CO₂, gas, pest detection)

Predictive analytics using machine learning for spoilage detection

Mobile application support

Multi-silo monitoring and networked deployment

📚 Academic Context

This project was developed as part of the Engineering Lab curriculum at RV College of Engineering, emphasizing practical application of programming, embedded systems, and data visualization concepts.
