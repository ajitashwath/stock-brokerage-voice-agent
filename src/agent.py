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
logger = logging.getLogger("jordan-agent")

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
    guest_name: str | None = None
    is_interested: bool = False
    investment_goals: str | None = None
    risk_appetite: str | None = None
    investment_experience: str | None = None
    objections: list[str] = field(default_factory=list)

class GreetingAgent(Agent):
    def __init__(self):
        super().__init__(
            instructions="""You are Jordan, a senior market analyst with Stratton Oakmont.
            Your current task is to start the cold call.
            1. Greet the user warmly and professionally.
            2. Confirm their name if you have it.
            3. Check if it's a good time to chat for a moment.
            4. Deliver your concise, engaging value proposition: "I'm calling from Stratton Oakmont, and I help investors like you explore high-growth opportunities in the Indian stock market to build long-term wealth."
            5. Your goal is to get a neutral or positive response to proceed to the next step.
            Speak at a brisk but natural pace (~140-150 words per minute).
            Example: "Hello, am I speaking with [Contact_Name]? This is Jordan from Stratton Oakmont. Do you have a moment to discuss how you can benefit from the current market trends?"
            """
        )
    
    async def on_enter(self) -> None:
        await self.session.generate_reply(instructions="Greet the user, introduce yourself, and deliver your soft pitch.")

    @function_tool()
    async def detected_answering_machine(self, context: RunContext[CallState]):
        logger.info("Answering machine detected. Leaving a message and hanging up.")
        await context.session.generate_reply(
            instructions="""Leave a brief, friendly message: "Hello, this is Jordan from Stratton Oakmont. I was calling to discuss some exciting investment opportunities in the Indian market. I'll try again another time. Thank you!" After saying this, you will hang up."""
        )
        if context.session.current_speech:
            await context.session.current_speech.wait_for_playout()
        await hangup_call()

    @function_tool()
    async def proceed_to_qualification(self, context: RunContext[CallState]):
        logger.info("Handoff from Greeting to Qualification")
        return "Excellent!", QualificationAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to GoodbyeAgent.")
        return "Of course. Thank you for your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class QualificationAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""You are Jordan, a senior market analyst. Your current task is to qualify the lead.
            Ask 1-2 critical, open-ended questions to uncover their investment potential.
            - "Are you currently investing in the stock market, perhaps through SIPs or direct equity?"
            - "What are your financial goals for the next 5-10 years? Are you thinking about retirement, a big purchase, or wealth creation?"
            - "On a scale of 1-10, how would you describe your risk appetite when it comes to investments?"
            Listen carefully to their response to determine if they are interested, have an objection, or are not interested at all.""",
            chat_ctx=chat_ctx,
        )

    @function_tool()
    async def prospect_is_interested(self, context: RunContext[CallState], investment_goals: str, risk_appetite: str, investment_experience: str = ""):
        logger.info(f"Prospect is interested. Goals: {investment_goals}, Risk Appetite: {risk_appetite}, Experience: {investment_experience}")
        context.userdata.is_interested = True
        context.userdata.investment_goals = investment_goals
        context.userdata.risk_appetite = risk_appetite
        context.userdata.investment_experience = investment_experience
        return "That's great to hear!", ClosingAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def prospect_has_objection(self, context: RunContext[CallState], objection: str):
        logger.info(f"Prospect has an objection: {objection}")
        context.userdata.objections.append(objection)
        return "I understand your concern.", ObjectionHandlerAgent(chat_ctx=self.session._chat_ctx)

    @function_tool()
    async def prospect_not_interested(self, context: RunContext[CallState]):
        logger.info("Prospect is not interested.")
        return "I appreciate your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)
    
    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to GoodbyeAgent.")
        return "No problem at all. Thank you for your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class ObjectionHandlerAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""You are Jordan, a senior market analyst. Your current task is to handle objections.
            Respond empathetically to the user's concerns. Ask follow-up questions to understand their specific worries.
            - If "The market is too risky/volatile": "I understand that the market has its ups and downs. That's why we focus on a diversified portfolio and long-term strategies to mitigate risk. Have you considered Systematic Investment Plans or 'SIPs' to average out your investments over time?"
            - If "I don't have enough money to invest": "That's a common concern. The great thing about the Indian market is that you can start small. We have options that allow you to begin investing with just a few thousand rupees a month."
            - If "I'm not familiar with the stock market": "Not a problem at all. Part of my job is to guide you. We provide clear and simple advice, and we can start with some basic, well-researched options to get you comfortable."
            Your goal is to resolve the objection and steer the conversation back towards qualification.""",
            chat_ctx=chat_ctx,
        )
    
    @function_tool()
    async def objection_resolved(self, context: RunContext[CallState]):
        logger.info("Objection resolved, returning to qualification.")
        return "Does that sound better?", QualificationAgent(chat_ctx=self.session._chat_ctx)
    
    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to Goodbye Agent.")
        return "I understand completely. Thank you for your time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class ClosingAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""You are Jordan, a senior market analyst. Your current task is to close for a consultation.
            The prospect has shown interest. Your goal is to schedule a 15-minute consultation to discuss their financial goals and a personalized investment strategy.
            Use an assumptive close.
            Example: "Based on what you've told me, I'm confident we can help you achieve your financial goals. I'd like to schedule a 15-minute, no-obligation call to discuss a personalized investment plan. Would tomorrow at 4 PM work for you?"
            If they are hesitant, offer flexibility and emphasize the no-obligation nature of the call.""",
            chat_ctx=chat_ctx,
        )
    
    @function_tool()
    async def consultation_scheduled(self, context: RunContext[CallState], date: str, time: str):
        logger.info(f"Consultation scheduled for {date} at {time}.")
        return f"Excellent, I've scheduled that consultation for us...", GoodbyeAgent(chat_ctx=self.session._chat_ctx)
    
    @function_tool()
    async def end_call(self, context: RunContext[CallState]):
        logger.info("User requested to end call. Handing off to GoodbyeAgent.")
        return "I understand. We can connect another time.", GoodbyeAgent(chat_ctx=self.session._chat_ctx)


class GoodbyeAgent(Agent):
    def __init__(self, chat_ctx):
        super().__init__(
            instructions="""Your task is to end the call politely and professionally.
            If a consultation was booked, confirm it. If not, thank them for their time and leave the door open for future contact.
            Example (no interest): "Not a problem at all. Thank you for your time, [Contact Name]. I'll send you a follow-up email with my contact information in case you'd like to discuss investment opportunities in the future. Have a great day!" """,
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
        agent_name="jordan-outbound-caller",
        num_idle_processes=1,
        load_threshold=float('inf'),
    ))