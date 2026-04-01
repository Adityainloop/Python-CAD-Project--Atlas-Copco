# 🤖 AI-Assisted CAD Assembly System

Intelligent Multi-Part CAD Assembly using Geometry + Natural Language

🧠 Project Overview

This project is an AI-assisted CAD automation system that can automatically assemble multiple mechanical components from STEP files using:

Geometric feature detection (holes, shafts, planes)
Transformation mathematics (rotation + translation)
Natural language instructions (e.g., "insert shaft into bore", "place hopper on top of frame")

Unlike traditional CAD tools like SolidWorks or Fusion 360, where assembly is manual, this system automates the entire process.

🎯 Key Capabilities
🔹 Geometry Understanding
Detects:
Cylinders (shaft / hole)
Planes (flat surfaces)
Bounding boxes
Extracts:
Axis direction
Diameter
Position (center)
Surface area
🔹 Intelligent Assembly Engine

Supports:

✅ Shaft → Hole insertion
✅ Axis alignment (rotation using vector math)
✅ Translation with depth offset
✅ Multi-part sequential assembly
✅ Assembly hierarchy (parent-child relationships)

🔹 Natural Language Driven Assembly

Example prompts:

insert shaft into bore
place support frame on top of table frame
mount bearing beside shaft

🔹 Export & Visualization
Export formats:
STEP
STL
IGES
3D Viewer:
Powered by OpenCascade via pythonOCC
Integrated PyQt viewer

🛠️ Tech Stack
Python 3.11 (Conda Environment)
pythonOCC 7.7.1 (OpenCascade CAD Kernel)
Tkinter (GUI)
PyQt5 (3D Viewer)
NumPy (Vector Math)
Claude API (Optional AI Prompt Engine)

⚙️ Core Assembly Algorithm
Pipeline:
STEP Files
   ↓
Geometry Analysis
   ↓
Feature Detection (holes, shafts, planes)
   ↓
Prompt Parsing (NLP → operations)
   ↓
Rotation (axis alignment)
   ↓
Translation (positioning)
   ↓
Assembly Hierarchy Execution
   ↓
Export + Visualization


🧪 Real-World Test Case
🔧 Shredder Machine Assembly

This system is tested on a multi-part industrial shredder assembly including: (Still in testing phase currently)

Table Frame
Support Frame
Hexagonal Shaft
Bearings
Bearing Covers
Blades + Spacers
Fixed Blade
Upper Hopper
Lower Hopper

Total: 11+ complex mechanical parts

Steps to run:

Upload STEP files
Enter assembly instructions (optional)
Run assembly
View result in 3D
Export assembled model

💡 Why This Project Matters

This project sits at the intersection of:

Mechanical Engineering
CAD Automation
AI / NLP
Computational Geometry

It aims to solve a real industry problem:

👉 Reducing manual CAD assembly effort

🚀 Future Vision (Industry-Level Goals)
Full constraint-based assembly system (like CAD mates)
ML-based feature recognition
Plugin for CAD tools (Fusion / SolidWorks)
Real-time assembly suggestions
Complete multi-part automation

👨‍💻 Author

Aditya Dalvi
SY Engineering Student
VIT Pune

⭐ Status

🚧 Advanced Prototype → Moving toward Industry-Level System
