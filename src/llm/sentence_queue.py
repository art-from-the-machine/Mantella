import logging
import queue
import threading
from src.llm.sentence import Sentence
from src import utils

class SentenceQueue:
    __logging_level = 42
    __should_log = False

    def __init__(self) -> None:
        self.__queue: queue.Queue[Sentence] = queue.Queue[Sentence]()
        self.__get_lock: threading.Lock = threading.Lock()
        self.__put_lock: threading.Lock = threading.Lock()
        self.__is_more_to_come: bool = False
    
    @property
    def is_more_to_come(self) -> bool:
        return self.__is_more_to_come
    
    @is_more_to_come.setter
    def is_more_to_come(self, value: bool):
        self.__is_more_to_come = value

    @utils.time_it
    def get_next_sentence(self) -> Sentence | None:
        self.log(f"Trying to aquire get_lock to get next sentence")
        with self.__get_lock:
            if self.__queue.qsize() > 0 or self.__is_more_to_come:
                retrieved_sentence = self.__queue.get()
                self.log(f"Retrieved '{retrieved_sentence.text}'")
                return retrieved_sentence
            else:
                self.log(f"Nothing to get from queue, returning None")
                return None
    
    @utils.time_it
    def put(self, new_sentence: Sentence):
        self.log(f"Trying to aquire put_lock to put '{new_sentence.text}'")
        with self.__put_lock:
            self.log(f"Putting '{new_sentence.text}'")
            self.__queue.put(new_sentence)

    @utils.time_it
    def put_at_front(self, new_sentence: Sentence):
        self.log(f"Trying to aquire get_lock to put_at_front '{new_sentence.text}'")
        with self.__get_lock:
            self.log(f"Trying to aquire put_lock to put_at_front '{new_sentence.text}'")
            with self.__put_lock:            
                sentence_list: list[Sentence] = []
                try:
                    while True:
                        sentence_list.append(self.__queue.get_nowait() )
                except queue.Empty:
                    pass
                self.__queue.put_nowait(new_sentence)
                for s in sentence_list:
                    self.__queue.put_nowait(s)

    @utils.time_it
    def clear(self):
        self.log(f"Trying to aquire get_lock to clear()")
        with self.__get_lock:
            self.log(f"Trying to aquire put_lock to clear()")
            with self.__put_lock:
                try:
                    while True:                
                        self.__queue.get_nowait()
                except queue.Empty:
                    pass
    
    @utils.time_it
    def log(self, text: str):
        if(self.__should_log):
            logging.log(self.__logging_level, text)
