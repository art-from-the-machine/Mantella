from datetime import datetime
import logging
import base64
import os
import src.utils as utils
import numpy as np
import win32gui
import mss
import cv2
import ctypes
from pathlib import Path
from src.config.definitions.game_definitions import GameEnum

class ImageManager:
    '''
    Manages game window capture and image processing
    '''
    
    @utils.time_it
    def __init__(self, 
                 game: GameEnum, 
                 save_folder: str, 
                 save_screenshot: bool, 
                 image_quality: int, 
                 low_resolution_mode: bool, 
                 resize_method: str, 
                 capture_offset: dict[str, int], 
                 use_game_screenshots: bool,
                 game_image_path: str | None) -> None:
        
        WINDOW_TITLES = {
            GameEnum.SKYRIM: 'Skyrim Special Edition',
            GameEnum.SKYRIM_VR: 'Skyrim VR',
            GameEnum.FALLOUT4: 'Fallout4',
            GameEnum.FALLOUT4_VR: 'Fallout4VR'
        }
        # Get window title from game enum, or as a last resort try using the display name
        self.__window_title: str = WINDOW_TITLES.get(game, game.display_name)
        self.__save_screenshot: bool = save_screenshot
        self.__image_quality: int = image_quality
        self.__capture_offset: dict[str, int] = capture_offset
        self.__low_resolution_mode: bool = low_resolution_mode

        RESIZING_METHODS = {
            'Nearest': cv2.INTER_NEAREST,
            'Linear': cv2.INTER_LINEAR,
            'Cubic': cv2.INTER_CUBIC,
            'Lanczos': cv2.INTER_LANCZOS4
        }
        self.__resize_method: int = RESIZING_METHODS.get(resize_method, cv2.INTER_NEAREST)

        self.__use_game_screenshots: bool = use_game_screenshots
        self.__game_image_file_path = None
        if game_image_path:
            self.__game_image_file_path: str = str(Path(game_image_path) / "Mantella_Vision.jpg")
            if self.__use_game_screenshots:
                if os.path.exists(self.__game_image_file_path):
                    logging.log(23, f'Removing leftover in-game vision screenshot from previous run...')
                    os.remove(self.__game_image_file_path)

        if self.__save_screenshot:
            self.__image_path: str = save_folder+'data\\tmp\\images'
            os.makedirs(self.__image_path, exist_ok=True)

        self.__capture_params = None

        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except:
            logging.warning('Failed to read monitor DPI. Images may not be saved in the correct dimensions.')


    @property
    def capture_params(self):
        if self.__capture_params is None:
            self.__capture_params = self._calculate_capture_params()
        return self.__capture_params
    

    def reset_capture_params(self):
        self.__capture_params = None


    @utils.time_it
    def _calculate_capture_params(self) -> dict[str, int]:
        '''Calculate the capture parameters / coordinates of the game window

        Returns:
            dict[str,int]: A dictionary containing window locations and their coordinates
        '''
        hwnd = win32gui.FindWindow(None, self.__window_title)
        if not hwnd:
            # Check if the game version is GOG
            gog_title = self.__window_title + ' GOG'
            hwnd = win32gui.FindWindow(None, gog_title)
            if not hwnd:
                logging.error(f"Window '{self.__window_title}' not found")
                self.__capture_params = None
                return None

        window_rect = win32gui.GetWindowRect(hwnd)
        client_rect = win32gui.GetClientRect(hwnd)
        client_left, client_top = win32gui.ClientToScreen(hwnd, (0, 0))
        
        left_border = client_left - window_rect[0]
        top_border = client_top - window_rect[1]

        capture_left = max(window_rect[0] + left_border + self.__capture_offset.get('left', 0), 0)
        capture_top = max(window_rect[1] + top_border + self.__capture_offset.get('top', 0), 0)
        capture_width = client_rect[2] + self.__capture_offset.get('right', 0)
        capture_height = client_rect[3] + self.__capture_offset.get('bottom', 0)

        return {"left": capture_left, "top": capture_top, "width": capture_width, "height": capture_height}


    @utils.time_it
    def _resize_image(self, image: np.ndarray, width: int, height: int) -> np.ndarray:
        '''Resize the image to the target resolution specified here: 
        https://platform.openai.com/docs/guides/vision/managing-images

        In summary:
            "low" detail images should have a resolution of 512x512
            "high" detail images should have a maximum length of 768 for the short side and 2048 for the long side

        Args:
            image (numpy.ndarray): The image to resize
            width (int): The width of the screenshot
            height (int): The height of the screenshot

        Returns:
            numpy.ndarray: The resized image
        '''

        if self.__low_resolution_mode:
            target_size = 512
            if height < width:
                scale_factor = target_size / height
                new_height = target_size
                new_width = int(width * scale_factor)
            else:
                scale_factor = target_size / width
                new_width = target_size
                new_height = int(height * scale_factor)

            resized_image = cv2.resize(image, (new_width, new_height), interpolation=self.__resize_method)

            start_x = (new_width - target_size) // 2
            start_y = (new_height - target_size) // 2

            cropped_image = resized_image[start_y:start_y + target_size, start_x:start_x + target_size]

            return cropped_image
        else:
            max_short_side = 768
            max_long_side = 2_000

            short_side = min(height, width)
            long_side = max(height, width)
            
            if short_side <= max_short_side and long_side <= max_long_side:
                return image
            
            scale_factor = min(max_short_side / short_side, max_long_side / long_side)
            
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            
            resized_image = cv2.resize(image, (new_width, new_height), interpolation=self.__resize_method)
            
            return resized_image
    

    @utils.time_it
    def _take_screenshot(self, params: dict[str, int]) -> tuple[np.ndarray, int, int]:
        '''Take a screenshot within the area specified by params

        Args:
            params (dict[str, int]): The capture parameters

        Returns:
            image (numpy.ndarray): The captured screenshot as a numpy array
            width (int): The width of the screenshot
            height (int): The height of the screenshot
        '''
        with mss.mss() as sct:
            screenshot = sct.grab(params)
        return np.array(screenshot), screenshot.width, screenshot.height
    

    @utils.time_it
    def _get_screenshot(self) -> tuple[np.ndarray, int, int]:
        '''Search for saved screenshots that have been taken in-game, removing them once loaded

        Returns:
            image (numpy.ndarray): The saved screenshot as a numpy array
            width (int): The width of the screenshot
            height (int): The height of the screenshot
        '''
        screenshot = cv2.imread(self.__game_image_file_path)
        os.remove(self.__game_image_file_path)

        height, width = screenshot.shape[:2]
        return np.array(screenshot), width, height
    

    @utils.time_it
    def _encode_image_to_jpeg(self, screenshot):
        return cv2.imencode('.jpg', screenshot, [cv2.IMWRITE_JPEG_QUALITY, self.__image_quality])[1]
    

    @utils.time_it
    def get_image(self) -> str | None:
        '''Capture, process, and encode an image of the game window

        Returns:
            str: Base64 encoded JPEG image, or None if capture fails
        '''
        try:
            params = self.capture_params
            if not params:
                return None
  
            # Capture
            if self.__use_game_screenshots and self.__game_image_file_path is not None:
                if os.path.exists(self.__game_image_file_path):
                    screenshot, width, height = self._get_screenshot()
                else:
                    return None
            else:
                screenshot, width, height = self._take_screenshot(params)

            # Process
            screenshot = self._resize_image(screenshot, width, height)

            # Encode
            buffer = self._encode_image_to_jpeg(screenshot)
            img_str = base64.b64encode(buffer).decode()

            # Optionally, save the image to disk
            if self.__save_screenshot:
                self._save_screenshot_to_file(buffer)
            
            return img_str
        
        except Exception as e:
            utils.play_error_sound()
            logging.error(f"An error occurred: {e}")
            self.reset_capture_params() # reset the window capture coordinates
            return None
        

    @utils.time_it
    def _save_screenshot_to_file(self, screenshot: bytes):
        '''Save the screenshot to a file
        
        Args:
            screenshot (bytes): The screenshot data to save
        '''
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.__image_path}/{self.__window_title.replace(' ', '_')}_{timestamp}.jpg"

        with open(filename, 'wb') as f:
            f.write(screenshot)
