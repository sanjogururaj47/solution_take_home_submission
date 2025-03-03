# Forward Deployed Engineer Take Home - Submission, Sanjog Gururaj

## Overview

Implemented the chatbot with flights, hotels, and transfers (apparently they don't have rental car options?)

Oh, and thought i'd respond with my own recommendation. The first thing that came to mind when I heard "Amadeus":

[![Cool Movie](https://img.youtube.com/vi/awqqTGI4B-c/0.jpg)](https://www.youtube.com/watch?v=awqqTGI4B-c)


## Installation

### Prerequisites

Make sure to **clone** and not fork this repo. You can do this by clicking the `Code` button and selecting `Download ZIP`, or copy the path, and run:

```bash
git clone https://github.com/...
```

Ensure you have python, node, and npm installed. 
Would **recommend** using a virtual environment to install the dependencies.

```bash
python -m venv .
source bin/activate
```

Then cd into the project directory:

```bash
cd solution_take_home_submission 
```

### Backend

Navigate to the backend directory and install the dependencies:

```bash
cd backend
pip install -r requirements.txt
```

### Frontend

Navigate to the frontend directory and install the dependencies:

```bash
cd frontend
npm install
```

### Running the application
To run the client, navigate to /frontend and run:

```bash
npm start
```

To run the server, open a new terminal and navigate to /backend and run:

**Important**: You need to generate the access token for the Amadeus API. Before running the server, run the following command:

```bash
python app/amadeus_access_token_refresh.py
```

Remember to activate the virtual environment in the new terminal.

Then run the server and refresh the webpage:

```bash
uvicorn app.main:app --reload
```

This will attach the access token to the .env file. It expires every 30 mins, so if you encounter an ambiguous error, try running the command again. Then restarting the server.

## Problem Statement

How can Brainbase interface with live travel data and behave as a real life travel agent would?

## Assumptions

- The user is booking a flight for themselves.
- Users details are already stored, and known by the agent
- Because we are using the Amadeus testAPI sometimes the hotel names and properties are not real (sometimes for flights, too)