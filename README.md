# Digital Document Organizer

A web-based document management application developed using Python Flask, HTML, CSS, JavaScript and SQLite. It helps users upload, organize, search, download, rename and delete their digital documents from a single dashboard.

## Project Overview

Managing digital documents across different folders can become difficult and time-consuming. The Digital Document Organizer provides a simple interface to store and manage documents efficiently using categories and search functionality.

## Features

- **Document Upload:** Upload PDF, DOC, DOCX, TXT, PNG, JPG and JPEG files.
- **Document Categorization:** Organize files into Education, Personal, Certificates, Finance, Work and Other categories.
- **Document Search:** Find documents using their filenames.
- **Category Filter:** Filter documents based on their categories.
- **Download Documents:** Download previously uploaded files.
- **Rename Documents:** Change document names while preserving their file extensions.
- **Delete Documents:** Remove documents from the application.
- **Dashboard:** View document statistics and manage files from one place.
- **Database Storage:** Store document details using SQLite.

## Technologies Used

| Technology | Purpose |
|---|---|
| Python | Backend programming |
| Flask | Web application framework |
| HTML | Web page structure |
| CSS | Styling and layout |
| JavaScript | Frontend interactions |
| SQLite | Database management |
| VS Code | Development environment |
| Git and GitHub | Version control |

## Project Structure

```text
Digital-Document-Organizer/
│
├── app.py
├── .gitignore
├── README.md
│
├── templates/
│   └── index.html
│
├── static/
│   └── style.css
│
├── uploads/
├── documents.db
└── venv/
```

Note: The local database, uploaded documents and virtual environment are excluded from GitHub through `.gitignore`. They are created locally when the application is run.

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/Alekhya-1236/Digital-Document-Organizer.git
```

### 2. Open the project folder

```bash
cd Digital-Document-Organizer
```

### 3. Create a virtual environment

```bash
python -m venv venv
```

### 4. Activate the virtual environment

For Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\venv\Scripts\Activate.ps1
```

### 5. Install Flask

```bash
pip install Flask
```

### 6. Run the application

```bash
python app.py
```

### 7. Open in your browser

```text
http://127.0.0.1:5000
```

## Database

The application uses SQLite to store document metadata, including:

- Document ID
- Original filename
- Stored filename
- Category
- File type
- File size
- Upload date

## Future Enhancements

- User authentication and login
- Cloud storage integration
- Document preview
- Advanced sorting and filtering
- Improved security and access control
- Responsive mobile interface

## Author

**Alekhya A**

Artificial Intelligence and Machine Learning Student

GitHub: [Alekhya-1236](https://github.com/Alekhya-1236)

## Project Status

Developed as an academic course project using the Software Engineering and System Design approach.
