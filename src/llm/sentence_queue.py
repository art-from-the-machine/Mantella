import logging
import queue
import threading
from src.llm.sentence import sentence

class sentence_queue:
    __logging_level = 42

    def __init__(self) -> None:
        self.__queue: queue.Queue[sentence] = queue.Queue[sentence]()
        self.__get_lock: threading.Lock = threading.Lock()
        self.__put_lock: threading.Lock = threading.Lock()
        self.__is_more_to_come: bool = False
    
    @property
    def Is_more_to_come(self) -> bool:
        return self.__is_more_to_come
    
    @Is_more_to_come.setter
    def Is_more_to_come(self, value: bool):
        # logging.log(self.__logging_level, f"Trying to aquire get_lock to set Is_more_to_come to '{value}'")
        # with self.__get_lock:
            self.__is_more_to_come = value

    def get_next_sentence(self) -> sentence | None:
        logging.log(self.__logging_level, f"Trying to aquire get_lock to get next sentence")
        with self.__get_lock:
            if self.__queue.qsize() > 0 or self.__is_more_to_come:
                retrieved_sentence = self.__queue.get()
                logging.log(self.__logging_level, f"Retrieved '{retrieved_sentence.Sentence}'")
                return retrieved_sentence
            else:
                logging.log(self.__logging_level, f"Nothing to get from queue, returning None")
                return None
    
    def put(self, new_sentence: sentence):
        logging.log(self.__logging_level, f"Trying to aquire put_lock to put '{new_sentence.Sentence}'")
        with self.__put_lock:
            logging.log(self.__logging_level, f"Putting '{new_sentence.Sentence}'")
            self.__queue.put(new_sentence)


    def put_at_front(self, new_sentence: sentence):
        logging.log(self.__logging_level, f"Trying to aquire get_lock to put_at_front '{new_sentence.Sentence}'")
        with self.__get_lock:
            logging.log(self.__logging_level, f"Trying to aquire put_lock to put_at_front '{new_sentence.Sentence}'")
            with self.__put_lock:            
                sentence_list: list[sentence] = []
                try:
                    while True:
                        sentence_list.append(self.__queue.get_nowait() )
                except queue.Empty:
                    pass
                self.__queue.put_nowait(new_sentence)
                for s in sentence_list:
                    self.__queue.put_nowait(s)

    def clear(self):
        logging.log(self.__logging_level, f"Trying to aquire get_lock to clear()")
        with self.__get_lock:
            logging.log(self.__logging_level, f"Trying to aquire put_lock to clear()")
            with self.__put_lock:
                try:
                    while True:                
                        self.__queue.get_nowait()
                except queue.Empty:
                    pass
