import openai
import tiktoken
import logging
import src.utils as utils
import time

@utils.time_it
def chatgpt_api(input_text, messages, llm):
    if input_text:
        messages.append(
            {"role": "user", "content": input_text},
        )
        logging.info('Getting LLM response...')
        try:
            chat_completion = openai.ChatCompletion.create(
                model=llm, messages=messages, headers={"HTTP-Referer": 'https://github.com/art-from-the-machine/Mantella', "X-Title": 'mantella'}, max_tokens=300
            )
        except openai.error.RateLimitError:
            logging.warning('Could not connect to LLM API, retrying in 5 seconds...')
            time.sleep(5)
    
    reply = chat_completion.choices[0].message.content
    messages.append(
        {"role": "assistant", "content": chat_completion.choices[0].message.content},
    )
    logging.info(f"LLM Response: {reply}")

    return reply, messages


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