import logging
from dataclasses import dataclass, field
from dotenv import load_dotenv
import os
import json
import asyncio

from livekit import rtc, api
from livekit.agents import (Agent, AgentSession, JobContext, RoomInputOptions, RunContext, WorkerOptions, cli, get_job_context, function_tool)
from livekit.plugins import cartesia, deepgram, google, noise_cancellation, silero


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("vikram-agent")

load_dotenv(".env.local")

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
if not outbound_trunk_id:
    raise ValueError("SIP_OUTBOUND_TRUNK_ID is not set in the environment variables.")

async def hangup_call():
    logger.info("Hanging up the call.")
    job_ctx = get_job_context()
    try:
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=job_ctx.room.name)
        )
    except Exception as e:
        logger.error(f"Error hanging up call: {e}")

# Dataclass for State Management
@dataclass
class CallState:
    prospect_name: str | None = None
    is_interested: bool = False
    motivation: str | None = None
    timeline: str | None = None
    objections: list[str] = field(default_factory=list)

class GreetingAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are Vikram, an expert realtor with HomeLife Miracle Realty.
            Your current task is to start the cold call.
            1. Greet the user enthusiastically.
            2. Confirm their name if you have it.
            3. Check if it's a good time to chat for a moment.
            4. Deliver your concise, engaging value proposition: "I help people like you find their dream home or sell their property for top value in today's competitive Toronto market."
            5. Your goal is to get a neutral or positive response to proceed to the next step.
            Speak at a brisk but natural pace (~140-150 words per minute).
            Example: "Hi, this is Abhinav with HomeLife Miracle Realty. Is this [Contact_Name]? Got a quick moment to chat?"
            """
        )
    
    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions="Greet the user, introduce yourself, and deliver your soft pitch.")

    @function_tool()
    async def detected_answering_machine(self, context: RunContext[CallState]):
        logger.info("Answering machine detected. Leaving a message and hanging up.")
        await context.session.generate_reply(
            instructions="""Leave a brief, friendly message: "Hi, this is Abhinav from HomeLife Miracle Realty. I was calling to discuss the real estate market. I'll try again another time. Thanks!" After saying this, you will hang up."""
        )
        if context.session.current_speech:
            await context.session.current_speech.wait_for_playout()
        await hangup_call()

    @function_tool()
    async def proceed_to_qualification(self, context: RunContext[CallState]):
        logger.info("Handoff from Greeting to Qualification")
        return "Great!", QualificationAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to GoodbyeAgent.")
        return "Of course. Thanks for your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class QualificationAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""You are Abhinav, an expert realtor. Your current task is to qualify the lead.
            Ask 1-2 critical, open-ended questions to uncover potential interest in buying or selling.
            - "Have you thought about buying or selling a home in the next 3-6 months, or are you happy where you are?"
            - "If you were to move, where would you go next, and what's driving that idea?"
            - "On a scale of 1-10, how motivated are you to explore home buying or selling right now?"
            Listen carefully to their response to determine if they are interested, have an objection, or are not interested at all.""",
            chat_ctx=chat_ctx,
        )

    @function_tool()
    async def prospect_is_interested(self, context: RunContext[CallState], motivation: str, timeline: str):
        logger.info(f"Prospect is interested. Motivation: {motivation}, Timeline: {timeline}")
        context.userdata.is_interested = True
        context.userdata.motivation = motivation
        context.userdata.timeline = timeline
        return "That's fantastic!", ClosingAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def prospect_has_objection(self, context: RunContext[CallState], objection: str):
        logger.info(f"Prospect has an objection: {objection}")
        context.userdata.objections.append(objection)
        return "I understand.", ObjectionHandlerAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def prospect_not_interested(self, context: RunContext[CallState]):
        logger.info("Prospect is not interested.")
        return "I appreciate your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)
    
    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to GoodbyeAgent.")
        return "No problem. I appreciate your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class ObjectionHandlerAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""You are Abhinav, an expert realtor. Your current task is to handle objections.
            Respond empathetically to the user's concerns. Ask follow-up questions to understand their specific worries.
            - If "I'm not interested": "I hear you. May I ask if you're happy with your current home, or is there something specific holding you back from considering a move?"
            - If "The market's too high": "I get that concern. Are you worried about affordability, or is it about finding a home that fits your budget? I can share strategies..."
            - If "I'm working with another realtor": "That's great! What's working well with them, and is there any area where I could add value?"
            Your goal is to resolve the objection and steer the conversation back towards qualification.""",
            chat_ctx=chat_ctx,
        )
    
    @function_tool()
    async def objection_resolved(self, context: RunContext[CallState]):
        logger.info("Objection resolved, returning to qualification.")
        return "Does that make sense?", QualificationAgent(chat_ctx=self.session._chat_ctx)
    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to Goodbye Agent.")
        return "I understand. Thank you for your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class ClosingAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""You are Abhinav, an expert realtor. Your current task is to close for an appointment.
            The prospect has shown interest. Your goal is to schedule a 15-minute consultation.
            Use an assumptive close.
            Example: "Based on what you've shared, I'd love to chat more about your plans and share some market insights. Are you free for a quick 15-minute call Tuesday at 10 AM?"
            If they are hesitant, offer flexibility.""",
            chat_ctx=chat_ctx,
        )
    @function_tool()
    async def meeting_scheduled(self, context: RunContext[CallState], date: str, time: str):
        logger.info(f"Meeting scheduled for {date} at {time}.")
        return f"Perfect, I've booked that for us...", GoodbyeAgent(chat_ctx=self.session._chat_ctx)
    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to GoodbyeAgent.")
        return "I understand. Let's talk another time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class GoodbyeAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""Your task is to end the call politely and professionally.
            If a meeting was booked, confirm it. If not, thank them for their time and leave the door open for future contact.
            Example (no interest): "No problem at all. Thanks for your time, [Contact Name]. I'll check in later, and feel free to reach out if you start thinking about buying or selling!""",
            chat_ctx=chat_ctx,
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions="Say goodbye to the user based on the outcome of the call."
        )
       
        if self.session.current_speech:
            await self.session.current_speech.wait_for_playout()
        await hangup_call()


