
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

class ImageToDelete:
    def __init__(self, image_path: Path):
        self.image_path = image_path

class ImageManager:
    KEY_CONTEXT_CUSTOMVALUES_VISION_READY: str = "mantella_vision_ready"
    KEY_CONTEXT_CUSTOMVALUES_VISION_RES: str = "mantella_vision_resolution"
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
                logging.warning(f"The file {image_path} does not exist.")
        except Exception as e:
            logging.error(f"An error occurred while adding image to delete list: {e}")

    def delete_images_from_file(self):
        for image in self.__images_to_delete:
            try:
                if image.image_path.is_file():
                    image.image_path.unlink()  # Delete the file, to enable later
                    logging.log(21,f"Deleted image {image.image_path}")
                else:
                    logging.warning(f"The file {image.image_path} does not exist.")
            except Exception as e:
                logging.error(f"An error occurred while deleting image {image.image_path}: {e}")
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
                logging.warning(f"The file {str(image_path)} does not exist.")
                return None
            resolution = str(self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_VISION_RES)).lower() or "auto"
            image_msg_instance = image_message(str(image_path), description, resolution, True)  # Need to put player name back in eventually
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
        if self.__context.get_custom_context_value(self.KEY_CONTEXT_CUSTOMVALUES_VISION_READY)==True:
            if self.__context.config.image_analysis_iterative_querying == False:
                logging.info("'Vision ready' Returned true, commencing iterative query")
                image_instance= self.__create_message_from_image(self.__direct_prompt) 
                messages.replace_or_add_message(image_instance,image_message)
            else:
                image_instance= self.__create_message_from_image(self.__iterative_prompt)
                logging.info("Waiting for image_description_response to be filled")
                self.__generation_thread = Thread(target=self.__output_manager.generate_simple_response, args=[image_instance])
                self.__generation_thread.start()
                self.__generation_thread.join()  # Wait for generate_simple_response to complete
                self.__generation_thread=None
                new_image_description_message : image_description_message = image_description_message(self.__output_manager.generated_simple_result, False)
                if self.__output_manager.generated_simple_result != "":
                    messages.replace_or_add_message(new_image_description_message,image_description_message)
                self.__output_manager.generated_simple_result=""

        else:
            self.__clean_message_thread_from_images(messages)

    def find_most_recent_jpg(self,directory):
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
            
            # Check if there are any recent .jpg files
            if not recent_files:
                logging.warning(f"No .jpg files found in the directory {directory} within the last 2 minutes.")
                return None
            
            # Find the most recent .jpg file from the filtered list
            most_recent_file = max(recent_files, key=lambda f: f.stat().st_mtime)
            
            # Return the filepath of the most recent .jpg file
            logging.log(21,f"Returning most recent Steam jpg file {most_recent_file}.")
            return str(most_recent_file)
        except Exception as e:
            logging.error(f"Error checking most recent jpg: {e}")
            return None
    
