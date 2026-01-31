"""
Game Client Simulator - Sends HTTP requests to Mantella server
Simulates the game sending commands to a running Mantella production service

How it works:
1. Game client sends requests to Mantella server via HTTP
2. For microphone input: 
   - Client sends empty string for player input
   - SERVER listens to the microphone (not the client)
   - Server transcribes speech and returns the text
3. Server generates NPC responses and synthesizes voice
4. Client receives voice files and plays them

This mimics the actual game-Mantella communication flow.
"""
import requests
import json
import logging
import csv
import soundfile as sf
import sounddevice as sd
from pathlib import Path
from src.http.communication_constants import communication_constants as comm_consts

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)


def play_audio(filename: str):
    """Play audio file synchronously"""
    try:
        data, samplerate = sf.read(filename)
        sd.play(data, samplerate)
        sd.wait()  # Wait until audio finishes
    except Exception as e:
        logging.error(f"Could not play audio: {e}")


class GameContextSimulator:
    """Simulates all game context data that Papyrus would gather."""
    
    # Simulated quest database - maps decimal FormID to (quest_name, status, stage, locations)
    # Based on actual game output for Preston Garvey
    # locations = list of "LocationName (AliasName)" strings for radiant quests (via Lighthouse extender)
    SIMULATED_QUESTS = {
        # Preston Garvey / Minutemen main quests
        1703964: ("When Freedom Calls", "completed", 0, []),  # 0x001A0038
        238679: ("The First Step", "not_started", 0, []),     # 0x0003A467
        726866: ("Taking Independence", "not_started", 0, []), # 0x000B1752
        1270569: ("Old Guns", "not_started", 0, []),          # 0x00136399
        1099338: ("Defend the Castle", "not_started", 0, []), # 0x0010C64A (note: game shows "Defend The Castle")
        776964: ("Form Ranks", "not_started", 0, []),         # 0x000BDA44
        1160046: ("Sanctuary", "completed", 0, []),           # 0x0011B06E
        1495094: ("Inside Job", "not_started", 0, []),        # 0x0016CF26
        658758: ("The Nuclear Option", "not_started", 0, []), # 0x000A0D46 (Minutemen ending)
        1082598: ("With Our Powers Combined", "not_started", 0, []), # 0x00108966
        527718: ("Out of the Fire", "not_started", 0, []),    # 0x00080D66
        1245511: ("Troubled Waters", "not_started", 0, []),   # 0x00130147
        
        # Preston Garvey radiant quests (with <Alias> placeholders and resolved locations with alias names)
        622902: ("Raider Troubles at <Alias=ActualLocation>", "running", 50, ["Outpost Zimonja (ActualLocation)", "BADTFL Regional Office (RaiderDungeon)"]),  # 0x00098136
        622903: ("Clearing the Way for <Alias=ActualLocation>", "not_started", 0, []),
        622904: ("Defend <Alias=ActualLocation>", "not_started", 0, []),
        622905: ("Defend the artillery at <Alias=ActualLocation>", "not_started", 0, []),
        622906: ("Ghoul Problem at <Alias=ActualLocation>", "not_started", 0, []),
        622907: ("<Alias=ActualLocation>: Greenskins", "not_started", 0, []),  # Super Mutant Troubles
        622908: ("Kidnapping at <Alias=ActualLocation>", "not_started", 0, []),
        622909: ("Resettle Refugees at <Alias=HostileWorkshopLocation>", "not_started", 0, []),
        622910: ("Rogue Courser at <Alias=Dungeon>", "not_started", 0, []),
        622911: ("Stop the Raiding at <Alias=ActualLocation>", "not_started", 0, []),
        622912: ("Taking Point: <Alias=HostileWorkshopLocation>", "not_started", 0, []),
        
        # Nick Valentine quests
        106457: ("Long Time Coming", "running", 100, []),
        
        # General quests
        106969: ("Out of Time", "completed", 0),
    }
    
    # Simulated player state
    PLAYER_STATE = {
        "level": 15,
        "weapon": "10mm Pistol",
        "power_armor": False,
        "sneaking": False,
        "in_combat": False,
        "health_percent": 0.85,
        "rad_percent": 0.05
    }
    
    # Simulated nearby NPCs (name, distance, role)
    NEARBY_NPCS = [
        ("Sturges", 150, "settler"),
        ("Mama Murphy", 200, "settler"),
        ("Marcy Long", 180, "settler"),
        ("Jun Long", 190, "settler"),
    ]
    
    # Simulated NPC roles for conversation participants
    NPC_ROLES = {
        "Preston Garvey": {
            "companion": True,
            "relationship": 3,  # Ally
            "faction": "minutemen",
            "essential": True
        },
        "Piper Wright": {
            "companion": True,
            "relationship": 2,  # Confidant
            "faction": "companion",
            "essential": True
        },
        "Nick Valentine": {
            "companion": True,
            "relationship": 2,
            "faction": "companion",
            "essential": True
        },
        "Sturges": {
            "companion": False,
            "relationship": 1,  # Friend
            "faction": "settler",
            "essential": False
        }
    }
    
    # Simulated location
    LOCATION = {
        "name": "Sanctuary Hills",
        "type": "settlement",
        "interior": False
    }
    
    def get_player_state_string(self) -> str:
        """Generate player state string like Papyrus would."""
        parts = [f"level:{self.PLAYER_STATE['level']}"]
        
        if self.PLAYER_STATE["weapon"]:
            parts.append(f"weapon:{self.PLAYER_STATE['weapon']}")
        if self.PLAYER_STATE["power_armor"]:
            parts.append("power_armor")
        if self.PLAYER_STATE["sneaking"]:
            parts.append("sneaking")
        if self.PLAYER_STATE["in_combat"]:
            parts.append("in_combat")
        
        return "|".join(parts)
    
    def get_nearby_npcs_string(self) -> str:
        """Generate nearby NPCs string like Papyrus would."""
        entries = []
        for name, distance, role in self.NEARBY_NPCS:
            entries.append(f"{name}:{distance}:{role}")
        return "|".join(entries)
    
    def get_npc_role_string(self, npc_name: str) -> str:
        """Generate NPC role string for a specific NPC."""
        if npc_name not in self.NPC_ROLES:
            return "relationship:0"
        
        role = self.NPC_ROLES[npc_name]
        parts = []
        
        if role.get("companion"):
            parts.append("companion")
        
        parts.append(f"relationship:{role.get('relationship', 0)}")
        
        if role.get("faction"):
            parts.append(f"faction:{role['faction']}")
        
        if role.get("essential"):
            parts.append("essential")
        
        return "|".join(parts)
    
    def get_location_string(self) -> str:
        """Generate location string like Papyrus would."""
        parts = []
        if self.LOCATION.get("name"):
            parts.append(f"name:{self.LOCATION['name']}")
        
        if self.LOCATION.get("interior"):
            parts.append("interior")
        else:
            parts.append("exterior")
        
        return "|".join(parts)
    
    def simulate_quest_check(self, quest_ids: list[int]) -> str:
        """Simulate Papyrus CheckQuestsFromFormIDs function.
        
        Format: QuestName:status[:stage][:Location1~Location2]
        Matches actual game output with Lighthouse Papyrus Extender location data.
        """
        if not quest_ids:
            return ""
        
        results = []
        for form_id in quest_ids:
            if form_id in self.SIMULATED_QUESTS:
                quest_data = self.SIMULATED_QUESTS[form_id]
                name = quest_data[0]
                status = quest_data[1]
                stage = quest_data[2]
                locations = quest_data[3] if len(quest_data) > 3 else []
                
                # Build quest entry: Name:Status[:Stage][:Location1~Location2]
                if status == "completed":
                    entry = f"{name}:completed"
                elif status == "running":
                    entry = f"{name}:running:{stage}"
                    # Add locations for running radiant quests (via Lighthouse extender)
                    if locations:
                        entry += ":" + "~".join(locations)
                else:
                    entry = f"{name}:not_started"
                
                results.append(entry)
        
        return "|".join(results)
    
    def get_full_context(self, npc_name: str, quest_ids: list[int] | None = None) -> dict:
        """Get all simulated game context values."""
        context = {
            # Player state
            comm_consts.KEY_CONTEXT_PLAYER_STATE: self.get_player_state_string(),
            "mantella_player_health_percent": self.PLAYER_STATE["health_percent"],
            "mantella_player_rad_percent": self.PLAYER_STATE["rad_percent"],
            
            # Nearby NPCs
            comm_consts.KEY_CONTEXT_NEARBY_NPCS: self.get_nearby_npcs_string(),
            
            # NPC role
            comm_consts.KEY_CONTEXT_NPC_ROLE: self.get_npc_role_string(npc_name),
            
            # Location
            comm_consts.KEY_CONTEXT_LOCATION_TYPE: self.get_location_string(),
        }
        
        # Quest context if quest IDs provided
        if quest_ids:
            quest_string = self.simulate_quest_check(quest_ids)
            if quest_string:
                context[comm_consts.KEY_CONTEXT_NPC_QUESTS] = quest_string
                logging.info(f"🎮 Quest context: {quest_string}")
        
        return context


