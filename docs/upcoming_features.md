# Upcoming Features

## Feature: Agentic AI Installer (v2.0)

**Priority**: High  
**Complexity**: Medium-High  
**Estimated Effort**: 2-3 days  
**Prerequisites**: LM Studio integration (already complete)

---

### Overview

Transform the current "narrator" AI installer into a fully autonomous agent that can:

- Analyze system state
- Decide what commands to run
- Execute commands directly
- Handle errors automatically
- Provide true "hand-holding" installation experience

### Current State (v1.0)

```
User runs setup.bat/sh
        ↓
Hardcoded Python steps execute
        ↓
AI comments on what's happening
        ↓
If error → AI explains, user must fix manually
```

### Target State (v2.0)

```
User runs setup.bat/sh
        ↓
AI Agent enters control loop:
  1. Analyze current state
  2. Decide next action
  3. Ask user permission (optional)
  4. Execute command
  5. Check result
  6. If error → AI decides fix, loops back to step 3
  7. If success → next step
        ↓
Installation complete (AI handled everything)
```

---

### Architecture

#### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    AgenticInstaller                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │   StateAnalyzer  │    │   ActionDecider  │               │
│  │   - system_info  │    │   - next_action  │               │
│  │   - check_deps   │    │   - fix_error    │               │
│  │   - detect_errors│    │   - validate     │               │
│  └────────┬─────────┘    └────────┬─────────┘               │
│           │                       │                          │
│           └───────────┬───────────┘                          │
│                       ↓                                      │
│              ┌─────────────────┐                             │
│              │   CommandRunner │                             │
│              │   - whitelist   │                             │
│              │   - execute     │                             │
│              │   - capture_out │                             │
│              └────────┬────────┘                             │
│                       ↓                                      │
│              ┌─────────────────┐                             │
│              │   SafetyGuards  │                             │
│              │   - confirm_ui  │                             │
│              │   - rollback    │                             │
│              │   - retry_limit │                             │
│              └─────────────────┘                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### Class Structure

