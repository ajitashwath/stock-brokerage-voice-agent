<a href="https://livekit.io/">
  <img src="./.github/assets/livekit-mark.png" alt="LiveKit logo" width="100" height="100">
</a>

# Outbound Stock Brokerage Caller - Python (LiveKit Agent)

A complete outbound sales calling system built with [LiveKit Agents for Python](https://github.com/livekit/agents). This agent makes cold calls for investment opportunities with a sophisticated multi-stage conversation flow.

## Features

### Multi-Agent Sales Pipeline
- **GreetingAgent**: Professional introduction and soft pitch delivery
- **QualificationAgent**: Uncovers investment potential through targeted questions
- **ObjectionHandlerAgent**: Handles common sales objections with empathy
- **ClosingAgent**: Schedules consultations using assumptive closing techniques
- **GoodbyeAgent**: Professional call conclusion and follow-up commitment

### Advanced Capabilities
- **Outbound SIP Calling**: Automated dialing through LiveKit SIP infrastructure
- **Answering Machine Detection**: Leaves appropriate messages and hangs up
- **State Management**: Tracks prospect information throughout the call
- **Dynamic Agent Handoffs**: Seamless transitions between conversation stages
- **Call Analytics**: Integrated metrics and logging for performance tracking

### Technical Stack
- **LLM**: Google Gemini 1.5 Flash for natural conversation
- **STT**: Deepgram Nova-3 for accurate speech recognition
- **TTS**: Cartesia Sonic with professional voice selection
- **VAD**: Silero VAD for precise speech detection
- **Noise Cancellation**: LiveKit Cloud BVC Telephony enhancement

## Agent Conversation Flow

```
GreetingAgent
    ↓ (interested)
QualificationAgent
    ↓ (objection)          ↓ (interested)         ↓ (not interested)
ObjectionHandlerAgent → ClosingAgent        →  GoodbyeAgent
    ↓ (resolved)           ↓ (scheduled)
QualificationAgent   →   GoodbyeAgent
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env.local` and configure:

```bash
# LiveKit Configuration
LIVEKIT_URL=wss://your-livekit-instance.com
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# SIP Configuration (Required for outbound calling)
SIP_OUTBOUND_TRUNK_ID=your_sip_trunk_id

# AI Service APIs
OPENAI_API_KEY=your_openai_key  # Optional, using Google Gemini
DEEPGRAM_API_KEY=your_deepgram_key
CARTESIA_API_KEY=your_cartesia_key
```

### SIP Trunk Setup

This agent requires a configured SIP trunk for outbound calling:
1. Set up a SIP trunk in your LiveKit Cloud dashboard
2. Configure your SIP provider credentials
3. Ensure outbound calling is enabled
4. Add the trunk ID to `SIP_OUTBOUND_TRUNK_ID`

## Installation & Setup

1. **Install Dependencies**
   ```bash
   cd agent-starter-python
   uv sync
   ```

2. **Download Required Models**
   ```bash
   uv run python src/agent.py download-files
   ```

3. **Load Environment (Optional)**
   ```bash
   lk app env -w .env.local
   ```

## Running the Agent

### Development Mode
```bash
uv run python src/agent.py dev
```

### Production Mode
```bash
uv run python src/agent.py start
```

### Making Test Calls

Use the included `call.py` script to initiate outbound calls:

```bash
# Edit the phone number in src/call.py
PHONE_NUMBER_TO_CALL = "+1234567890"

# Run the test call
uv run python src/call.py
```

The script will:
- Validate your SIP configuration
- Create a room for the call
- Dispatch the agent
- Initiate the outbound call

## Agent Behavior

### Sales Script Highlights

**Greeting Phase**:
- Professional introduction as "Jordan from Stratton Oakmont"
- Confirms contact name and availability
- Delivers value proposition about Indian stock market opportunities

**Qualification Questions**:
- Current investment status (SIPs, direct equity)
- Financial goals (5-10 year timeline)
- Risk appetite assessment (1-10 scale)

**Objection Handling**:
- Market volatility concerns → SIP diversification benefits
- Insufficient capital → Low minimum investment options
- Market inexperience → Educational support and guidance

**Closing Strategy**:
- Assumptive close for 15-minute consultation
- Flexible scheduling options
- No-obligation positioning

## Frontend Integration

While designed for outbound calling, this agent can work with frontend applications:

| Platform | Repository | Description |
|----------|------------|-------------|
| **Web** | [`livekit-examples/agent-starter-react`](https://github.com/livekit-examples/agent-starter-react) | React & Next.js integration |
| **Mobile** | [`livekit-examples/agent-starter-flutter`](https://github.com/livekit-examples/agent-starter-flutter) | Cross-platform mobile app |
| **iOS** | [`livekit-examples/agent-starter-swift`](https://github.com/livekit-examples/agent-starter-swift) | Native iOS application |

## Compliance & Ethics
This sales calling system should be used in compliance with:
- Local telemarketing regulations
- Do Not Call registry requirements
- GDPR/privacy regulations where applicable
- Industry-specific compliance standards

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
