import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

try:
    if os.getenv("GOOGLE_API_KEY"):
        print("✅Gemini API Key loaded from .env file.")
        print(os.getenv('GOOGLE_API_KEY'))
    else:
        print("❌GOOGLE API KEY is not found!")
    
except Exception as e:
    print(f"🔑Setup Error: Details {e}")


from google.adk.agents import Agent
from google.adk.runners import InMemoryRunner
from google.adk.tools import google_search
from google.genai import types

retry_config=types.HttpRetryOptions(
    attempts=3,
    exp_base=2,
    initial_delay=1,
    http_status_codes=[429,500,503,504]
)

root_agent = Agent(
    model='gemini-2.0-flash-lite',
    name='root_agent',
    description='A helpful assistant for user questions.',
    instruction='Answer user questions to the best of your knowledge',
    tools=[google_search]
)
print("✅Agent is Created")

#<-----------runner------------->

runner = None
session_id = None

async def setup():
    global runner, session_id
    runner = InMemoryRunner(agent=root_agent)
    session = await runner.session_service.create_session(
        app_name=runner.app_name,
        user_id="user",
    )
    session_id = session.id

async def ask(prompt: str) -> str:
    response_text = ""
    async for event in runner.run_async(
        user_id="user",
        session_id=session_id,
        new_message=types.Content(
            role="user",
            parts=[types.Part(text=prompt)]
        )
    ):
        if event.is_final_response():
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
    return response_text