```python
# agentic_installer.py

class StateAnalyzer:
    """Gathers information about the current system state."""
    
    def get_full_state(self) -> dict:
        """Returns comprehensive system state."""
        return {
            "os": platform.system(),
            "python_version": sys.version,
            "python_installed": self.check_python(),
            "docker_installed": self.check_docker(),
            "docker_running": self.check_docker_running(),
            "venv_exists": self.check_venv(),
            "dependencies_installed": self.check_deps(),
            "ports_available": self.check_ports([3000, 8000, 5435, 6343, 6380]),
            "disk_space_gb": self.get_disk_space(),
            "ram_gb": self.get_ram(),
            "last_error": self.last_error,
            "completed_steps": self.completed_steps,
        }


class ActionDecider:
    """Uses LLM to decide what action to take next."""
    
    def __init__(self, lm_studio_url: str, model: str):
        self.url = lm_studio_url
        self.model = model
        self.system_prompt = self._load_agent_prompt()
    
    def decide_next_action(self, state: dict) -> Action:
        """Ask LLM what to do next given current state."""
        prompt = f"""
        Current installation state:
        {json.dumps(state, indent=2)}
        
        What is the next action to take? Respond in JSON format:
        {{
            "action": "run_command" | "ask_user" | "complete" | "abort",
            "command": "the command to run (if applicable)",
            "explanation": "what this does in plain English",
            "risk_level": "safe" | "moderate" | "dangerous"
        }}
        """
        response = self._call_llm(prompt)
        return Action.from_json(response)
    
    def decide_error_fix(self, error: str, state: dict) -> Action:
        """Ask LLM how to fix an error."""
        prompt = f"""
        An error occurred:
        {error}
        
        Current state:
        {json.dumps(state, indent=2)}
        
        How should I fix this? Respond in JSON format.
        """
        return Action.from_json(self._call_llm(prompt))


class CommandRunner:
    """Executes commands with safety checks."""
    
    # Only these commands can be run
    WHITELIST_PATTERNS = [
        r"^python -m venv",
        r"^pip install",
        r"^docker compose",
        r"^docker pull",
        r"^docker ps",
        r"^apt update",
        r"^apt install python3",
        r"^brew install",
        r"^winget install",
        r"^git clone",
    ]
    
    # These are NEVER allowed
    BLACKLIST_PATTERNS = [
        r"rm -rf",
        r"del /",
        r"format",
        r"mkfs",
        r"dd if=",
        r"> /dev/",
        r"chmod 777",
        r"curl .* \| bash",
        r"wget .* \| sh",
    ]
    
    def execute(self, command: str, confirm: bool = True) -> CommandResult:
        """Execute a command if it passes safety checks."""
        if not self._is_safe(command):
            return CommandResult(
                success=False,
                error="Command blocked by safety filter"
            )
        
        if confirm:
            if not self._get_user_confirmation(command):
                return CommandResult(success=False, error="User declined")
        
        return self._run_subprocess(command)


class SafetyGuards:
    """Prevents runaway AI and enables recovery."""
    
    MAX_RETRIES = 3
    MAX_TOTAL_COMMANDS = 50
    CONFIRM_MODES = ["always", "moderate_and_above", "dangerous_only", "never"]
    
    def __init__(self, confirm_mode: str = "moderate_and_above"):
        self.confirm_mode = confirm_mode
        self.command_count = 0
        self.retry_count = {}
        self.command_history = []
    
    def should_confirm(self, action: Action) -> bool:
        """Determine if user confirmation is needed."""
        if self.confirm_mode == "always":
            return True
        if self.confirm_mode == "never":
            return False
        if self.confirm_mode == "dangerous_only":
            return action.risk_level == "dangerous"
        # moderate_and_above
        return action.risk_level in ["moderate", "dangerous"]
    
    def can_retry(self, step: str) -> bool:
        """Check if we can retry a failed step."""
        return self.retry_count.get(step, 0) < self.MAX_RETRIES
    
    def record_command(self, command: str, result: CommandResult):
        """Track command history for potential rollback."""
        self.command_history.append({
            "command": command,
            "result": result,
            "timestamp": datetime.now().isoformat()
        })


class AgenticInstaller:
    """Main agent loop."""
    
    def __init__(self, confirm_mode: str = "moderate_and_above"):
        self.state = StateAnalyzer()
        self.decider = ActionDecider(LM_STUDIO_URL, self._detect_model())
        self.runner = CommandRunner()
        self.safety = SafetyGuards(confirm_mode)
    
    def run(self):
        """Main agent loop."""
        print_ai("Let's get ArkhamMirror set up. I'll handle the heavy lifting.")
        
        while True:
            # 1. Analyze current state
            current_state = self.state.get_full_state()
            
            # 2. Ask AI what to do next
            action = self.decider.decide_next_action(current_state)
            
            # 3. Handle the action
            if action.type == "complete":
                print_ai("That's everything. ArkhamMirror is ready to go!")
                break
            
            if action.type == "abort":
                print_ai(f"I can't continue: {action.explanation}")
                break
            
            if action.type == "ask_user":
                response = input(f"ARKHAM: {action.explanation}\nYour response: ")
                # Feed response back to AI in next loop
                continue
            
            if action.type == "run_command":
                # 4. Safety check
                should_confirm = self.safety.should_confirm(action)
                
                # 5. Show what we're about to do
                print_ai(action.explanation)
                
                # 6. Execute
                result = self.runner.execute(
                    action.command, 
                    confirm=should_confirm
                )
                
                # 7. Record for potential rollback
                self.safety.record_command(action.command, result)
                
                # 8. Handle result
                if result.success:
                    print_success(f"Done: {action.command}")
                else:
                    print_error(f"Failed: {result.error}")
                    
                    # 9. Ask AI how to fix
                    if self.safety.can_retry(action.command):
                        fix_action = self.decider.decide_error_fix(
                            result.error, 
                            current_state
                        )
                        # Next loop will try the fix
                        continue
                    else:
                        print_ai("I've tried a few times but can't get past this one. You might need to check manually.")
                        break
```

---

### User Experience Modes

#### Mode 1: Full Hand-Holding (Default for non-technical users)

```
confirm_mode = "always"
```

AI explains every command before running, user types Y to proceed.

```
ARKHAM: I'm going to create a Python virtual environment. This keeps 
ArkhamMirror's dependencies separate from your system.

Running: python -m venv venv
Continue? [Y/n] y

[OK] Virtual environment created.

ARKHAM: Now I'll install the required Python packages. This downloads 
about 2.5GB of machine learning libraries. It'll take a few minutes.

Running: pip install -r app/requirements.txt
Continue? [Y/n] y
```

#### Mode 2: Trust Mode (For confident users)

```
confirm_mode = "never"
```

AI runs everything automatically, just narrates.

```
ARKHAM: Creating your Python environment... done.
ARKHAM: Installing dependencies... this'll take a few minutes.
[████████████████████████████] 100%
ARKHAM: Starting Docker containers...
ARKHAM: All set. ArkhamMirror is at localhost:3000.
```

