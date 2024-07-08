
import logging
import time
import os
from threading import Thread
from src.output_manager import ChatManager
from src.llm.messages import image_message, image_description_message 
from src.conversation.context import context
from src.llm.message_thread import message_thread
from pathlib import Path
from datetime import datetime, timedelta
import base64
from PIL import Image
from io import BytesIO

class ImageToDelete:
    def __init__(self, image_path: Path):
        self.image_path = image_path

class ImageManager:
    KEY_CONTEXT_CUSTOMVALUES_VISION_READY: str = "mantella_vision_ready"
    KEY_CONTEXT_CUSTOMVALUES_VISION_RES: str = "mantella_vision_resolution"
    KEY_CONTEXT_CUSTOMVALUES_VISION_RESIZE: int = "mantella_vision_resize"
    def __init__(self, context_for_conversation, output_manager, generation_thread) -> None:
        
        self.__context: context = context_for_conversation 
        self.__output_manager: ChatManager = output_manager
        #self.__game = self.__output_manager.__game #Check if this is working correctly
        self.__direct_prompt =self.__context.config.image_llm_direct_prompt
        self.__iterative_prompt =self.__context.config.image_llm_iterative_prompt
        self.__generation_thread = generation_thread  # Ensure this is always initialized
        self.__images_to_delete = []  # Initialize as an empty list of ImageToDelete objects

    def __add_image_to_delete(self, image_path: str):
        try:
            path_obj = Path(image_path)
            if path_obj.is_file():
                self.__images_to_delete.append(ImageToDelete(path_obj))
                #logging.info(f"Image {image_path} added to delete list.")
            else:
                logging.debug(f"The file {image_path} does not exist.")
        except Exception as e:
            logging.debug(f"An error occurred while adding image to delete list: {e}")

    def delete_images_from_file(self):
        for image in self.__images_to_delete:
            try:
                # Regular image deletion
                if image.image_path.is_file():
                    image.image_path.unlink()  # Delete the file
                    logging.debug( f"Deleted image {image.image_path}")
                else:
                    logging.debug(f"The file {image.image_path} does not exist.")

                # Prepare the VR image path
                vr_image_path = image.image_path.with_name(image.image_path.stem + '_vr.jpg')
                
                # VR image deletion
                if vr_image_path.is_file():
                    vr_image_path.unlink()  # Delete the VR file
                    logging.debug( f"Deleted VR image {vr_image_path}")
                else:
                    logging.debug(f"The VR file {vr_image_path} does not exist.")
            except Exception as e:
                logging.error(f"An error occurred while deleting images: {e}")

        # Clear the list after attempting to delete all images
        self.__images_to_delete.clear()

    def attempt_to_add_most_recent_image_to_deletion_array(self):
        if self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_VISION_READY)==True:
            try:
                most_recent_image_path, is_vr = self.__output_manager.get_image_filepath()
                if is_vr: 
                    most_recent_image_path = self.find_most_recent_jpg(str(most_recent_image_path))
                    self.__add_image_to_delete(str(most_recent_image_path))
            except Exception as e:
                logging.error(f"An error occurred while adding the latest image to deletion array: {e}")

    @staticmethod
    def resize_image(image_path, target_width):
        """
        Resize the image at the specified path to the target width while preserving the aspect ratio.
        Parameters:
        - image_path: Path to the image to be resized.
        - target_width: Desired width of the image. If None or the original width is smaller, no resizing is performed.
        """
        try:
            with Image.open(image_path) as img:
                original_width, original_height = img.size

                # If resizing is not needed
                if target_width is None or original_width <= target_width:
                    # Save the image temporarily to avoid returning a closed object
                    img.save(image_path)
                    # Reopen and return the image as a new PIL Image object
                    return Image.open(image_path)

                # Calculate new dimensions
                aspect_ratio = original_height / original_width
                new_height = int(target_width * aspect_ratio)

                # Resize and return new image
                resized_img = img.resize((target_width, new_height), Image.LANCZOS )
                resized_img.save(image_path)  # Overwrite the original image or save as a new file
                #logging.info(f"Resized image to target width :  {target_width}")
                return resized_img
        except Exception as e:
            logging.warning(f"Failed to resize image {image_path}: {str(e)}")
            return None

        # Example usage
        # resized_image = resize_image('path/to/your/image.jpg', 1900)
        # if resized_image is None:
        #     print("Image resizing failed.")

    @staticmethod
    def image_to_base64(pil_img, format='JPEG'):
        """
        Convert a PIL Image object to a base64-encoded string.
        
        Parameters:
            pil_img (PIL.Image): A PIL Image object.
            format (str): The format to save the image in memory. Defaults to 'JPEG'.
            
        Returns:
            str: A base64-encoded string of the image.
        """
        # Create a bytes buffer for the in-memory image
        img_buffer = BytesIO()
        
        # Save the image to the buffer in JPEG format
        pil_img.save(img_buffer, format=format)
        
        # Get the byte data from the buffer
        byte_data = img_buffer.getvalue()
        
        # Encode this byte data to base64
        base64_str = base64.b64encode(byte_data).decode('utf-8')
        
        return base64_str

    def __create_message_from_image(self,description):
        try:
            # Create an instance of the image_message class
            image_path, is_vr = self.__output_manager.get_image_filepath()
            image_path = Path(image_path) 
            if is_vr: 
                recent_image_path = self.find_most_recent_jpg(str(image_path))
                if recent_image_path:
                    image_path = Path(recent_image_path) 
                else:
                    logging.warning(f"No jpg file created in the last 2 minutes was found in {str(image_path)} .")
                    return None
                self.__add_image_to_delete(str(image_path))
            else:
                image_path = Path(image_path) / "Mantella_Vision.jpg" 
            # Check if the file exists
            if not image_path.is_file():
                logging.debug(f"The file {str(image_path)} does not exist.")
                return None
            resolution = str(self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_VISION_RES)).lower() or "auto"
            resize_value = int(self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_VISION_RESIZE)) or 1024
            image_object = self.resize_image(image_path, resize_value) #Need to make this editable
            encoded_image_str = self.image_to_base64(image_object)
            image_msg_instance = image_message(encoded_image_str, description, resolution, True)  # Need to put player name back in eventually
            return image_msg_instance
                   
        except Exception as e:
            logging.error(f"An error occurred while creating the user image: {e}")
            return None
    
    def __clean_message_thread_from_images(self, messages):
        if messages.has_message_type(image_message):
                messages.delete_all_message_type(image_message)
        if messages.has_message_type(image_description_message):
            messages.delete_all_message_type(image_description_message)

    def process_image_analysis(self, messages: message_thread):
        if self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_VISION_READY):
            if self.__context.config.image_analysis_iterative_querying == False:
                logging.info("'Vision ready' Returned true, attempting direct image query")
                image_instance = self.__create_message_from_image(self.__direct_prompt)
                if image_instance:
                    messages.replace_or_add_message(image_instance, image_message)
                else:
                    logging.debug("No valid image instance created for direct querying.")
            else:
                logging.info("'Vision ready' Returned true, attempting iterative query")
                image_instance = self.__create_message_from_image(self.__iterative_prompt)
                if image_instance:
                    logging.info("Waiting for image_description_response to be filled")
                    self.__generation_thread = Thread(target=self.__output_manager.generate_simple_response, args=[image_instance])
                    self.__generation_thread.start()
                    self.__generation_thread.join()
                    self.__generation_thread = None
                    if self.__output_manager.generated_simple_result:
                        new_image_description_message = image_description_message(self.__output_manager.generated_simple_result, False)
                        messages.replace_or_add_message(new_image_description_message, image_description_message)
                    else:
                        logging.warning("Generated simple response did not produce a valid result.")
                else:
                    logging.debug("No valid image instance created for iterative querying.")
        else:
            self.__clean_message_thread_from_images(messages)

    def find_most_recent_jpg(self, directory):
        # Convert the directory to a Path object
        time.sleep(0.5)
        dir_path = Path(directory)
        
        # Check if the directory exists
        if not dir_path.is_dir():
            logging.error(f"The directory {directory} for image search does not exist or is not a directory.")
            return None
        
        try:
            # Get the current time
            now = datetime.now()
            
            # Get a list of all .jpg files in the directory
            jpg_files = list(dir_path.glob('*.jpg'))
            
            # Filter the files to include only those modified in the last 2 minutes
            recent_files = [f for f in jpg_files if datetime.fromtimestamp(f.stat().st_mtime) > now - timedelta(minutes=2)]
            
            # Sort files by modification time, most recent first
            recent_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

            # Filter out the files based on conditions
            for file in recent_files:
                # Check if file ends with '_vr.jpg'
                if not file.name.endswith('_vr.jpg'):
                    # Check if file is in the deletion list
                    if file not in (x.image_path for x in self.__images_to_delete):
                        logging.debug( f"Returning most recent jpg file {file}.")
                        return str(file)

            # If no suitable file found
            logging.debug(f"No suitable .jpg file found in the directory {directory}.")
            return None
        except Exception as e:
            logging.error(f"Error checking most recent jpg: {e}")
            return None
