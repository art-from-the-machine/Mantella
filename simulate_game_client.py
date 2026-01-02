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
                timeout=60  # 2 minutes for mic input + STT processing
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
    
    choice = input(f"\n👉 Select NPC (1-10) or press Enter for first: ").strip()
    idx = int(choice) - 1 if choice else 0
    selected = npcs[idx]
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
    
    print("="*60)
    print("Starting Conversation")
    print("="*60)
    if USE_MICROPHONE:
        print("\n🎤 Speak into your microphone when prompted")
    else:
        print("\n💬 Type your responses (or 'quit' to exit)")
    print("="*60 + "\n")
    
    # Start conversation
    start_response = client.start_conversation(selected_npc, use_microphone=USE_MICROPHONE)
    print(f"✓ Conversation started: {start_response.get(comm_consts.KEY_REPLYTYPE)}")
    
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
                    # In real game, you would update context and resend with the same text
                    # Use the transcribed/typed text from before
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

