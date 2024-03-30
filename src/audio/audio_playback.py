import math
import numpy as np
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = '1'
import pygame
from src.llm.sentence import sentence
from src.config_loader import ConfigLoader
from src.character_manager import Character

class audio_playback:
    def __init__(self, config: ConfigLoader) -> None:
        self.__FO4Volume_scale: float = config.FO4Volume / 100.0  # Normalize to 0.0-1.0
        self.__playback_channel: pygame.mixer.Channel | None = None
        self.pygame_initialize()        

    def pygame_initialize(self):
        # Ensure pygame is initialized
        if not pygame.get_init():
            pygame.init()

        # Explicitly initialize the pygame mixer
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=22050, size=-16, channels=2)  # Adjust these values as necessary

    def play_adjusted_volume(self, sentence_to_play: sentence, sound_origin_position: tuple[float, float], player_position: tuple[float, float], player_rotation: float):
        if self.__playback_channel:
            while self.__playback_channel.get_busy():  # Wait until playback is done
                pygame.time.delay(100)            
            del self.__playback_channel

        distance: float = math.sqrt(math.pow(sound_origin_position[0] - player_position[0], 2) + math.pow(sound_origin_position[1] - player_position[1], 2))
            
        # Calculate the relative angle
        relative_angle = self.__calculate_relative_angle(sound_origin_position, player_position, player_rotation)

        # Normalize the relative angle between -180 and 180
        normalized_angle = relative_angle % 360
        if normalized_angle > 180:
            normalized_angle -= 360  # Adjust angles to be within [-180, 180]

        # Calculate volume scale based on the normalized angle
        if normalized_angle >= -90 and normalized_angle <= 90:  # Front half
            # Linear scaling: Full volume at 0 degrees, decreasing to 50% volume at 90 degrees to either side
            volume_scale_left = 0.5 + normalized_angle / 90 * 0.5
            volume_scale_right = 0.5 - normalized_angle / 90 * 0.5
        elif normalized_angle > 90 and normalized_angle < 180:
            volume_scale_left = 90 / normalized_angle
            volume_scale_right = 1- 90 / normalized_angle
        elif normalized_angle > -180 and normalized_angle < -90:
            volume_scale_left = 1- 90 / abs(normalized_angle)
            volume_scale_right = 90 / abs(normalized_angle)
        else:  # failsafe if for some reason an unmanaged number is entered
            volume_scale_left = 0.5
            volume_scale_right = 0.5

        # Apply the calculated scale differently to left and right channels based on angle direction
        #if normalized_angle >= 0:  # Turning right
        #    volume_scale_left = volume_scale
        #    volume_scale_right = 1 - abs(normalized_angle) / 90 * 0.5  # Decrease right volume as angle increases
        #else:  # Turning left
        #    volume_scale_right = volume_scale
    #    volume_scale_left = 1 - abs(normalized_angle) / 90 * 0.5  # Decrease left volume as angle decreases

        # Ensure volumes don't drop below a threshold, for example, 0.1, if you want to keep a minimum volume level
        min_volume_threshold = 0.1
        volume_scale_left = max(volume_scale_left, min_volume_threshold)
        volume_scale_right = max(volume_scale_right, min_volume_threshold)

        if distance > 0:
            distance_factor = max(0, 1 - (distance / 4000))
        else:
            distance_factor=1

        # Load the WAV file
        sound = pygame.mixer.Sound(sentence_to_play.Voice_file)
        original_audio_array = pygame.sndarray.array(sound)
        
        if original_audio_array.ndim == 1:  # Mono sound
            # Duplicate the mono data to create a stereo effect
            audio_data_stereo = np.stack((original_audio_array, original_audio_array), axis=-1)
        else:
            audio_data_stereo = original_audio_array
        
        # Adjust volume for each channel according to angle, distance, and config volume
        audio_data_stereo[:, 0] = (audio_data_stereo[:, 0] * volume_scale_left * distance_factor * self.__FO4Volume_scale).astype(np.int16)  # Left channel
        audio_data_stereo[:, 1] = (audio_data_stereo[:, 1] * volume_scale_right * distance_factor * self.__FO4Volume_scale).astype(np.int16)  # Right channel
        
        # Convert back to pygame sound object
        adjusted_sound = pygame.sndarray.make_sound(audio_data_stereo)
        
        # Play the adjusted stereo audio
        self.__playback_channel = adjusted_sound.play()

    @staticmethod                    
    def __convert_game_angle_to_trig_angle(game_angle):
        #Used for Mantella Fallout to play directional audio
        """
        Convert the game's angle to a trigonometric angle.
        
        Parameters:
        - game_angle: The angle in degrees as used in the game.
        
        Returns:
        - A float representing the angle in degrees, adjusted for standard trigonometry.
        """
        if game_angle < 90:
            return 90 - game_angle
        else:
            return 450 - game_angle

    @staticmethod
    def __calculate_relative_angle(player_pos, target_pos, game_angle_z):
         #Used for Mantella Fallout to play directional audio
        """
        Calculate the direction the player is facing relative to the target, taking into account
        the game's unique angle system.
        
        Parameters:
        - player_pos: A tuple (x, y) representing the player's position.
        - target_pos: A tuple (x, y) representing the target's position.
        - game_angle_z: The angle (in degrees) the player is facing, according to the game's system.
        
        Returns:
        - The angle (in degrees) from the player's perspective to the target, where:
            0 = facing towards the target,
            90 = facing left of the target,
            270 = facing right of the target,
            180 = facing away from the target.
        """
        # Convert game angle to trigonometric angle
        trig_angle_z = audio_playback.__convert_game_angle_to_trig_angle(game_angle_z)
        
        # Calculate vector from player to target
        vector_to_target = (target_pos[0] - player_pos[0], target_pos[1] - player_pos[1])
        
        # Calculate absolute angle of the vector in degrees
        absolute_angle_to_target = math.degrees(math.atan2(vector_to_target[1], vector_to_target[0]))
        
        # Normalize the trigonometric angle
        normalized_trig_angle = trig_angle_z % 360
        
        # Calculate relative angle
        relative_angle = (absolute_angle_to_target - normalized_trig_angle) % 360
        
        # Adjust relative angle to follow the given convention
        if relative_angle > 180:
            relative_angle -= 360  # Adjust for angles greater than 180 to get the shortest rotation direction
        
        return relative_angle