class GameClientSimulator:
    """Simulates a game client sending HTTP requests to Mantella server"""
    
    def __init__(self, server_url: str = "http://localhost:4999"):
        """Initialize the game client simulator
        
        Args:
            server_url: Base URL of the Mantella server (default: http://localhost:4999)
        """
        self.server_url = f"{server_url}/mantella"
        self.session = requests.Session()
        self.turn_counter = 0
        self.pending_quest_context = ""  # Simulates Papyrus _pendingQuestContext
        self.game_context = GameContextSimulator()
        self.current_npc_name = ""
        self.pending_quest_ids: list[int] = []
        
    def send_request(self, request_data: dict) -> dict:
        """Send an HTTP POST request to Mantella server
        
        Args:
            request_data: The request payload to send
            
        Returns:
            The server's response as a dictionary
        """
        try:
            logging.debug(f"Sending request: {json.dumps(request_data, indent=2)}")
            response = self.session.post(
                self.server_url,
                json=request_data,
                timeout=120  # 2 minutes for mic input + STT processing
            )
            response.raise_for_status()
            response_data = response.json()
            logging.debug(f"Received response: {json.dumps(response_data, indent=2)}")
            return response_data
        except requests.exceptions.ConnectionError:
            logging.error("❌ Could not connect to Mantella server. Is it running?")
            raise
        except requests.exceptions.Timeout:
            logging.error("❌ Request timed out")
            raise
        except Exception as e:
            logging.error(f"❌ Request failed: {e}")
            raise
    
    def initialize(self) -> dict:
        """Send initialization request"""
        logging.info("Sending INIT request...")
        request = {
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_INIT
        }
        return self.send_request(request)
    
    def start_conversation(self, npc_data: dict, use_microphone: bool = False) -> dict:
        """Send start conversation request
        
        Args:
            npc_data: Dictionary containing NPC information from CSV
            use_microphone: Whether to use microphone input (server-side) or text input
            
        Returns:
            Server response
        """
        self.current_npc_name = npc_data['name']
        
        # Parse NPC data
        base_id = npc_data['base_id']
        try:
            base_id = int(base_id, 16)
        except:
            base_id = int(base_id)
        
        gender = 0
        if str(npc_data.get('gender', '')).lower() in ['female', '1', 'f']:
            gender = 1
        
        race = npc_data.get('race', 'Human')
        if not race.startswith('<') and not race.endswith('Race>'):
            race = f"<{race}Race>"
        
        # Choose input type based on config
        input_type = comm_consts.KEY_INPUTTYPE_MIC if use_microphone else comm_consts.KEY_INPUTTYPE_TEXT
        
        request = {
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_STARTCONVERSATION,
            comm_consts.KEY_STARTCONVERSATION_WORLDID: "SanctuaryHillsWorld",
            comm_consts.KEY_INPUTTYPE: input_type,
            comm_consts.KEY_ACTORS: [
                {
                    comm_consts.KEY_ACTOR_BASEID: base_id,
                    comm_consts.KEY_ACTOR_REFID: base_id,
                    comm_consts.KEY_ACTOR_NAME: npc_data['name'],
                    comm_consts.KEY_ACTOR_GENDER: gender,
                    comm_consts.KEY_ACTOR_RACE: race,
                    comm_consts.KEY_ACTOR_VOICETYPE: f"<{npc_data.get('fallout4_voice_folder', 'MaleBoston')}>",
                    comm_consts.KEY_ACTOR_ISINCOMBAT: False,
                    comm_consts.KEY_ACTOR_ISENEMY: False,
                    comm_consts.KEY_ACTOR_RELATIONSHIPRANK: 0,
                    comm_consts.KEY_ACTOR_ISPLAYER: False,
                    comm_consts.KEY_ACTOR_CUSTOMVALUES: {},
                    comm_consts.KEY_ACTOR_EQUIPMENT: {}
                },
                {
                    comm_consts.KEY_ACTOR_BASEID: 7,
                    comm_consts.KEY_ACTOR_REFID: 7,
                    comm_consts.KEY_ACTOR_NAME: "Player",
                    comm_consts.KEY_ACTOR_GENDER: 0,
                    comm_consts.KEY_ACTOR_RACE: "<HumanRace>",
                    comm_consts.KEY_ACTOR_VOICETYPE: "<MaleBoston>",
                    comm_consts.KEY_ACTOR_ISINCOMBAT: False,
                    comm_consts.KEY_ACTOR_ISENEMY: False,
                    comm_consts.KEY_ACTOR_RELATIONSHIPRANK: 0,
                    comm_consts.KEY_ACTOR_ISPLAYER: True,
                    comm_consts.KEY_ACTOR_CUSTOMVALUES: {},
                    comm_consts.KEY_ACTOR_EQUIPMENT: {}
                }
            ],
            comm_consts.KEY_CONTEXT: {
                comm_consts.KEY_CONTEXT_LOCATION: "Sanctuary Hills",
                comm_consts.KEY_CONTEXT_TIME: 12,
                comm_consts.KEY_CONTEXT_INGAMEEVENTS: [],
                comm_consts.KEY_CONTEXT_WEATHER: "Clear",
                comm_consts.KEY_CONTEXT_CUSTOMVALUES: {}
            }
        }
        
        logging.info("Sending START CONVERSATION request...")
        return self.send_request(request)
    
    def continue_conversation(self, context: dict | None = None) -> dict:
        """Send continue conversation request
        
        Args:
            context: Optional context to include (events, location, etc.)
            
        Returns:
            Server response
        """
        if context is None:
            context = {
                comm_consts.KEY_CONTEXT_LOCATION: "Sanctuary Hills",
                comm_consts.KEY_CONTEXT_TIME: 12,
                comm_consts.KEY_CONTEXT_INGAMEEVENTS: [],
                comm_consts.KEY_CONTEXT_WEATHER: "Clear",
                comm_consts.KEY_CONTEXT_CUSTOMVALUES: {}
            }
        
        # Add ALL game context (simulates BuildCustomContextValues in Papyrus)
        if comm_consts.KEY_CONTEXT_CUSTOMVALUES not in context:
            context[comm_consts.KEY_CONTEXT_CUSTOMVALUES] = {}
        
        # Get full simulated game context
        game_ctx = self.game_context.get_full_context(
            self.current_npc_name, 
            self.pending_quest_ids if self.pending_quest_ids else None
        )
        context[comm_consts.KEY_CONTEXT_CUSTOMVALUES].update(game_ctx)
        
        request = {
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_CONTINUECONVERSATION,
            comm_consts.KEY_CONTINUECONVERSATION_TOPICINFOFILE: 1,
            comm_consts.KEY_CONTEXT: context
        }
        
        return self.send_request(request)
    
    def player_input(self, player_text: str, context: dict | None = None) -> dict:
        """Send player input request
        
        Args:
            player_text: The text the player said
            context: Optional context to include
            
        Returns:
            Server response
        """
        if context is None:
            context = {
                comm_consts.KEY_CONTEXT_LOCATION: "Sanctuary Hills",
                comm_consts.KEY_CONTEXT_TIME: 12,
                comm_consts.KEY_CONTEXT_INGAMEEVENTS: [],
                comm_consts.KEY_CONTEXT_WEATHER: "Clear",
                comm_consts.KEY_CONTEXT_CUSTOMVALUES: {}
            }
        
        # Add ALL game context
        if comm_consts.KEY_CONTEXT_CUSTOMVALUES not in context:
            context[comm_consts.KEY_CONTEXT_CUSTOMVALUES] = {}
        
        game_ctx = self.game_context.get_full_context(
            self.current_npc_name,
            self.pending_quest_ids if self.pending_quest_ids else None
        )
        context[comm_consts.KEY_CONTEXT_CUSTOMVALUES].update(game_ctx)
        
        request = {
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_PLAYERINPUT,
            comm_consts.KEY_REQUESTTYPE_PLAYERINPUT: player_text,
            comm_consts.KEY_CONTEXT: context
        }
        
        logging.info(f"Sending PLAYER INPUT: '{player_text}'")
        return self.send_request(request)
    
    def end_conversation(self) -> dict:
        """Send end conversation request"""
        request = {
            comm_consts.KEY_REQUESTTYPE: comm_consts.KEY_REQUESTTYPE_ENDCONVERSATION
        }
        
        logging.info("Sending END CONVERSATION request...")
        return self.send_request(request)
    
    def process_start_response(self, response: dict) -> None:
        """Process start_conversation_completed response like Papyrus does
        
        Extracts quest IDs and stores them for later use.
        """
        if comm_consts.KEY_QUEST_IDS_TO_CHECK in response:
            quest_ids = response[comm_consts.KEY_QUEST_IDS_TO_CHECK]
            logging.info(f"📋 Received quest FormIDs to check: {quest_ids}")
            self.pending_quest_ids = quest_ids
        else:
            logging.info("📋 No quest IDs received from server")
            self.pending_quest_ids = []


