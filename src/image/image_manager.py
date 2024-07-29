from datetime import datetime
import logging
import pygetwindow as gw
import pyautogui
import base64
import io
from PIL import Image
import os

class ImageManager:
    def __init__(self, game, save_folder) -> None:
        window_titles = {
            'Skyrim': 'Skyrim Special Edition',
            'SkyrimVR': 'Skyrim VR',
            'Fallout4': 'Fallout4',
            'Fallout4VR': 'Fallout4VR'
        }
        self.__window_title = window_titles.get(game, game)

        self.__image_path: str = save_folder+'data\\tmp\\images'
        os.makedirs(self.__image_path, exist_ok=True)


    def add_image_to_messages(self, openai_messages):
        image = self._get_image()
        # Add the image to the last user message or create a new message if needed
        if openai_messages and openai_messages[-1]['role'] == 'user':
            openai_messages[-1]['content'] = [
                {"type": "text", "text": openai_messages[-1]['content']},
                {"type": "image_url", "image_url": {"url":  f"data:image/jpeg;base64,{image}"}}
            ]
        else:
            openai_messages.append({
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url":  f"data:image/jpeg;base64,{image}"}}
                ]
            })

        return openai_messages


    def _save_screenshot(self, screenshot):
        if screenshot is None:
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.__image_path}/{self.__window_title.replace(' ', '_')}_{timestamp}.png"

        screenshot.save(filename, "PNG")


    def _resize_image(self, image, target_height=720):
        width, height = image.size
        new_width = int((target_height / height) * width)
        
        resized_image = image.resize((new_width, target_height), Image.LANCZOS)
        
        return resized_image
    

    def _get_image(self):
        try:
            window = gw.getWindowsWithTitle(self.__window_title)[0]
            
            if window.isMinimized:
                window.restore()
            
            left, top = window.left+10, window.top+10
            width, height = window.width-30, window.height-30
            logging.info(f'left: {left}, top: {top}, width: {width}, height: {height}')
            screenshot = pyautogui.screenshot(region=(left, top, width, height))
            compressed_image = self._resize_image(screenshot,target_height=480)
            buffered = io.BytesIO()
            compressed_image.save(buffered, format="JPEG", quality=85)
            img_str = base64.b64encode(buffered.getvalue()).decode()
            self._save_screenshot(screenshot)
            return img_str
        except IndexError:
            return None
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            return None