#### Mode 3: Smart Confirm (Balanced - recommended default)

```
confirm_mode = "moderate_and_above"
```

Safe commands run automatically, anything impactful asks first.

---

### Safety Considerations

#### Command Whitelist (things AI CAN do)

- Create Python venv
- pip install packages
- docker compose up/down
- apt/brew/winget install (specific packages only)
- git clone (ArkhamMirror repo only)
- Create directories
- Download files from trusted sources

#### Command Blacklist (NEVER allowed)

- Any form of `rm -rf` or recursive delete
- System modifications outside the project
- Network requests piped to shell
- Permission changes (chmod 777, etc.)
- Disk formatting or partitioning
- Registry edits (Windows)
- Sudo for anything not explicitly whitelisted

#### Escape Hatches

- User can always Ctrl+C to abort
- Maximum 50 commands per session
- Maximum 3 retries per step
- "abort" keyword stops everything

---

### LLM Prompt Engineering

The agent needs a carefully crafted system prompt:

```
# agent_prompt.txt

You are ARKHAM, an autonomous installation agent for ArkhamMirror.

YOUR CAPABILITIES:
- You can run commands on the user's system
- You can read command output and react to errors
- You can ask the user questions

YOUR CONSTRAINTS:
- Only use commands from the approved list
- Never run destructive commands
- Always explain what you're doing
- If unsure, ask the user

INSTALLATION GOAL:
1. Create Python venv
2. Install dependencies from requirements.txt
3. Start Docker containers (postgres, qdrant, redis)
4. Download spaCy model
5. Initialize database
6. Verify everything works

RESPONSE FORMAT:
Always respond with valid JSON:
{
    "action": "run_command" | "ask_user" | "complete" | "abort",
    "command": "the exact command",
    "explanation": "plain English for the user",
    "risk_level": "safe" | "moderate" | "dangerous"
}

EXAMPLES OF RISK LEVELS:
- safe: pip install, docker ps, python --version
- moderate: docker compose up, apt install
- dangerous: (you should never suggest these)
```

---

### Implementation Phases

#### Phase 1: Core Agent Loop (Day 1)

- [ ] Create `agentic_installer.py`
- [ ] Implement `StateAnalyzer` class
- [ ] Implement `ActionDecider` with LLM integration
- [ ] Implement `CommandRunner` with whitelist
- [ ] Basic agent loop that can complete a simple install

#### Phase 2: Safety & UX (Day 2)

- [ ] Implement `SafetyGuards` class
- [ ] Add confirmation prompts
- [ ] Add retry logic with limits
- [ ] Add command history for debugging
- [ ] Colored output and progress indicators

#### Phase 3: Error Recovery (Day 3)

- [ ] Implement error analysis prompts
- [ ] Add common error→fix mappings as examples for LLM
- [ ] Test edge cases (network failure, disk full, etc.)
- [ ] Add "ask human for help" escalation

#### Phase 4: Testing & Polish

- [ ] Test on clean Windows VM
- [ ] Test on clean Ubuntu container
- [ ] Test error recovery scenarios
- [ ] Documentation and user guide

---

### Files to Create/Modify

```
scripts/
├── ai_installer.py           # Keep as fallback (v1.0)
├── agentic_installer.py      # NEW: Full agent (v2.0)
├── prompts/
│   ├── installer_persona.txt # Existing narrator prompt
│   └── agent_prompt.txt      # NEW: Agent decision prompt
└── safety/
    ├── command_whitelist.py  # NEW: Allowed commands
    └── command_blacklist.py  # NEW: Forbidden patterns
```

---

### Success Criteria

1. **Hands-free install**: User runs setup, types Y a few times, done
2. **Error recovery**: AI automatically fixes common issues
3. **Safe**: Cannot run destructive commands even if LLM hallucinates
4. **Transparent**: User always knows what's being run
5. **Escapable**: User can abort at any time

---

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM suggests dangerous command | Whitelist + blacklist filters |
| LLM loops forever on unfixable error | Retry limits + max command count |
| User blindly approves everything | Risk warnings for moderate/dangerous |
| LLM gives wrong fix advice | Human escalation after 3 failures |
| Network issues during LLM call | Graceful fallback to v1.0 narrator |

---

### Open Questions

1. **Should we support offline mode?** (Use hardcoded steps if no LM Studio)
2. **Should the agent be able to restart Docker?** (Requires elevation)
3. **How verbose should the narration be?** (User preference?)
4. **Should we log all commands to a file?** (For debugging)

---

**Status**: Planned for post-v1.0 release  
**Last Updated**: 2025-12-12
