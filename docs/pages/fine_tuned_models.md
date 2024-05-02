(fine-tuned-models)=
# Fine-Tuned Models

<div style="display: flex; align-items: center;">
  <div style="flex: none; white-space: nowrap; text-align: right; padding-right: 5px;">
    Available On
  </div>
  <div>
    <a href="https://huggingface.co/art-from-the-machine/Mantella-Skyrim-Llama-3-8B-GGUF" target="_blank">
      <img src="../_static/img/hugging_face_link_transparent.png" alt="Hugging Face Banner that links to Mantella Fine-Tuned Models" style="max-width:25%;height:auto;">
    </a>
  </div>
</div> 

<hr style="border: 1px solid #505050; margin-top: 5px; margin-bottom: 15px;">

## Introduction
Fine-tuning LLMs allows these models to learn the nuances, style, and knowledge of a specific domain, resulting in improved performance and more coherent outputs.
To enhance the quality of Skyrim and Fallout conversations, fine-tuned models specifically tailored to the dialogue style and lore of these games can improve LLM output when compared to their non-fine-tuned counterparts.

## Skyrim

### Dataset
An Alpaca-style dataset of 8,800+ player <-> NPC interactions has been generated via the [Mantella LLM Fine-Tuning repo](https://github.com/art-from-the-machine/Mantella-LLM-Fine-Tuning). This dataset has been used to fine-tune the below LLMs.

### Fine-Tunes

#### Llama 3 8B Instruct
Link to Model: [https://huggingface.co/art-from-the-machine/Mantella-Skyrim-Llama-3-8B-GGUF](https://huggingface.co/art-from-the-machine/Mantella-Skyrim-Llama-3-8B-GGUF)

<details>
<summary><b>Example Output</b></summary>

```json
[
    {
        "role": "assistant",
        "content": "Ah, welcome to The Bannered Mare! Have a seat by the fire, and I'll have one of the barmaids bring you a pint of our finest ale. What brings you to Whiterun today?"
    },
    {
        "role": "user",
        "content": "What's life like in Whiterun?"
    },
    {
        "role": "assistant",
        "content": "Life in Whiterun is good, thank you for asking. The Jarl's been doing a fine job of keeping the city prosperous. Of course, there's always something going on, whether it's the Companions looking for new members or the Thieves Guild trying to... well, steal things. But overall, it's a good place to live."
    },
    {
        "role": "user",
        "content": "What do you think about the civil war in Skyrim?"
    },
    {
        "role": "assistant",
        "content": "The civil war? Well, I think it's a shame, to be honest. I've got friends on both sides of the conflict, and it's hard to see them fighting each other. But I suppose it's not my place to say who's right or wrong. I just hope it ends soon and we can all get back to living our lives in peace."
    },
    {
        "role": "user",
        "content": "I'm looking for work. Got any leads?"
    },
    {
        "role": "assistant",
        "content": "Work, you say? Well, the city's always looking for people to help with the harvest, and the Jarl's guards could use some extra hands. If you're looking for something more... adventurous, you might want to talk to the Companions. They're always looking for new members to join their ranks. Just be warned, though - it's not for the faint of heart."
    },
    {
        "role": "user",
        "content": "I'm looking for an Elder Scroll. Do you know anything about them?"
    },
    {
        "role": "assistant",
        "content": "Elder Scrolls? Ah, yes... I've heard rumors about those ancient artifacts. Some say they hold the secrets of the world, while others claim they're cursed. I don't know much about them, but I've heard that the Greybeards in the mountains might know more. They're a reclusive bunch, but if you're willing to brave the wilderness, you might be able to learn something from them."
    }
]
```
</details>

## Contribute
Many improvements can be made to the Skyrim dataset. A Fallout 4 dataset could also potentially be generated using the same methodology used to create the Skyrim dataset. A full list of potential future improvements can be found [here](https://github.com/art-from-the-machine/Mantella-LLM-Fine-Tuning#future-work).

If you would like to fine-tune your own Skyrim or Fallout models, [Unsloth](https://unsloth.ai/) is a great way to get started with template Colab notebooks. If you are eager to fine-tune your own models, but are not sure about how to start, feel free to reach out on [Discord](https://discord.gg/Q4BJAdtGUE)!