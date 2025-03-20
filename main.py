from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import os
import uuid
from mistralai import Mistral
from loguru import logger
#load the .env file
from dotenv import load_dotenv
load_dotenv()

# Create the FastAPI app
app = FastAPI(title="List Your Problems API")

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with specific origin in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DB_NAME = "problems.db"

def load_models():
    # Initialize models and components
    api_key = os.getenv("MISTRAL_API_KEY")
    client = Mistral(api_key=api_key)
    return client

mistral_client = load_models()

def get_mistral_response(problem, model="mistral-large-latest"):
    #This function is going to output only a YES or a NO from the Mistral Model. 
    #The job of the model is to determine if the problem that the user has posted isn't something obscene or racist or sexist or bad (to a huge degree). 
    #The model will only output a YES or a NO. 
    messages = [
        {
            "role" : "system",
            "content" : """You are a helpful assistant that determines if the given statement is obscene, racist, sexist, or offensive or not (to a huge degree). You will output a YES if it passes the test
            i.e it is not obscene, racist, sexist, or offensive to anyone. You will output a NO if it can potentially be obscene, racist, sexist, or offensive to anyone.
            Also output NO to obviously stupid jokes and statments which are calling me (Prateek) names or are just crass jokes which are not worth storing in the database and are obviously not real problems.
            Again you need to output only YES or NO."""
        },
        {
            "role": "user", "content": problem
        }
    ]
    chat_response = mistral_client.chat.complete(
        model=model,
        messages=messages
    )
    return (chat_response.choices[0].message.content)
def init_db():
    """Initialize the database if it doesn't exist."""
    if not os.path.exists(DB_NAME):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        #add uuid column to the table. 
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem TEXT NOT NULL,
            name TEXT DEFAULT 'Anonymous',
            email TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT NOT NULL
        )
        ''')
        conn.commit()
        conn.close()

# Call the init_db function when the application starts
init_db()

# Define the data model
class ProblemEntry(BaseModel):
    problem: str
    name: str = "Anonymous"
    email: str = ""

class ProblemResponse(BaseModel):
    id: int
    problem: str
    name: str
    created_at: str

# Endpoint to add a new problem entry
@app.post("/add_entry")
async def add_entry(entry: ProblemEntry):
    """Add a new problem entry to the database."""
    if not entry.problem.strip():
        raise HTTPException(status_code=400, detail="Problem description cannot be empty")
    
    # Convert UUID to string before inserting
    uuid_str = str(uuid.uuid4())
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        logger.info(f"Adding entry: {entry.problem}")
        mistral_response = get_mistral_response(entry.problem)
        logger.info(f"Mistral response: {mistral_response}")
        if mistral_response.upper() == "YES":
            cursor.execute(
                "INSERT INTO problems (problem, name, email, uuid) VALUES (?, ?, ?, ?)",
                (entry.problem, entry.name, entry.email, uuid_str)  # Now using uuid_str instead of uuid4
            )
            conn.commit()
            return {"status": "success", "message": "Entry added successfully"}
        else:
            logger.info(f"Entry not added because it was flagged as potentially offensive: {entry.problem}")
            return {"status": "error", "message": "Entry not added because it was flagged as potentially offensive"}
    except Exception as e:
        conn.rollback()
        logger.error(f"{str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

# Endpoint to get all entries
@app.get("/get_all_entries")
async def get_all_entries():
    """Retrieve all problem entries from the database."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT id, problem, name, created_at FROM problems ORDER BY created_at DESC"
        )
        entries = cursor.fetchall()
        
        # Convert the sqlite3.Row objects to dictionaries
        result = []
        for entry in entries:
            result.append({
                "id": entry["id"],
                "problem": entry["problem"],
                "name": entry["name"],
                "created_at": entry["created_at"]
            })
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

#Now make a dev endpoint for deleting an entry with a given uuid. 
@app.delete("/delete_entry/{uuid}")
async def delete_entry(uuid: str):
    """Delete an entry from the database with the given UUID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM problems WHERE uuid = ?", (uuid,))
        conn.commit()
        return {"status": "success", "message": "Entry deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()

#Now make a dev endpoint for getting all the data in the database in a json format. 
@app.get("/get_all_data_Prateek")
async def get_all_data():
    """Get all data from the database in a JSON format."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM problems")
        entries = cursor.fetchall()
        return [dict(row) for row in entries]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    finally:
        conn.close()



    




# Run the application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="localhost", port=8000)