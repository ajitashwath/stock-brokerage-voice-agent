import asyncio
import os
import json
import time
from dotenv import load_dotenv
from livekit import api

AGENT_NAME = "vikram-outbound-caller"

PHONE_NUMBER_TO_CALL = "+918825526326"


async def main():
    load_dotenv(".env")
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    ws_url = os.getenv("LIVEKIT_URL") 

    if not all([api_key, api_secret, ws_url]):
        raise ValueError("LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL must be set in your .env file")

  
    http_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")
    print(f"Connecting to LiveKit at {http_url}...")
    lkapi = api.LiveKitAPI(url=http_url, api_key=api_key, api_secret=api_secret)

    room_name = f"outbound-call-{int(time.time())}"
    print(f"Using unique room name: {room_name}")

    metadata = json.dumps({
        "phone_number": PHONE_NUMBER_TO_CALL
    })
    print(f"Dispatching job with metadata: {metadata}")

    try:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name=AGENT_NAME,
                room=room_name,
                metadata=metadata
            )
        )
        print("\nDispatch created successfully!")
        print(f"Dispatch ID: {dispatch.id}")
        print(f"Agent Name: {dispatch.agent_name}")
        print(f"Room Name: {dispatch.room}")
    except Exception as e:
        print(f"\nError creating dispatch: {e}")
    finally:
        await lkapi.aclose()

if __name__ == "__main__":
    asyncio.run(main())