def select_npc() -> dict:
    """Let user select an NPC from the CSV file"""
    npc_file = 'data/Fallout4/fallout4_characters.csv'
    npcs = []
    
    with open(npc_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['name'] and row['base_id']:
                npcs.append(row)
    
    print(f"\n📋 Found {len(npcs)} NPCs. Showing first 10:")
    for i, npc in enumerate(npcs[:10], 1):
        print(f"  {i}. {npc['name']}")
    
    choice = input(f"\n👉 Enter number (1-10), name to search, or Enter for first: ").strip()
    
    if not choice:
        selected = npcs[0]
    elif choice.isdigit():
        idx = int(choice) - 1
        selected = npcs[idx]
    else:
        # Search by name (case-insensitive)
        matches = [n for n in npcs if choice.lower() in n['name'].lower()]
        if not matches:
            print(f"❌ No NPC found matching '{choice}'")
            return select_npc()
        elif len(matches) == 1:
            selected = matches[0]
        else:
            print(f"\n🔍 Found {len(matches)} matches:")
            for i, npc in enumerate(matches[:10], 1):
                print(f"  {i}. {npc['name']}")
            sub_choice = input(f"\n👉 Select (1-{min(10, len(matches))}): ").strip()
            idx = int(sub_choice) - 1 if sub_choice else 0
            selected = matches[idx]
    
    print(f"\n✓ Selected: {selected['name']}\n")
    return selected


def get_test_events(turn: int, npc_name: str) -> list[str]:
    """Generate test events for different scenarios"""
    scenarios = {
        3: ["Preston Garvey picked up Beer Bottle", "Preston Garvey dropped Beer Bottle", 
            f"{npc_name} equipped Dirty Rags", f"{npc_name} unequipped Dirty Rags"],
        6: ["Preston Garvey picked up Wet"] * 3 + ["Preston Garvey dropped Wet"] * 2,
        9: ["Raider is attacking Player"] * 2 + ["Preston Garvey picked up Legendary Weapon", f"{npc_name} entered combat"],
        12: ["Preston Garvey picked up Stimpak", "Raider is attacking Player", "Raider is attacking Player", 
             "Preston Garvey dropped Beer", "Raider is attacking Player"],
    }
    return scenarios.get(turn, [f"Preston Garvey picked up Stimpak", f"{npc_name} equipped Leather Armor"])


def main():
    print("="*60)
    print("Game Client Simulator - Sends requests to Mantella server")
    print("="*60)
    
    # Configuration
    SERVER_URL = "http://localhost:4999"
    ENABLE_EVENT_SIMULATION = False  # Enable/disable in-game event simulation
    ENABLE_AUDIO_PLAYBACK = True     # Enable/disable audio playback
    USE_MICROPHONE = True            # True = use microphone, False = type text
    
    print(f"\n🌐 Server URL: {SERVER_URL}")
    print(f"📊 Event simulation: {'ENABLED' if ENABLE_EVENT_SIMULATION else 'DISABLED'}")
    print(f"🔊 Audio playback: {'ENABLED' if ENABLE_AUDIO_PLAYBACK else 'DISABLED'}")
    print(f"🎤 Microphone input: {'ENABLED' if USE_MICROPHONE else 'DISABLED (text input)'}")
    
    # Initialize client
    client = GameClientSimulator(SERVER_URL)
    
    # Test server connection
    try:
        print("\n🔌 Testing server connection...")
        init_response = client.initialize()
        print(f"✓ Server responded: {init_response.get(comm_consts.KEY_REPLYTYPE)}")
    except Exception:
        print("\n❌ Could not connect to server. Please:")
        print("   1. Run Mantella in production mode (main.py)")
        print("   2. Or use VS Code: 'Mantella (Production)' debug config")
        print("   3. Wait for 'Waiting for player to select an NPC...' message")
        input("\nPress Enter to exit...")
        return
    
    # Select NPC
    selected_npc = select_npc()
    
    # Show simulated game context
    print("="*60)
    print("Simulated Game Context:")
    print("="*60)
    print(f"  Player: Level {client.game_context.PLAYER_STATE['level']}, {client.game_context.PLAYER_STATE['weapon']}")
    print(f"  Location: {client.game_context.LOCATION['name']}")
    print(f"  NPC Role: {client.game_context.get_npc_role_string(selected_npc['name'])}")
    print(f"  Nearby: {', '.join(n[0] for n in client.game_context.NEARBY_NPCS)}")
    print("="*60)
    
    print("\nStarting Conversation")
    print("="*60)
    if USE_MICROPHONE:
        print("\n🎤 Speak into your microphone when prompted")
    else:
        print("\n💬 Type your responses (or 'quit' to exit)")
    print("="*60 + "\n")
    
    # Start conversation
    start_response = client.start_conversation(selected_npc, use_microphone=USE_MICROPHONE)
    print(f"✓ Conversation started: {start_response.get(comm_consts.KEY_REPLYTYPE)}")
    
    # Process the response like Papyrus does (check for quest IDs)
    client.process_start_response(start_response)
    if client.pending_quest_ids:
        print(f"📋 Will send quest context for {len(client.pending_quest_ids)} quests")
    
    # Base context for conversation
    base_context = {
        comm_consts.KEY_CONTEXT_LOCATION: "Sanctuary Hills",
        comm_consts.KEY_CONTEXT_TIME: 12,
        comm_consts.KEY_CONTEXT_INGAMEEVENTS: [],
        comm_consts.KEY_CONTEXT_WEATHER: "Clear",
        comm_consts.KEY_CONTEXT_CUSTOMVALUES: {}
    }
    
    turn_counter = 0
    
    try:
        while True:
            turn_counter += 1
            
            # Add simulated events occasionally
            current_context = base_context.copy()
            if ENABLE_EVENT_SIMULATION and turn_counter % 3 == 0:
                test_events = get_test_events(turn_counter, selected_npc['name'])
                current_context[comm_consts.KEY_CONTEXT_INGAMEEVENTS] = test_events
                print(f"\n{'='*60}")
                print(f"📋 SIMULATED EVENTS (turn {turn_counter}): {len(test_events)} events")
                print(f"{'='*60}")
            
            # Continue conversation (get NPC responses)
            response = client.continue_conversation(current_context)
            reply_type = response.get(comm_consts.KEY_REPLYTYPE)
            
            if reply_type == comm_consts.KEY_REPLYTYPE_NPCTALK:
                # NPC is speaking
                npc_talk = response.get(comm_consts.KEY_REPLYTYPE_NPCTALK, {})
                speaker = npc_talk.get(comm_consts.KEY_ACTOR_SPEAKER, 'NPC')
                line = npc_talk.get(comm_consts.KEY_ACTOR_LINETOSPEAK, '')
                voice_file = npc_talk.get(comm_consts.KEY_ACTOR_VOICEFILE, '')
                duration = npc_talk.get(comm_consts.KEY_ACTOR_DURATION, 0)
                
                if line:
                    print(f"\n💬 {speaker}: {line}")
                if voice_file:
                    if ENABLE_AUDIO_PLAYBACK:
                        print(f"   🎵 Playing: {Path(voice_file).name} ({duration:.1f}s)")
                        play_audio(voice_file)
                    else:
                        print(f"   🎵 Audio: {Path(voice_file).name} ({duration:.1f}s)")
                
                # Continue to get the next sentence
                
            elif reply_type == comm_consts.KEY_REPLYTYPE_PLAYERTALK:
                # Player's turn
                print("\n" + "="*60)
                
                if USE_MICROPHONE:
                    # Microphone mode: send empty string, server will listen to mic
                    print("🎤 Listening... (speak now)")
                    print("="*60)
                    player_text = ""  # Empty string triggers server-side mic listening
                else:
                    # Text mode: prompt for typed input
                    player_text = input("👤 You: ").strip()
                    print("="*60)
                    
                    if player_text.lower() in ['quit', 'exit', 'q']:
                        break
                    
                    if not player_text:
                        print("⚠️  Empty input, please type something...")
                        continue
                
                # Send player input (empty if mic, typed text if text mode)
                player_response = client.player_input(player_text, current_context)
                player_reply_type = player_response.get(comm_consts.KEY_REPLYTYPE)
                
                # Get transcribed text if using microphone
                if USE_MICROPHONE and comm_consts.KEY_TRANSCRIBE in player_response:
                    transcribed_text = player_response[comm_consts.KEY_TRANSCRIBE]
                    print(f"✓ Transcribed: {transcribed_text}\n")
                    player_text = transcribed_text  # Update player_text for potential retry
                    
                    # Check for quit command in transcribed text
                    if transcribed_text.lower().strip() in ['quit', 'exit', 'stop']:
                        print("⏹️  Quit command detected")
                        break
                
                # Check if events need updating
                if player_reply_type == comm_consts.KEY_REQUESTTYPE_TTS:
                    logging.info("Events updated, re-sending player input...")
                    player_response = client.player_input(player_text, current_context)
                    player_reply_type = player_response.get(comm_consts.KEY_REPLYTYPE)
                
                # If player voice is enabled, play it
                if player_reply_type == comm_consts.KEY_REPLYTYPE_NPCTALK:
                    player_voice = player_response.get(comm_consts.KEY_REPLYTYPE_NPCTALK, {})
                    player_voice_file = player_voice.get(comm_consts.KEY_ACTOR_VOICEFILE, '')
                    if player_voice_file:
                        if ENABLE_AUDIO_PLAYBACK:
                            print(f"🎵 Playing player voice: {Path(player_voice_file).name}")
                            play_audio(player_voice_file)
                        else:
                            print(f"🎵 Player voice: {Path(player_voice_file).name}")
                
                # Loop continues to get NPC response
                
            elif reply_type == comm_consts.KEY_REPLYTYPE_ENDCONVERSATION:
                print("\n\n✓ Conversation ended by server")
                break
                
            else:
                print(f"\n⚠️  Unknown reply type: {reply_type}")
                break
                
    except KeyboardInterrupt:
        print("\n\n⏸️  Interrupted by user")
    
    # End conversation
    print("\nEnding conversation...")
    client.end_conversation()
    print("✓ Goodbye!")


if __name__ == "__main__":
    main()
