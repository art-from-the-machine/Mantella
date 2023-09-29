import openai
import tiktoken
import logging
import src.utils as utils
import time
import requests

@utils.time_it
def chatgpt_api(input_text, messages, llm):
    reply = ""
    if input_text:
        messages.append(
            {"role": "user", "content": input_text},
        )
        logging.info('Getting ChatGPT response...')
        try:
            # check if using kobold llm or not, if using kobold as indicated by the alternative_openai_api_base in the config, then we passed that value to "llm" in game_manager for this purpose
            if 'api/extra/generate/stream' in llm:
                # need to parse llm to just get the domain stored in llm and then add /api/v1/generate dynamically; note here we are using the non-streaming API for the summary.
                parts_of_url = llm.split('/')
                start_of_url = '/'.join(parts[:3])
                kobold_url = start_of_url + '/api/v1/generate' #'http://localhost:5001/api/v1/generate'
                # need to convert messages array into a single string prompt for kobold which does not use messages array format
                formatted_messages = []
                for message in messages:
                    role = message["role"]
                    content = message["content"]
                    if role == "user":
                        formatted_messages.append(f"###Instruction: {content}")
                    elif role == "assistant":
                        formatted_messages.append(f"###Response: {content}")
                    elif role == "system":
                        formatted_messages.append(f"###Instruction: {content}")
                formatted_messages.append("###Response:")
                kobold_messages_string = "\n".join(formatted_messages)
                
                kobold_data = {
                    "prompt": kobold_messages_string,
                    "temperature": 1.0,
                    "top_p": 0.9,
                    "max_length": 200,
                    "rep_pen":1.12
                }

                # send a POST request to the kobold API
                response = requests.post(kobold_url, json=kobold_data)

                # check if the request was successful (status code 200)
                if response.status_code == 200:
                    try:
                        # parse the JSON response
                        data = response.json()
                        # extract the "text" value from the response and store it in the "reply" variable
                        reply = data["results"][0]["text"]
                        messages.append({"role": "assistant", "content": reply},)
                        logging.info(f"ChatGPT Response: {reply}")
                        return reply, messages
                    except ValueError:
                        print("Error: Failed to parse JSON response")
                else:
                    print(f"Error: Request failed with status code {response.status_code}")
            # if not using kobold then using a openai API based solution
            else:
                chat_completion = openai.ChatCompletion.create(
                    model=llm, messages=messages, headers={"HTTP-Referer": 'https://github.com/art-from-the-machine/Mantella', "X-Title": 'mantella'},
                )
                reply = chat_completion.choices[0].message.content
                messages.append({"role": "assistant", "content": reply},)
                logging.info(f"ChatGPT Response: {reply}")
                return reply, messages
        except openai.error.RateLimitError:
            logging.warning('Could not connect to ChatGPT API, retrying in 5 seconds...')
            time.sleep(5)


def num_tokens_from_messages(messages, model="gpt-3.5-turbo"):
    """Returns the number of tokens used by a list of messages"""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    
    # note: this calculation is based on GPT-3.5, future models may deviate from this
    num_tokens = 0
    for message in messages:
        num_tokens += 4  # every message follows <im_start>{role/name}\n{content}<im_end>\n
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":  # if there's a name, the role is omitted
                num_tokens += -1  # role is always required and always 1 token
    num_tokens += 2  # every reply is primed with <im_start>assistant
    return num_tokens