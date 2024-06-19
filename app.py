import os
from dotenv import load_dotenv
from flask import Flask, render_template, request
from mindsdb_sdk.utils.mind import create_mind
from openai import OpenAI
import json
import logging
import time

# Configure logging to ignore Werkzeug's default logging messages
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)
ts = str(int(time.time()))

# Load environment variables from a .env file
load_dotenv()

# Get the MindsDB API Key from the environment variables
mindsdb_api_key = os.getenv('MINDSDB_API_KEY')

#define base url
base_url = os.getenv('MINDSDB_API_URL', "https://llm.mdb.ai")
if base_url.endswith("/"):
    base_url = base_url[:-1]


# If the MindsDB API Key is not found, print an error message and exit
if not mindsdb_api_key:
    print("Please create a .env file and add your MindsDB API Key")
    exit()


# Create a Flask application instance
app = Flask(__name__, static_folder='static', template_folder='templates')

# Create an instance of the OpenAI client with the MindsDB API Key and endpoint
client = OpenAI(
   api_key=mindsdb_api_key,
   base_url=base_url
)

# create an assistant
assistant = client.beta.assistants.create(
    name="Math Tutor",
    instructions="You are a personal math tutor. Write and run code to answer math questions.",
    tools=[{"type": "code_interpreter"}],
    model="gpt-4o",
)
print(f"Assistant successfully created: {assistant}")

# crate a thread
thread = client.beta.threads.create()
print(f"Thread successfully created: {thread}")

# Define the route for the home page
@app.route('/')
def index():
    return render_template('index.html')  # Render the index.html template

# Define the route for sending a message
@app.route('/get', methods=['POST'])
def get():
    messages = client.beta.threads.messages.list(
        thread_id=thread.id
    )
    res = []
    for message in messages.data:
        res.append({"role":message.role, "content": getText(message.content)})
    return res

# Define the route for sending a message
@app.route('/send', methods=['POST'])
def send():
    res = []
    message = request.form['message']  # Get the message from the form
    try:
        # add a messge to the thread
        message = client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=message
        )

        # create run and retrieve status
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=assistant.id,
        )
        # get messages or status
        if run.status == 'completed': 
            # Get all messages from thread
            messages = client.beta.threads.messages.list(
                thread_id=thread.id
            )
            res.append({
                        "role": "assistant", 
                        "content": getText(messages.data[-1].content)
                    })
            
        else:
            print(run.status)

        
    except Exception as e:
        # Handle different types of errors and append error messages to the res list
        if 'code' in e:
            if e.code == 401:
                res.append({"role": "error", "content": "Invalid MindsDB API Key, please verify your API key and update your .env file."})
            if e.code == 429:
                res.append({"role": "error", "content": "You have reached your message limit of 10 requests per minute per IP and, at most, 4 requests per IP in a 10-second period.  Please refer to the documentation for more details or contact us to raise your request limit."})
            elif e.code == 500:
                res.append({"role": "error", "content": "Internal system error. Please try again later."})
        else:
            res.append({"role": "error", "content": "Internal system error. Please try again later."})
    
    return res

@app.route('/delete-thread', methods=['POST'])
def delete():
    global thread
    # delete thread
    print(f"Deleting thread: {thread.id}")
    client.beta.threads.delete(thread.id)
    # crate a new thread
    print(f"Creating new thread")
    thread = client.beta.threads.create()
    print(f"Thread successfully created: {thread}")
    return {'status':'ok'}

def getText(content):
    # Iterate content of last message to find a TextContentBlock element 
    for element in content:
        if element.__class__.__name__ == 'TextContentBlock':
            return element.text.value

# Run the Flask application
if __name__ == '__main__':
    print("App Running on 127.0.0.1:8000")
    app.run(port=8000, debug=False)
