# Image Requirements for Voice MCP Article

This document lists all the screenshots/images you need to capture for the article "Give Your AI Agent a Voice: Building a Voice-Enabled MCP for Hands-Free Development"

## Required Screenshots

### 📸 Image 1: Roo Using the ask_user Tool
**Location in article:** After the "How It Works: Architecture" section  
**What to capture:** Screenshot of Roo's interface showing the `ask_user` tool being called  
**Details to show:**
- The tool call in Roo's UI
- The question being asked
- The tool name "ask_user" visible
- Optional: Show the MCP server connection status

**How to capture:**
1. Have VoiceMCP configured and running in Roo
2. Ask Roo something that triggers it to use `ask_user`
3. Capture the moment when the tool is invoked in the UI

---

### 📸 Image 2: Voice Confirmation Flow
**Location in article:** After the "AskUser Tool with Confirmation Loop" code section  
**What to capture:** Screenshot showing the complete confirmation flow in Roo's conversation  
**Details to show:**
- Initial question asked
- User's voice response (transcribed)
- Confirmation question ("I heard: ... Is this correct?")
- User's confirmation ("Yes")
- Agent proceeding with the answer

**How to capture:**
1. Trigger a voice interaction with `ask_user`
2. Respond to the question
3. Respond to the confirmation
4. Screenshot the complete conversation thread showing all steps

---

### 📸 Image 3: Windows Audio Recording Indicator
**Location in article:** After the "Audio Processing: Recording and Transcription" section  
**What to capture:** Screenshot of Windows showing audio recording is active  
**Details to show:**
- Windows taskbar with microphone icon active, OR
- Windows Sound settings showing recording levels, OR
- NAudio recording visualization (if available)

**How to capture:**
1. Start a voice interaction that triggers recording
2. Open Windows Sound settings (right-click speaker icon → Sound settings → Input)
3. Screenshot showing the microphone level bars moving while you speak
4. OR capture Windows taskbar showing mic is active

---

### 📸 Image 4: Roo MCP Configuration
**Location in article:** After the "Configuration in Roo" section  
**What to capture:** Screenshot of Roo's MCP configuration UI or the mcp.json file  
**Details to show:**
- VoiceMCP server listed and active
- The server configuration (command, args)
- `alwaysAllow` settings visible
- Timeout setting visible
- **IMPORTANT:** Sanitize any API keys or sensitive endpoints

**How to capture:**
1. Open your `.roo/mcp.json` file in an editor
2. Or open Roo's MCP server settings UI
3. Screenshot showing VoiceMCP is configured
4. Before sharing, replace sensitive data with placeholders

---

### 📸 Image 5: Complete Conversation Example
**Location in article:** In the "Real-World Usage: The Driving Scenario" section  
**What to capture:** Screenshot of a full voice interaction showing the practical use case  
**Details to show:**
- Agent asking about a code decision (e.g., "Which approach would you prefer?")
- Your voice response transcribed
- Confirmation loop
- Agent proceeding with implementation

**Suggested scenario to capture:**
1. Ask Roo to refactor some code
2. Have it encounter a decision point
3. It should use `ask_user` to ask you which approach to take
4. Screenshot the entire conversation showing:
   - The code context
   - The question
   - Your answer
   - Confirmation
   - Agent continuing with your choice

---

## Optional Images

### 📸 Optional Image: Driving Setup
**Location in article:** Introduction section  
**What to show:** Your actual setup for voice interaction while driving  
**Details:**
- Phone with ChatGPT open (showing you already use voice AI)
- Car audio system showing Bluetooth connection
- NOT while actually driving (safety first - take photo while parked)

**Only include if:**
- You're comfortable sharing this
- It adds value to the "driving home" story
- You can capture it safely while parked

---

## Image Format Guidelines

- **Format:** PNG or JPEG
- **Resolution:** At least 1200px width for clarity
- **File naming:** Use descriptive names like:
  - `roo-voice-mcp-ask-user-tool.png`
  - `voice-confirmation-flow.png`
  - `windows-audio-recording.png`
  - `roo-mcp-config.png`
  - `complete-voice-conversation.png`

- **Privacy:** 
  - Sanitize any API keys
  - Replace your actual Azure endpoint with `[your-resource].openai.azure.com`
  - Remove any personal/company code if visible
  - Consider blurring background windows if they contain sensitive info

---

## Where to Add Images in the Article

The article currently has 5 placeholder comments marked with `[📸 TODO: ...]`. Replace each placeholder with your actual image using this format:

```markdown
![Alt text description](path/to/image.png)
*Caption explaining what the image shows*
```

For example:
```markdown
![Roo using the ask_user MCP tool](assets/images/roo-voice-ask-user.png)
*Roo calling the ask_user tool to get voice input from the developer*
```

---

## Testing Checklist

Before capturing screenshots:

- [ ] VoiceMCP is built and configured in Roo
- [ ] Azure OpenAI credentials are set up correctly
- [ ] Microphone is working and selected as default
- [ ] Speakers/audio output is working
- [ ] You've tested a complete voice interaction successfully
- [ ] Roo's conversation history shows the tool calls clearly

---

## Tips for Good Screenshots

1. **Clean up your screen** - Close unnecessary windows
2. **Increase font size** - Make code/text readable in screenshots
3. **Use light theme** - Usually photographs better than dark theme
4. **Capture at key moments** - Right when the tool is being used
5. **Show enough context** - Include surrounding UI elements for clarity
6. **Test the image** - Make sure it's clear and legible when viewing at article width

---

## Questions?

If any screenshot requirement is unclear, or if you'd like to modify what should be captured, let me know!