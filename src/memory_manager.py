import atexit
import asyncio
import string
import uuid
import src.utils as utils
import logging
import subprocess
import sys
import signal

import chromadb

class Memory:
    def __init__(self, config):
        loop = asyncio.new_event_loop()
        self.config = config
        if self.config.vector_memory_enabled == '1' and self.config.vector_memory_chromadb_c_s == '1':
            # Start chromadb and don't wait 
            try:
                self._db_process = subprocess.Popen(['chroma', 'run', '--path', self.config.vector_memory_db_path])
            except:
                logging.error(f'Could not run chromadb. Mantella has no memory.')
                input('\nPress any key to stop Mantella...')
                sys.exit(0)
            # Try to terminate chromadb at program exit
            atexit.register(self.stop)
            signal.signal(signal.SIGINT, self.__signal_stop)
            signal.signal(signal.SIGTERM, self.__signal_stop)

            self._db_client = chromadb.HttpClient(host=self.config.vector_memory_db_host, port=self.config.vector_memory_db_port)
        elif self.config.vector_memory_enabled == '1' and self.config.vector_memory_chromadb_c_s == '0':
            self._db_client = chromadb.PersistentClient(path=self.config.vector_memory_db_path)

    def __signal_stop(self, signum, frame):
        self.stop()

    def stop(self):
        if self._db_process is not None and self._db_process.poll() is None:
            self._db_process.terminate()

    @utils.time_it
    def memorize(self, convo_id, character_info, location, time, relationship='a stranger', character_comment='', player_comment=''):
        time_desc = utils.get_time_group(time)
        memory_str = f'{character_info["name"]} was talking to the player, {relationship} {time_desc} in {location}.\n {character_info["name"]} said: "{character_comment}".\n The player responded: "{player_comment}"'
        try:
            collection = self._db_client.get_or_create_collection(name=_collection_name(character_info['name']), metadata={"hnsw:space": "cosine"})
            collection.add(documents=[memory_str], metadatas=[
                {'convo_id': convo_id, 'location': location}
            ], ids=[uuid.uuid4().hex])
        except Exception as e:
            logging.error(f'Error saving memory to vectordb: {e}')

    @utils.time_it
    def recall(self, convo_id, character_info, location, time, relationship = 'a stranger', player_comment: str = None):
        time_desc = utils.get_time_group(time)
        query_str =  f'{time_desc} in {location}.\n The player meets {relationship} {character_info["name"]}.'
        if player_comment is not None and len(player_comment) > 0:
            query_str = f'It is {time_desc} in {location}.\n The player is talking to {relationship} {character_info["name"]}.\n The player says: {player_comment}"'
        try:
            collection = self._db_client.get_collection(name=_collection_name(character_info['name']))
            logging.info(f'Recall query {query_str}')
            logging.info(f'There are {collection.count()} memories')
            result = collection.query(query_texts=[query_str], 
                                      where={
                                          convo_id: {
                                              '$ne': convo_id
                                          }
                                      },
                                      include=["documents"],
                                      n_results=3)
            logging.info(f'Recalled memories {result}')
            return result["documents"]
        except Exception as e:
            logging.error(f'Error loading memories from vectordb: {e}')
            return None
        
    def update_memories(self, message, memories):
        if len(memories) > 0:
            mem = 'Below are your memories from past conversations:\n%s}' % "".join(memories, "\n\n")
            message = mem + '\n' + message

def _collection_name(character_name: str): 
    return character_name.lower().translate(str.maketrans('', '', string.punctuation + string.whitespace + string.digits))