async def entrypoint(ctx: JobContext):
    try:
        dial_info = json.loads(ctx.job.metadata or "{}")
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in job metadata: {ctx.job.metadata}, error: {e}")
        dial_info = {}
    
    phone_number = dial_info.get("phone_number")
    if not phone_number:
        logger.error("phone_number not found in metadata, shutting down.")
        return

    participant_identity = phone_number
    logger.info(f"starting outbound call agent for room: {ctx.room.name}, dialing: {phone_number}")
    await ctx.connect()

    logger.info("Loading VAD model...")
    vad = silero.VAD.load()
    logger.info("VAD model loaded.")

    session = AgentSession[CallState](
        llm=google.LLM(model="gemini-1.5-flash"),
        stt=deepgram.STT(model="nova-3", language="en-US"),
        tts=cartesia.TTS(model="sonic-english", voice="6f84f4b8-58a2-430c-8c79-688dad597532"),
        vad=vad,
        userdata=CallState(),
    )

    session_started = asyncio.create_task(
        session.start(
            agent=GreetingAgent(),
            room=ctx.room,
            room_input_options=RoomInputOptions(noise_cancellation=noise_cancellation.BVCTelephony()),
        )
    )

    try:
        logger.info(f"dialing sip participant: {phone_number}")
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_identity,
                wait_until_answered=True, 
            )
        )
        logger.info("sip participant answered")
    except api.TwirpError as e:
        logger.error(f"error creating SIP participant: {e.message}, SIP status: {e.metadata.get('sip_status')}")
        ctx.shutdown()
        return

    await session_started
    participant = await ctx.wait_for_participant(identity=participant_identity)
    logger.info(f"participant joined: {participant.identity}")

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="vikram-outbound-caller",
        num_idle_processes=1,
        load_threshold=float('inf'),
    ))