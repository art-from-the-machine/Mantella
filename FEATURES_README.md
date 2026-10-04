# Feature Documentation

Trying my best to explain why I added these features and how to make the most of them. Currently it only works with Mantella below v 0.14.

## Directory

- [Character Tags](#character-tags)
- [Dynamic Events (tag feature)](#dynamic-events-tag-feature)
- [Lorebook](#lorebook)
- [Multiple Profile System](#multiple-profile-system)
- [Prompt Profiles](#prompt-profiles)
- [Sequential LLM Selection](#sequential-llm-selection)
- [Bio Sections to Exclude](#bio-sections-to-exclude)
- [Private Thoughts](#private-thoughts)
- [Personal Reflection](#personal-reflection)
- [Drop Last Sentences](#drop-last-sentences)
- [Send Only Bios](#send-only-bios)
- [Reload Character Data](#reload-character-data)
- [Save Summary Now](#save-summary-now)
- [Real World Timestamp](#real-world-timestamp)
- [Hot Swap](#hot-swap)
- [Live Conversation](#live-conversation)
- [bios_and_summaries Prompt Variable](#bios_and_summaries-prompt-variable)

## Character Tags

### What are character tags?

Character tags are reusable labels you assign to NPCs. Each tag maps to a description in a **bio templates** CSV.
When an NPC loads, Mantella appends the matching descriptions to their bio under `## Additional info`.

### Why use character tags?

- Give NPCs shared knowledge (a hold, a guild, a questline, etc) without rewriting every bio by hand. Update one template (for example `whiterun_hold`) and every NPC with that tag picks up the change.
- Use community-ready assignments so you do not have to decide which NPCs belong to which hold or quest.
- Assign personalities or moods to NPCs randomly to add more variety to your gameplay.

Note that there are no correct answers for how to create tags. It is up to your creativity and the story you want to tell.

Enable or disable this feature with **Enable Character Tag Reading** in the LLM settings.

### Recommended files (Nexus)

Strongly recommended: use the character CSV and bio templates from [Nexus](https://www.nexusmods.com/skyrimspecialedition/mods/174770).

That pack is built for this tag system:

- Its `skyrim_characters.csv` has the correct columns (`tags`, `tags_overwrite`, and related fields). Use that file (or start from it) so columns match what Mantella expects.
- Its bio_templates CSVs include the essential tags and already assign them to the right NPCs. You do not need to figure out who should get `whiterun_hold` — that tag is already on the correct characters. It also includes tags for quests, some popular mods, and more.

Using those files is the fastest way to get a working, game-wide tag setup.

### Quick start: create a tag and give it to an NPC

Follow these steps to add one custom tag without touching the big base CSV.

**1. Create the tag definition**

Create (or edit) a CSV under your personal templates folder:

`Documents\\My Games\\Mantella\\data\\Skyrim\\bio_templates\\my_custom_tags.csv`

Contents:

```
tag,description
whiterun_hold, Ado is the dragonborn who saved the city from a dragon attack.
```

Any `.csv` name is fine. Columns must be `tag` and `description`. You can also use the files from the nexus page mentioned above, in which lots of tags are already predefined. 

**2. Assign the tag to a character (**`tags` **vs** `tags_overwrite`**)**

Open the character's existing row in your character override CSV. You only need the `tags` / `tags_overwrite` columns.

**When to use which column**


| Goal                                                 | Column to fill   | Leave empty      |
| ---------------------------------------------------- | ---------------- | ---------------- |
| **Add** tag(s) on top of what the NPC already has    | `tags`           | `tags_overwrite` |
| **Replace** the NPC's entire tag list with a new set | `tags_overwrite` | -                |


- Use `tags` for most edits. Example: NPC already has `companion` in the base file; you set `tags` in your override CSV to `whiterun_hold` → effective tags become `companion,whiterun_hold`.
- Use `tags_overwrite` only when you don't like the tags the NPC is assigned in the base character file and want to clear them and replace them with your own. Example: you set `tags_overwrite` to `riften_hold,thieves_guild` → effective tags are **only** those two; everything from the `tags` column is ignored.
- Assign tags as a comma-separated list (for example: `warrior,mage,whiterun_hold`).

**3. Reload**

Go to **Other → Reload Character Data → Reload**.

**4. Check**

Start a new conversation with that NPC, or open **Bio Editor**, select them, and confirm **Runtime Tags** includes your tag (for example `whiterun_hold`). Their bio should gain the description under `## Additional info` in the log.

Also:

- Use the **Bio Editor** tab to edit a character's tags, see **Runtime Tags** (the merged effective list). It's a good place to debug.
- Tags are **case-sensitive** and must match the template name exactly.
- Duplicate tags are applied only once.
- Bios, templates, summaries, private thoughts, and personal reflections may use `{player_name}`; it is replaced with the current player's name at runtime (or `"the player"` if none is present).

### File structure & override system

This section is for people who want to know how the base file, override files work and the best practices for using them.

Character file and tags file both use a **layered** file layout: a base file first, then optional override folders on top.
Later layers win (except `tags`, which appends).

#### Character data (who has which tags / bios)


| Layer                     | Role                                                                | Path                                                                                  |
| ------------------------- | ------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| **1. Base**               | The base file, usually what you download from the Nexus page above. | `<Mantella install>\\data\\Skyrim\\skyrim_characters.csv`                             |
| **2. Mod overrides**      | Shared / mod-manager overrides, usually from mod authors            | `<Skyrim Data>\\SKSE\\Plugins\\MantellaSoftware\\data\\Skyrim\\character_overrides\\` |
| **3. Personal overrides** | Your private edits (safest place for you to customize)              | `Documents\\My Games\\Mantella\\data\\Skyrim\\character_overrides\\`                  |


Load order: **base → mod overrides → personal overrides**.
Later layers win: mod overrides overwrite the base; personal overrides overwrite both. (Exception: `tags` appends instead of replacing, as mentioned above.)

**File naming (character overrides)**

- You can put **multiple files** in an override folder.
- Names are free: `my_edits.csv`, `companions.json`, `whiterun_npcs.csv`, etc. — only the extension matters.
- Supported extensions: `.csv` and `.json`.
- Every file in the folder is loaded; there is no required filename.

#### Bio templates (what each tag means)


| Layer                     | Role                                   | Path                                                                            |
| ------------------------- | -------------------------------------- | ------------------------------------------------------------------------------- |
| **1. Base**               | Default / Nexus template CSVs          | `<Mantella install>\\data\\Skyrim\\bio_templates\\`                             |
| **2. Mod overrides**      | Shared template packs from mod authors | `<Skyrim Data>\\SKSE\\Plugins\\MantellaSoftware\\data\\Skyrim\\bio_templates\\` |
| **3. Personal overrides** | Your private tag text edits            | `Documents\\My Games\\Mantella\\data\\Skyrim\\bio_templates\\`                  |


Load order: **base → mod → personal**.
Later layers win: mod overwrites base; personal overwrites both. Same tag name in a later folder replaces the earlier description.

**File naming (bio templates)**

- You can put **multiple CSV files** in the same `bio_templates` folder.
- They do **not** have to be named `bio_templates.csv`. That name is only the default Mantella creates if the folder is empty.
- Any filename works as long as it ends in `.csv` — for example: `holds.csv`, `questlines.csv`, `my_custom_tags.csv`.
- Each file must have columns `tag` and `description`.
- All CSVs in the folder are loaded and merged into one tag dictionary. If the same tag name appears in more than one file (or a later layer), the **last one loaded wins** (later folder layers always beat earlier ones; within a folder, load order follows the directory listing).

Example layout:

```
data\\Skyrim\\bio_templates\\
  bio_templates.csv      ← optional; common default / Nexus name
  holds.csv              ← fine
  sidequests.csv         ← fine
  my_custom_tags.csv     ← fine
```

### Reloading after file changes

Editing CSVs on disk does **not** update Mantella automatically — character data and bio templates are loaded into memory at startup.

After you change `skyrim_characters.csv`, any `character_overrides` file, or any file under `bio_templates`:

1. Open the **Other** settings tab in the Mantella UI.
2. Find **Reload Character Data**.
3. Click the **Reload** button.

That reloads character CSVs, overrides, **and** bio templates from disk (it recreates the game data in memory). See also [Reload Character Data](#reload-character-data).

**Notes**

- If a conversation is active, Reload Character Data **ends that conversation** first, then reloads.
- You can also fully restart Mantella instead; Reload is the faster option while the UI is already open.
- After reloading, start a **new** conversation (or re-select the NPC in Bio Editor) to see updated tags/bios.

## Dynamic Events (tag feature)

### What are dynamic events?

Dynamic events are a **feature of the character tag system**. You write them inside a tag's description in a bio templates CSV — same place as normal tag text — but they behave differently at runtime.

A tag description can hold two kinds of content:


| Content                 | What it looks like                 | Where it goes                                                                                |
| ----------------------- | ---------------------------------- | -------------------------------------------------------------------------------------------- |
| **Static tag text**     | Ordinary sentences / bullets       | Appended to the NPC's **bio** (`## Additional info`), like any other tag                     |
| **Dynamic event lines** | `- <unix_timestamp>: <event text>` | **Not** added to the bio. Merged into the NPC's **memory timeline** (conversation summaries) |


Format for an event line (must start the line):

```
- <unix_epoch_seconds>: <event text>
```

### Quick Start: create a dynamic event in a tag

Example tag description (static text + two dated event lines):


| tag             | description                                                                                                                                                                                                             |
| --------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `whiterun_hold` | `NPCs in Whiterun Hold know of the Dragonborn.` *(static — goes into the bio)* `- 1739270400: {player_name} became Thane of Whiterun` *(dynamic event)* `- 1740000000: {player_name} defeated Alduin` *(dynamic event)* |


Need a Unix timestamp? Open the **Other** tab and use **Real World Timestamp** → **Get Timestamp** (see [Real World Timestamp](#real-world-timestamp)), then paste it into your event line.

Assign the tag the same way as any other tag (`tags` / `tags_overwrite`). After editing templates, use **Other → Reload Character Data → Reload**.

---

Now let's talk about what a dynamic event does, and when you need it.

### Feature 1: Chronological mixing with summaries

Conversation summaries and dynamic events can both carry **Unix timestamps**. At runtime, when Mantella builds an NPC's memory for an active conversation, timestamped dynamic events are **mixed with timestamped summaries in time order**. Timestamps are stripped before the text is sent to the LLM — the model only sees the ordered story.

#### Why does order matter?

Sometimes *when* something became true matters as much as the fact itself.

Suppose a snobbish Whiterun noble talked down to you for weeks. Those rude conversations are already in their summary. If you only put *"I am now the Thane of Whiterun"* into static tag text, that fact sits in the bio forever — but the old summaries still read as if they chose to insult you *while* you were Thane. The LLM often keeps treating you poorly, which is wrong.

With a dynamic event, `"became Thane of Whiterun"` gets a timestamp **after** those earlier summaries. In the next conversation the memory timeline ends with the Thane appointment, so the noble can plausibly change tone — respect, flattery, sudden politeness — because the status change sits in the correct place in history.

The same pattern works for quest endings, romance turning points, guild promotions, and anything else where past behavior should no longer apply after a dated beat.

#### What about content that is *not* timestamped?


| Item                                                                 | Behavior                                                                         |
| -------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| **Legacy summaries** (older summary paragraphs with no `ts=` marker) | Kept in their original file order and placed **before** the timestamped timeline |
| **Static tag text** (no event-line pattern)                          | Stays in the **bio** only — it never enters the memory timeline                  |
| **Timestamped summaries** + **dynamic events**                       | Merge-sorted together by timestamp (oldest → newest)                             |


So: undated memory stays at the front as a fixed block; everything with a timestamp is ordered by when it happened.

---

### Feature 2: New developments since last meeting

When you talk to an NPC again, Mantella also checks whether any dynamic events happened **after** your last recorded conversation with them.

**How detection works**

1. Find the **latest timestamp** among that NPC's timestamped summary blocks (the last time their memory was written with a `ts=` marker).
2. Any dynamic event whose timestamp is **strictly later** than that latest summary is treated as new.
3. If the NPC has **no** timestamped summaries yet, every dynamic event counts as new (baseline is `0`).

When the conversation starts, in runtime, those new events are listed in a separate block at the end of memory:

```
New developments since last meeting:
- {player_name} became Thane of Whiterun
- {player_name} defeated Alduin
```

That makes recent plot beats stand out: the NPC is not only remembering history in order — they are explicitly nudged about what changed since you last spoke. NPCs will react to these new developments automatically.

---

### Full example

**Shared setup**

Sildor is a Whiterun snob. You already talked twice; both times he insulted you. Those chats are already in his summaries:


| Timestamp    | Summary                                                                                                      |
| ------------ | ------------------------------------------------------------------------------------------------------------ |
| `1739000000` | Sildor mocked {player_name} as a muddy traveler with no standing. He refused help and ended the talk curtly. |
| `1740000000` | Sildor dismissed {player_name} again, joking that Jarl Balgruuf would never take such a person seriously.    |


His base personality (always in the bio):

```
Sildor is a wealthy, snobbish noble in Whiterun who looks down on outsiders and commoners.
```

You later become Thane of Whiterun. Below: same fact, two ways to put it on the `whiterun_hold` tag — and how that changes the next conversation.

---

#### A. Thane as **static** tag text (the problem)

**Tag**


| tag             | description                                                                           |
| --------------- | ------------------------------------------------------------------------------------- |
| `whiterun_hold` | NPCs in Whiterun Hold know of the Dragonborn. {player_name} became Thane of Whiterun. |


**What the LLM sees**

Bio gets the Thane line under `## Additional info`. Memory is only the old summaries — no order that puts Thane *after* the insults:

```
## Additional info
NPCs in Whiterun Hold know of the Dragonborn. {player_name} became Thane of Whiterun.

(memory)
- Sildor mocked {player_name} as a muddy traveler…
- Sildor dismissed {player_name} again…
```

**How Sildor responds**

He often stays rude. The model sees past contempt *and* “you are Thane” at the same time, with no clear before/after — so it treats the insults as if he chose them while you were already Thane, and keeps that tone.

---

#### B. Thane as a **dynamic** event (the fix)

**Tag**


| tag             | description                                                                                          |
| --------------- | ---------------------------------------------------------------------------------------------------- |
| `whiterun_hold` | NPCs in Whiterun Hold know of the Dragonborn. `- 1740500000: {player_name} became Thane of Whiterun` |


**What the LLM sees**

Static tag text still goes to the bio. The dated line goes into memory, sorted after both summaries. Because its timestamp is later than the latest summary, it also appears under **New developments**:

```
## Additional info
NPCs in Whiterun Hold know of the Dragonborn.

(memory)
- Sildor mocked {player_name} as a muddy traveler…
- Sildor dismissed {player_name} again…

New developments since last meeting:
- {player_name} became Thane of Whiterun
```

**How Sildor responds**

He can change tone — respect, flattery, sudden politeness — because the memory clearly shows: insults first, *then* you became Thane.

After you talk again and a newer summary is saved, the Thane line stays in the chronological timeline but drops out of **New developments** (only events newer than the latest summary show there).

## Lorebook

### What is the lorebook?

The lorebook is a list of **keys** and **descriptions** (stored in CSV files).
It is very handy when you want to teach the LLM facts about custom lore, places, relationships, etc. **only when they come up**, instead of stuffing every bio with long irrelevant context all the time.

When Mantella builds a prompt, it looks for those keys in the context — for example the current `{location}`, recent chat, or in-game events (will talk more about where it scans for the key below). If a key is found and matched, its description is inserted wherever you put `{lorebook}` in the prompt.

It works for conversation prompts and also for vision, memory, inner monologue, personal reflection, and resummarize prompts if those include `{lorebook}`.

Unlike character tags (which permanently expand an NPC's bio), lorebook entries are **situational**: they only appear when a matching key shows up in the context.

**Examples**

1. **Breezehome (location-triggered).** You want NPCs to know how your Breezehome looks. Create a lorebook entry describing the decorations, hearth location, furniture, rooms, etc. Because Mantella supports `{location}`, when you are at Breezehome the location value is `Breezehome`, the lore is pulled in, and the NPC can be aware of your home and surroundings in the current conversation without that text living in every bio.
2. **Custom lore talked about in chat.** You opened a famous restaurant in Riverwood called **In and Out**. Instead of putting that in every bio, prompt, or tag (so it burns tokens and can distract from the current topic), put it in the lorebook. It only appears when you or an NPC mentions it — for example you say *"Hey, let's go to the In and Out."* You do not have to explain what that is; the lore is pulled up and the NPC already knows.

Note that there is no single "correct" lorebook. Keys and descriptions are up to your creativity and the story you want the LLM to know.

**Important:** lorebook text only appears if your prompt includes `{lorebook}`. Default prompts do not include it — add the variable yourself (see below).

### Tags vs lorebook

Lorebook is **not** meant to replace tags. They work **side by side** and complement each other.

**Tags** are for world knowledge that should **always** be present for the NPCs who have them — things that shape how people treat you and how they talk, whether the current conversation mentions them or not. Example: use a `whiterun_hold` tag so Whiterun people know you are Thane of Whiterun, or that you are the Dragonborn. Not every chat will bring those up, but people still speak with respect. Same idea for shared local knowledge: everyone in Whiterun knows where the Bannered Mare is, no matter what topic you are on. That belongs on a tag so it lives in the bio every time.

**Lorebook** is for context you only want **when it is relevant**. You do not want Lydia thinking about Breezehome's decorations while you two are in Solitude talking to the queen. You want her to compliment your little home when you are actually in Breezehome. That is where the lorebook comes in: inject the detail on demand (via location, a spoken name, an event, etc.), then leave it out of every other conversation.


|                 | **Tags**                                                                  | **Lorebook**                                                |
| --------------- | ------------------------------------------------------------------------- | ----------------------------------------------------------- |
| When it appears | Always (for NPCs with that tag)                                           | Only when a key matches scanned text                        |
| Best for        | Standing world knowledge, status, shared local facts                      | Situational detail (rooms, custom places, one-off lore)     |
| Example         | `whiterun_hold`: you are Thane / Dragonborn; Bannered Mare is in Whiterun | `Breezehome`: furniture and layout only while you are there |


### How matching works

Mantella scans text from:


| Source                                                                                         | Included?                    |
| ---------------------------------------------------------------------------------------------- | ---------------------------- |
| Prompt variables used in that prompt (e.g. `{location}`, `{name}`, `{weather}`, `{time}`, etc) | Yes                          |
| Conversation history (spoken turns)                                                            | Yes                          |
| Recent in-game / custom events                                                                 | Yes                          |
| `{bio}` / `{bios}` / `{conversation_summary}` / `{bios_and_summaries}` / related memory blocks | **No** (excluded on purpose) |
| `{lorebook}` itself                                                                            | **No** (avoids recursion)    |


So `{location}` becoming `Breezehome`, or the player saying "Let's go to the In and Out", can trigger an entry — but text that only exists inside the NPC bio or summary will not, by design. Put shared world facts in the lorebook (or tags) instead of relying on bios to trigger keys.

Matched entries are sorted alphabetically by key and inserted wherever you placed `{lorebook}`.

### Quick start: create an entry

Follow these steps to add custom lorebook entries without touching a large base CSV. The examples below match the two use cases above.

**1. Create the entries**

Create (or edit) a CSV under your personal lorebook folder:

`Documents\\My Games\\Mantella\\data\\Skyrim\\lorebook\\my_custom_lore.csv`

Contents:

```
key,description
Breezehome,"Player home in Whiterun. Interior: warm firepit in the main room, weapon racks by the door, a cooking spit and pantry downstairs, a double bed and wardrobe upstairs, and shelves of books and trophies along the walls."
In and Out,"A famous restaurant in Riverwood known for quick meals and packed tables. Locals and travelers alike recommend it."
```

Any `.csv` name is fine. Columns must be `key` and `description`.

**2. Put** `{lorebook}` **in your prompt**

Open the relevant prompt in the **Prompts** tab (for example **Skyrim Prompt**) and add `{lorebook}` where you want matched entries to appear — often near the end, after location / weather / summary.

Example snippet:

```
The conversation takes place in {language}.
{conversation_summary}
{lorebook}
```

You can also add `{lorebook}` to multi-NPC, radiant, vision, memory, inner monologue, personal reflection, or resummarize prompts if those should receive lore too.

**3. Reload**

Go to **Other → Reload Character Data → Reload** (or restart Mantella).

**4. Check**

Start a **new** conversation, then either:

- Stand in **Breezehome** (so `{location}` contains `Breezehome`), or
- Say something like *"Let's go to the In and Out."*

Matched entries are injected as lines like:

```
- [Breezehome]: [Player home in Whiterun. Interior: ...]
- [In and Out]: [A famous restaurant in Riverwood ...]
```

If nothing matches, `{lorebook}` expands to empty text.

Also:

- Matching is **case-insensitive** (`breezehome` and `Breezehome` both hit the same entry).
- Keys match as whole words / tokens (word-boundary style). `Breezehome` matches inside `at Breezehome,` but not inside a longer glued word.
- Duplicate keys across files collapse to one entry; the **last loaded** description wins (see override order below).
- Empty keys or empty descriptions are skipped.

### File structure & override system

Lorebook files use the same **layered** layout as bio templates: a base folder first, then optional override folders on top. Later layers win for the same key.


| Layer                     | Role                                                                    | Path                                                                       |
| ------------------------- | ----------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| **1. Base**               | Default / shared lore CSVs shipped with Mantella (or packs you drop in) | `<Mantella install>\\data\\Skyrim\\lorebook\\`                             |
| **2. Mod overrides**      | Shared packs from mod authors / mod managers                            | `<Skyrim Data>\\SKSE\\Plugins\\MantellaSoftware\\data\\Skyrim\\lorebook\\` |
| **3. Personal overrides** | Your private lore edits (safest place to customize)                     | `Documents\\My Games\\Mantella\\data\\Skyrim\\lorebook\\`                  |


Load order: **base → mod overrides → personal overrides**.
Later layers win: mod overwrites base; personal overwrites both. Same key name in a later folder replaces the earlier description.

**File naming**

- You can put **multiple CSV files** in the same `lorebook` folder.
- They do **not** have to be named `lorebook.csv`.
- Any filename works as long as it ends in `.csv` — for example: `places.csv`, `factions.csv`, `my_custom_lore.csv`.
- Each file must have columns `key` and `description`.
- All CSVs in the folder are loaded and merged into one dictionary. If the same key appears in more than one file (or a later layer), the **last one loaded wins** (later folder layers always beat earlier ones; within a folder, load order follows the directory listing).

Example layout:

```
data\\Skyrim\\lorebook\\
  lorebook.csv           ← optional; common default name
  places.csv             ← fine
  factions.csv           ← fine
  my_custom_lore.csv     ← fine
```

### Reloading after file changes

Editing CSVs on disk does **not** update Mantella automatically — lorebook entries are loaded into memory when the lorebook manager starts (conversation / summary setup).

After you change any file under `lorebook`:

1. Open the **Other** settings tab in the Mantella UI.
2. Find **Reload Character Data**.
3. Click the **Reload** button.

That recreates game data and the rememberer from disk (including lorebook CSVs). Starting a new conversation then loads a fresh lorebook for chat prompts as well. See also [Reload Character Data](#reload-character-data).

**Notes**

- If a conversation is active, Reload Character Data **ends that conversation** first, then reloads.
- You can also fully restart Mantella instead; Reload is the faster option while the UI is already open.
- After reloading, start a **new** conversation and mention a key (or rely on location / events) to confirm the entry appears under `{lorebook}`.
- Remember: without `{lorebook}` in the active prompt, entries never show up even if they match.

## Multiple Profile System

### Use cases

Why use multiple profiles?

Parameters such as `presence_penalty`, `temperature`, `top_p`, and `repetition_penalty` slightly change the tone of the LLM. Different providers can also produce different response quality.

- **Blind-test parameters or providers** — set up several profiles (different penalties/temps, or different OpenRouter providers) and use random selection with weights to find what works best for a model.
- **Less predictable replies** — give profiles different `presence_penalty` / `temperature` values and pick randomly so responses stay more varied.
- **Toggle reasoning/thinking** — enable, disable, or A/B test reasoning per profile; useful on models that otherwise ramble or overthink.
- **Easy manual switching** — keep multiple saved sets and flip between them even when you are not using random selection (no retyping).
- **Different jobs, different settings** — e.g. a creative profile for roleplay and a stricter one for summaries. (Summaries always use Profile 1 regardless of the apply toggles.)
- **Combine with random LLM pools** — both the model and its parameter set can vary together.

### What are model profiles?

**Model Profiles** store LLM parameter sets (temperature, max tokens, provider filters, thinking/reasoning options, etc.)
per service and model, so you do not have to re-enter settings when switching models.

Profiles are edited in the **Model Profiles** settings tab and saved to `data/model_profiles.json`.

### Multiple profiles per model

Each service + model combination can have up to **10 slots** (Profile 1–10). Each slot has:

- **Parameters** — JSON of LLM request parameters
- **Enabled** — whether the slot can be chosen when random selection is used
- **Weight** — relative chance of being picked when random selection is on. A non-negative number (float is fine): can be less than 1 (e.g. `0.5`) or greater than 1 (e.g. `3`). Only the ratios matter — weights `1` and `3` mean a 1:3 chance (25% / 75%). `0` excludes the slot from random picks (same as leaving Enabled off).

### When profiles are applied

Turn on the apply toggles (in Model Profiles / LLM settings) for the contexts you want:

- **Apply Profile for One-on-One Conversations**
- **Apply Profile for Multi-NPC Conversations**
- **Apply Profile for Summaries**

When a toggle is **enabled** and a profile exists for the selected model, that profile’s JSON parameters are used for that context.

When a toggle is **disabled**, Mantella falls back to the default LLM settings from the **LLM** tab (temperature, max tokens, stop sequences, custom token count, etc. — whatever you configured there for the active service/model). Profiles are ignored for that context.

### How a slot is chosen

- **Random LLM selection** — among slots that are enabled with weight > 0, one is chosen by weight.
If none qualify, Profile 1 is used as a fallback.
- **Summaries** — always use Profile 1 (first slot), regardless of Enabled checkboxes or random selection.

### Example parameters JSON (glm 5.2)

```
{
    "max_tokens": 2000,
    "temperature": 1,
    "frequency_penalty": 0.1,
    "top_p": 0.95,
    "stop": [
        "#"
    ],
    "extra_body": {
        "repetition_penalty": 1.1,
        "presence_penalty": 0.1,
        "reasoning": {
            "exclude": true,
            "enabled": true,
            "effort": "xhigh"
        },
        "provider": {
            "only": [
                "z-ai"
            ]
        }
    }
}
```

Supported services for profiles: **OpenRouter**, **OpenAI**, and **NanoGPT**.

### Profiles vs random LLM pools

- **Random LLM pools** pick among different *models*.
- **Profiles** pick among different *parameter sets* for a given model.

They can work together: a model is chosen from the pool, then (when random selection is active)
a weighted profile slot for that model may be chosen.

Sequential LLM pools work the same way: each model in the sequential list can still pick a profile slot. See [Sequential LLM Selection](#sequential-llm-selection).

## Prompt Profiles

### Use cases

**Prompt Profiles** store the *prompt text* itself. You can totally ignore it if you just want to use the original prompts without considering creating prompt profiles. It is a quality of life feature to help you manage prompts and switch between prompts/store different version of prompts.

Why a second system:

- **A/B test prompts** in **runtime** without overwriting the Prompts tab. Keep a “safe default” there and switch between experimental prompts to test them out on the fly. For example, a more experimental director prompt, a shorter memory prompt, or a different inner-monologue style when you want it.
- **Swap jobs quickly** — a punchy one-on-one prompt for tavern talk, a stricter one for serious companions, a group-chat director prompt for multi-NPC. Flip **Active profile** instead of copy-pasting.
- **Keep the Prompts tab as a fallback.** If nothing is activated for a type, Mantella uses whatever is in the Prompts tab. Editing the Prompts tab never rewrites a saved profile, and saving a profile never overwrites the Prompts tab.

### What are prompt profiles?

Named prompt overlays, stored in `data/prompt_profiles.json`. Edited in the **Prompt Profiles** tab.

They are **per prompt type**. Skyrim Prompt, Multi-NPC, Director, Radiant, Memory, Inner Monologue, Personal Reflection, Resummarize, Vision, and the radiant start/end prompts each have their own named set. Fallout 4 conversation prompts are not overlay types — those still come from the Prompts tab. Shared types (memory, thoughts, reflection, vision, radiant start/end) apply regardless of game.

### Edit vs activate

The tab has two dropdowns on purpose:


| Control            | What it does                                                                                                                |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| **Edit profile**   | Which saved text you are looking at / changing. **Save** writes the **Prompt text**; it does **not** make the profile live. |
| **Active profile** | Which text actually runs. Choose **None (use Prompts tab)** to fall back.                                                   |


**Save vs Rename vs Delete** all act on the selected **Edit profile**. None of them change **Active profile** except as noted below.


| Button     | What it does                                                                                                                                                                                                          | What it does *not* do                                                                                                                                        |
| ---------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Save**   | Writes the current **Prompt text**. If **Name** matches the selected edit profile, that profile is updated. If **Name** is new, a **new** profile is created (the old one is left as-is — this is how you duplicate). | Does not rename. Does not activate the result. If **Name** already belongs to a *different* profile, Save is rejected so you do not overwrite the wrong one. |
| **Rename** | Changes only the **label** of the selected edit profile to whatever is in **Name**. If that profile was active, the active slot follows the new name.                                                                 | Does not write **Prompt text**. Unsaved text edits are not stored by Rename — Save those first.                                                              |
| **Delete** | Removes the selected edit profile. If it was active, that type falls back to the Prompts tab.                                                                                                                         | —                                                                                                                                                            |


Typical mix-up: you type a new **Name** and click **Save**, expecting a rename. That **creates a second profile** instead. Use **Rename** to change the name of the one you already have.

### Quick start

1. Open the **Prompt Profiles** tab.
2. Pick a **Prompt type** (for example **Skyrim Prompt**).
3. Paste or write the prompt in **Prompt text**, give it a **Name**, click **Save**.
4. Set **Active profile** to that name.
5. Start or continue a conversation. With [Hot Swap](#hot-swap) on, the next request uses the overlay.

To go back: set **Active profile** to **None (use Prompts tab)**.

**Notes**

- Activating (or editing the already-active profile) notifies Mantella so the overlay is picked up; you do not need Reload Character Data.

## Sequential LLM Selection

### Where to find it

**LLM** tab → **Enable Per-Request Sequential LLM (One-on-One / Multi-NPC)** and the matching **Sequential LLM Pool** JSON fields.

### What it does

 Sequential pools walk the list **in order**. Each NPC reply in that conversation uses the **next** model.

If a model fails to connect or errors mid-request, Mantella **skips to the next** entry instead of giving up. The walk **resets to the first model** when a new conversation starts.

Sequential selection **takes priority** over per-request random LLM selection. If sequential is on and the pool has valid entries, random-per-request is not used for that context.

### Use cases

- Add more variety to the conversation. Each new model would bring something new to the conversation. The sequential order can make sure it follows the exact order you want it to be insread of randomly jumping around (random llm selection).
- **Controlled A/B** — same conversation, model A then B then C, so you can hear the difference without dice rolls.
- Some models are really not great at opening up a conversation. Don't put that on the top of the list.
- **Variety without chaos** — rotate two or three models you already like, instead of a large random pool.

### Quick start

**1. Fill a pool**

Same JSON shape as the random pools:

```
[
{"service": "OpenRouter", "model": "deepseek/deepseek-v4-pro-0813"},
{"service": "OpenRouter", "model": "google/gemini-3.8-flash"},
{"service": "OpenRouter", "model": "google/gemini-3.1-pro-preview"},
{"service": "OpenRouter", "model": "google/gemini-3.8-flash"},
{"service": "OpenRouter", "model": "google/gemini-3.1-pro-preview"}
]
```

Use **Sequential LLM Pool (One-on-One)** and/or **Sequential LLM Pool (Multi-NPC)**.

**2. Turn it on**

Enable **Enable Per-Request Sequential LLM** for that conversation type.

**3. Check**

Start a conversation and look at the log: you should see sequential picks cycling through the list. After you end the chat and start another, it starts at the first model again.

**Notes**

- Empty / invalid pools are skipped; Mantella falls back to the normal (or random) client.
- If **Apply Profile for One-on-One / Multi-NPC** is on, each sequential pick can still apply a [model profile](#multiple-profile-system) for that service+model.

## Bio Sections to Exclude

### Where to find it

**LLM** tab → **Enable Bio Section Filter (Single + Multi)**, the nested **Also Apply to Summary, Inner Thoughts, and Personal Reflection** toggle, and **Bio Sections to Exclude (comma-separated)**.

### What it does

Many character bios are written with markdown section headers such as `## Race`, `## Appearance`, or `## Personal History`. This setting lets you **omit selected top-level sections from the prompt** sent to the LLM.

For example, I use it on a `Personal Secret` section. Those details would give away important things about NPCs the first time I meet them, so I keep that section excluded until we are close enough — then I turn the filter off (or remove that name from the exclude list) mid-conversation via hot swap so the secret can enter the prompt.

- It does **not** edit character CSV files or Bio Editor text. Filtering only happens when Mantella builds a conversation prompt (and, if the nested toggle is on, when it generates summaries / inner thoughts / personal reflections).
- Matching is **case-insensitive** against `## Section Name` headers (top-level `##` only — `###` subsections are ignored as exclude targets).
- Applies to **single-NPC and multi-NPC** conversations that include the player. It does **not** apply to radiant conversations.
- **Also Apply to Summary, Inner Thoughts, and Personal Reflection** (nested under the filter, **off** by default) uses the same exclude list for those memory-generation prompts, including **Bio Editor → Generate Reflection**. Conversation prompts still filter when the main toggle is on; this extra toggle only adds the memory paths. Radiant (player-less) chats stay unfiltered.

Use it when bios are long and you want to save tokens or keep the model focused (for example drop `Personal History` in casual chats, or drop `Race` if it is redundant with other context).

**Mid-conversation:** with **Enable Hot-Swap Settings** on (**Other** tab, default on), you can toggle **Enable Bio Section Filter**, the nested memory toggle, and edit **Bio Sections to Exclude** during an active conversation. The change applies on the next prompt (or the next summary / thoughts / reflection generation) without ending the chat — useful if you want full bios for a serious talk, then strip sections again afterward. See [Hot Swap](#hot-swap).

### Quick start

**1. Turn the filter on**

In the **LLM** tab, enable **Enable Bio Section Filter (Single + Multi)**. Optionally enable **Also Apply to Summary, Inner Thoughts, and Personal Reflection** if you also want those memory prompts to omit the same sections.

**2. List sections to remove**

In **Bio Sections to Exclude (comma-separated)**, enter the header names **without** the `##`. Separate multiple names with commas.

Example:

```
Personal History, Race
```

That removes these blocks from the prompt:

```
## Race
- Nord

## Appearance
- Tall, grey eyes

## Personal History
- Grew up in Whiterun...
```

…leaving something like:

```
## Appearance
- Tall, grey eyes
```

**3. Check**

Start a conversation (or keep talking if one is already active and hot swap is on) and look at the log / prompt: excluded `##` sections should be gone for that NPC. Names that do not appear as `##` headers in the bio are simply skipped (nothing breaks).

**Notes**

- Spaces around commas are fine (`Race, Personal History`).
- Only exact top-level header titles count — `Personal History` will not remove a header named `History`.
- Leave the field empty (or turn the filter off) to send the full bio again.
- Filter on/off, the nested memory toggle, and the exclude list can be changed mid-conversation when hot swap is enabled.

## Private Thoughts

### What it does

Conversation summaries are a factual recap of *what happened*. That is useful, but it can only do so much.

In real life, people constantly surprise you between meetings. After you part, they keep thinking — they form opinions, get excited about something you said — and next time they show up already carrying new motivation, hesitation, eagerness, or even hatred. More often than not you never see how those thoughts developed; you only meet the result. That unseen inner life is what makes people feel unpredictable. These features(Private thoughts, **[Personal reflection](#personal-reflection)**) aim for the same effect: the NPC processes last encounters on their own, then walks into the next one with that new intent already in place.

Ideally, NPCs should be able to evolve emotionally, their relationship with the player should be able to develop as they share more experiences. It would be even better and more realistic if they could naturally form and evolve their own thoughts and opinions based on shared events—independent of direct player input—to motivate their future actions, behaviors, and dialogue. We want the conversations to be more unpredictable in a realistic way, because people are unpredictable by nature. Simply summarizing or presenting facts is not enough; **"Private Thoughts"** and **"Personal Reflection"** are designed to tackle this.

They work on different time scales:

- **Private thoughts** are **short-term**. They only look at the **latest** event, so they capture how the NPC feels *right now* after what just happened — current mood, thoughts, opinions,  suspicion, affection, what they want to bring up next time.
- **[Personal reflection](#personal-reflection)** focuses on **long-term relationships and character development**. It is based on how the NPC feels and how their relationship with you has developed **from the first meeting through today**, not just the last conversation.

A private thought is not invented from nothing. It is the NPC processing *this* conversation on top of how they already see you. Two inputs matter most:

1. Their **[personal reflection](#personal-reflection)** — the long-term relationship they have already been carrying.
2. The small things in the latest talk — wording, tone, expressions, and what they *did* instead of what they admitted out loud. Those unspoken tells become the thought after you part.

### Example

A conversation can look ordinary from the outside and still leave the NPC carrying something you never heard. That is the point of private thoughts.

Say you have been traveling with **Serana after you saved her from her past**. You camp after clearing a Nordic ruin. She teases you for nearly walking into a trap. You ask if she is alright. She shrugs it off, talks about staying ahead of Harkon's people, takes first watch, and goes quiet. Nothing romantic is said. If you only read the summary, it looks like another practical night on the road. Then the LLM would miss the entire subtle emotion shift that happened in this conversation the next time you talk.  See how private thought tackles this problem.

**Conversation summary** (factual — *what happened*):

> Serana and {player_name} camped after clearing a Nordic ruin. Serana teased {player_name} for nearly triggering a pressure plate. {player_name} asked if she was alright. She said she was fine, mentioned staying ahead of Harkon's people, volunteered for first watch.

**Private thought** (unspoken — how she actually feels, in the style the default **Inner Monologue Prompt** is trying to produce: first person, not a recap, with a next-time intent). She is starting to develop feelings she did not show:

> I played it like it was nothing. The trap joke, "I'm fine," taking first watch so I wouldn't have to sit across the fire and actually look at them — that is the version they get. The real one is I have been thinking about them since we left the last village, and it is stupid, and I know it is stupid, and I still keep doing it. I haven't wanted someone near me in a very long time since I left that tomb, not like this, and I am not about to say that out loud to a person who just asked if I was "alright" like I am some shivering mortal. Next time I see them I am going to act like tonight never got under my skin. Then I am probably going to stand a little closer anyway, or ask where they are headed after all this, just to hear that they are not planning to walk off without me. I don't know what this is yet. But I will figure it out.

That paragraph did not come out of nowhere. Two things produced it.

**1. Her personal reflection.** By this camp she already has a longer unspoken write-up of how she sees you — the full example is in [Personal Reflection](#personal-reflection). It already says she stopped waiting for you to turn on her, wants you to stay, does not want you to notice that she wants that, and keeps catching herself picturing you in a future that is not her father's. Tonight's thought is that same relationship, zoomed in on *this* night. The reflection is why "I haven't wanted someone near me in a very long time" is already true before she teases you about a trap. The thought is the short-term version of a feeling the reflection has been carrying since Dimhollow.

**2. What she did in the conversation, not only what she said.** Nothing romantic is spoken. The summary only records teasing, "I'm fine," first watch. But in the actual conversation, her subtle wordings, her expressions, her tones and actions would indicate how she truly feels. These will be hidden by the summary totally, but will be caught by the private thoughts. After you part, those actions, expressions, and word choices are what the thought is allowed to interpret. 

You never hear that spoken. Next time you talk to her, her most recent thoughts are injected as `{private_thoughts}` (or appended to her memory in a group chat). The summary still says the night was uneventful. The thought is why she might suddenly be warmer, sharper, quieter, or a little too interested in whether you are staying — a change you have no conversation to explain.

In a **single-NPC** prompt log, `{private_thoughts}` is the raw paragraph (no extra wrapper). In **multi-NPC / radiant** chats the same text is appended to that NPC's memory section and wrapped so other speakers must not know it:

```
--- PRIVATE THOUGHT (unspoken; other people must not know this) ---
I played it like it was nothing... But I will figure it out. 
--- END PRIVATE THOUGHT ---
```

### Where to find it

**LLM** tab → **Save Private Thoughts** and **Send Private Thoughts to LLM**.

**Prompts** tab → **Inner Monologue Prompt** (the generation prompt). Put `{private_thoughts}` in a **single-NPC** conversation prompt if it is not already there (the default Skyrim / Fallout 4 prompts include it). Multi-NPC and radiant prompts do not accept `{private_thoughts}` — thoughts are appended to each NPC's memory instead (can be toggled off).

**Other** tab → **Save Inner Thoughts Now**, plus the **Also Save Inner Thoughts** toggle under **Save Summary Now**.

**Bio Editor** → **Private thoughts** field (view / edit / save the thought file).

### More details

Here we want to talk more about "Private thoughts".

Private thoughts are a short first-person inner monologue written after a summary is saved, based on the conversation (including wording, tone, and unspoken actions), the bio, [personal reflection](#personal-reflection) when one exists, and past events. The thoughts are stored in a separate folder from memories:

`data/<game>/thoughts/<world_id>/<NPC name>/..._thoughts_X.txt`

They are meant to stay **unspoken**. In multi-NPC / radiant chats the text is wrapped so other speakers must not know it. In a one-on-one chat `{private_thoughts}` is a separate prompt block (you can add a short “do not speak this” line around it in your conversation prompt if you want that extra reminder).

**Only the most recent thoughts are sent to the conversation LLM** — how many is set by **Send Private Thoughts to LLM** (default 1). Older thoughts stay on disk and are **not** dumped into the chat prompt. 

**Saving vs showing** are two different switches:


| Setting                          | Controls                                                                                                                                                                                             |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Save Private Thoughts**        | Whether a new thought is written when a conversation **ends** (requires **Enable Conversation Summaries to be turned on**). Off = no new thoughts created and saved; existing thoughts stay on disk. |
| **Send Private Thoughts to LLM** | How many of the **most recent** thoughts are sent into the next chat. **1** (default) sends only the latest thought; **N** sends the newest N, oldest first; **0** keeps files but sends nothing.  |


### How it shows up in the prompt


| Conversation            | Where the thought goes                                                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Single NPC**          | `{private_thoughts}` — **the most recent N thoughts** (oldest first), as its own block, not mixed into the summary. See the example above.                                                                                                                                       |
| **Multi-NPC / radiant** | Do not use `{private_thoughts}`. **The most recent N thoughts** are appended at the **end of that NPC's memory**, inside one wrapper, so the model can tell it apart from the factual summary. `{conversation_summaries}` / `{bios_and_summaries}` pick that up automatically. |


**How it knows which thought is latest**

Each saved thought is a block in the thought file, stamped with a Unix timestamp (`ts=`), the same kind of real-world clock used by summaries and [dynamic events](#dynamic-events-tag-feature):

```
ts=1739000000
- I don't trust them yet.

ts=1740000000
- I played it like it was nothing. ...
```

Mantella then:

1. Opens the NPC's thought folder and reads the thought file with the **highest file number** (`..._thoughts_1.txt`, `_thoughts_2.txt`, …).
2. Inside that file, finds every block that starts with `ts=<unix_seconds>`.
3. Sends the N blocks with the **largest timestamps**, oldest first, so the newest thought sits closest to the conversation. The `ts=` lines themselves are not sent to the conversation LLM.

If you end a conversation or click **Save Inner Thoughts Now**, the new block is stamped with the current real-world time, so it becomes the latest automatically. Need to see a timestamp? **Other** tab → [Real World Timestamp](#real-world-timestamp). Bio Editor saves the thought file as you edited it — leave the `ts=` lines in place if you want that ordering to stay correct.

If a file has **no** `ts=` markers (older / hand-edited text), Mantella falls back to the **last N blocks in the file**. Timestamped blocks always win over un-timestamped ones.

### Quick start

1. Turn on **Enable Conversation Summaries** (needed for conversation-end thoughts).
2. Turn on **Save Private Thoughts**. Leave **Send Private Thoughts to LLM** at **1** (or raise it to send more recent thoughts).
3. Optional: Confirm your single-NPC prompt includes `{private_thoughts}` (defaults already do).
4. End a conversation (or use **Save Inner Thoughts Now** / **Save Summary Now** with **Also Save Inner Thoughts**).
5. Start a **new** conversation with the same NPC and check the prompt log: the thought block should appear. In **Bio Editor**, open **Private thoughts** to read or edit the file.

**Notes**

- The conversation LLM only sees the **latest** thought. Older thoughts stay on disk and are **not** sent during chat.
- Thoughts use the **summary LLM** (same client as summaries), not the chat model.
- You can change the generation text in **Prompts → Inner Monologue Prompt**, or overlay it with a [prompt profile](#prompt-profiles).
- `{player_name}` in bios / thoughts is replaced at generation and when the thought is injected.
- Bio section filtering can apply to the bios used while *generating* thoughts if **Also Apply to Summary, Inner Thoughts, and Personal Reflection** is on. See [Bio Sections to Exclude](#bio-sections-to-exclude).

## Personal Reflection

### What it does

Conversation summaries are a factual recap of *what happened*. That is useful, but it can only do so much.

In real life, people constantly surprise you between meetings. After you part, they keep thinking — they form opinions, get excited about something you said — and next time they show up already carrying new motivation, hesitation, eagerness, or even hatred. More often than not you never see how those thoughts developed; you only meet the result. That unseen inner life is what makes people feel unpredictable. These features(**[Private thoughts](#private-thoughts)**, Personal reflection) aim for the same effect: the NPC processes last encounters on their own, then walks into the next one with that new intent already in place.

Ideally, NPCs should be able to evolve emotionally, their relationship with the player should be able to develop as they share more experiences. It would be even better and more realistic if they could naturally form and evolve their own thoughts and opinions based on shared events—independent of direct player input—to motivate their future actions, behaviors, and dialogue. We want the conversations to be more unpredictable in a realistic way, because people are unpredictable by nature. Simply summarizing or presenting facts is not enough; **"Private Thoughts"** and **"Personal Reflection"** are designed to tackle this.

They work on different time scales:

- **[Private thoughts](#private-thoughts)** are **short-term**. They only look at the **latest** event, so they capture how the NPC feels *right now* after what just happened — current mood, thoughts, opinions,  suspicion, affection, what they want to bring up next time.
- **Personal reflection** focuses on **long-term relationships and character development**. It is based on how the NPC feels and how their relationship with you has developed **from the first meeting through today**, not just the last conversation.

### Example

Same NPC as the [private thoughts example](#example) — **Serana** — but zoomed out. The reflection is everything since Dimhollow.

Say you found her in that tomb, walked her home, got tangled in her family's mess, and have been traveling with her since. Last night you camped after a ruin. She teased you, said she was fine, took first watch. Nothing personal was said. The [private thought](#private-thoughts) is why she might stand a little closer tomorrow. The reflection is why that shift is not coming out of nowhere: it is how she has come to see you from the first meeting through today.

**Conversation summaries** (factual — the whole history, compressed):

> {player_name} found Serana in Dimhollow Crypt. She was wary, asked for an escort home, and kept her past to herself. Serana and {player_name} reached Castle Volkihar. After facing Harkon, she asked for space and later chose to keep traveling with {player_name} rather than stay with her father. They have been on the road together since — hunting the prophecy, clearing ruins, camping. Last night she teased {player_name} about a trap, said she was fine, and took first watch.

**Personal reflection** (unspoken — how she sees the relationship *over time*, in the style the default **Personal Reflection Prompt** is trying to produce: first person, sectioned, not a recap of last night). The feelings she did not show have been building since the beginning:

> **Relationship:** {player_name}: They pulled me out of that tomb when I had no reason to trust a stranger, and I still remember keeping them at arm's length the whole way to the castle. I told myself they were useful. That was a lie I needed at the time. Somewhere between then and now I stopped waiting for them to turn on me, and I have not said that out loud because saying it would make it real. I still get sharp when they get too close to the old wounds. That is not them being the problem. That is me. I want them to stay. I also want them not to notice that I want that.
>
> **Current Life:** I am not locked in the dark anymore, and I am still not sure this is better. Traveling with them is the closest thing I have had to a life that is mine in a very long time. I keep waiting for it to end.
>
> **Long-Term Goals & Desires:** Harkon and the prophecy still sit in the back of my head, but they are not the only thing I am moving toward anymore. I want a future that is not my father's, and I keep catching myself picturing them in it, which is a problem I have not decided how to handle.
>
> **Future Outlook:** I expect they will keep walking into danger like it is nothing. I expect I will keep following. What I am afraid of is the day they decide they are done with a vampire who cannot even say she is glad they stayed.

You never hear that spoken. Next time you talk to her, the latest reflection is appended to her **bio** (single-NPC and group chat).  In the prompt log it looks like this (a new section appended at the end of the bio section):

```
## Personal Reflection (Don't speak out loud, these are private thoughts)
### Relationship:
- {player_name}: They pulled me out of that tomb when I had no reason to trust a stranger...
....
### Future Outlook
I expect they will keep walking into danger like it is nothing....
```

### Where to find it

**LLM** tab → **Save Personal Reflection** and **Send Personal Reflection to LLM**.

**Prompts** tab → **Personal Reflection Prompt**.

**Other** tab → **Save Personal Reflection Now**, plus **Also Save Personal Reflection** under **Save Summary Now**.

**Bio Editor** → **Personal Reflection** field, **Save Reflection**, and **Generate Reflection**.

### More details

Here we want to talk more about "Personal reflection".

Personal reflections are a longer first-person write-up of how an NPC currently sees their life — especially their relationship with you, what they want, and what they expect next. They are stored separately from both summaries and private thoughts:

`data/<game>/reflections/<world_id>/<NPC name>/..._reflections_X.txt`

Unlike thoughts (which focus on the conversation that just ended), a reflection treats the **whole history** as one continuous experience. The generation prompt is told to keep the previous reflection as a baseline and only change a section when something actually shifted. If nothing important changed, it should repeat the previous text rather than invent growth.

An NPC **must already have summaries** before a reflection is written. No summary file → that NPC is skipped.

**Only the latest reflection is sent to the conversation LLM.** Older reflections stay on disk and are **not** dumped into the chat prompt.

**Saving vs showing** are two different switches:


| Setting                             | Controls                                                                                                                                                                                          |
| ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Save Personal Reflection**        | Whether a new reflection is written when a conversation **ends** (after a summary). Manual **Save Personal Reflection Now** and **Bio Editor → Generate Reflection** still work when this is off. |
| **Send Personal Reflection to LLM** | Whether the **latest** reflection is sent into the next chat. **Latest** (default) sends **only that one reflection**, not the full history; **None** keeps files but sends nothing.              |


There is **no** `{personal_reflection}` prompt variable. When load mode is **Latest**, Mantella appends it after the (filtered) bio as:

```
## Personal Reflection (Don't speak out loud, these are private thoughts)
...
```

That heading is added at prompt time; the stored file does not include it. Because it lives on the bio, `{bio}` / `{bios}` / `{bios_and_summaries}` all pick it up.

**Save Summary Now** has its own **Also Save Personal Reflection** toggle and does **not** use **Save Personal Reflection**.

**How it knows which reflection is latest**

Each saved reflection is a block in the reflection file, stamped with a Unix timestamp (`ts=`), the same kind of real-world clock used by summaries, [private thoughts](#private-thoughts), and [dynamic events](#dynamic-events-tag-feature):

```
ts=1739000000
### Relationship:
- {player_name}: I still don't know what to make of them.

ts=1740000000
### Relationship:
- {player_name}: Something has shifted, even if I have not said it.
```

Mantella then:

1. Opens the NPC's reflection folder and reads the reflection file with the **highest file number** (`..._reflections_1.txt`, `_reflections_2.txt`, …).
2. Inside that file, finds every block that starts with `ts=<unix_seconds>`.
3. Sends the block with the **largest timestamp** — that is the latest reflection. The `ts=` line itself is not sent to the conversation LLM.

If you end a conversation, click **Save Personal Reflection Now**, or **Generate Reflection** in Bio Editor, the new block is stamped with the current real-world time, so it becomes the latest automatically. Need to see a timestamp? **Other** tab → [Real World Timestamp](#real-world-timestamp). Bio Editor **Save Reflection** writes the file as you edited it — leave the `ts=` lines in place if you want that ordering to stay correct.

If a file has **no** `ts=` markers (older / hand-edited text), Mantella falls back to the **last block in the file**. Timestamped blocks always win over un-timestamped ones.

### Quick start

1. Make sure the NPC already has at least one conversation summary (talk and end a chat, or **Save Summary Now**).
2. Turn on **Save Personal Reflection**. Leave **Send Personal Reflection to LLM** on **Latest**.
3. End a conversation, or click **Other → Save Personal Reflection Now**, or in **Bio Editor** click **Generate Reflection**.
4. Start a **new** conversation and check the prompt: the bio should end with the **Personal Reflection** heading. You can also read / edit the text in Bio Editor.

**Notes**

- The conversation LLM only sees the **latest** reflection. Older reflections stay on disk and are **not** sent during chat.
- Reflections use the **summary LLM**.
- **Generate Reflection** in Bio Editor uses the bio and summary text currently in those editors (handy for testing a prompt without ending a chat).
- Same bio-filter nested toggle as thoughts/summaries can strip sections from the bios used *while generating* a reflection.
- `{player_name}` is resolved in the bio that goes into generation and when the reflection is appended for chat.

## Drop Last Sentences

### Where to find it

**LLM** tab → **Drop Last Sentences (Single NPC)**.

### What it does

Many chat models tack a trailing question or filler onto otherwise good replies (“So, what do you think?” / “Is there anything else?” "Do you want A or B?"). This setting **drops the last N spoken sentences** of each single-NPC response.

Dropped sentences are:

- **Not spoken** in-game
- **Not written** into conversation history (so they cannot leak into the next turn or the summary)

At least **one** sentence is always kept. Set to **0** to disable (default).

**Only single-NPC conversations.** Multi-NPC is unchanged.

**Tradeoff:** Mantella has to generate those extra sentences before it knows which ones to throw away, so a higher N means a longer wait before the NPC starts talking. Setting it to a small number like 1 won't cause any noticable delays.

### Quick start

1. Open the **LLM** tab.
2. Set **Drop Last Sentences (Single NPC)** to `1` (a common starting point).
3. Talk to an NPC. Trailing questions / wrap-up lines should disappear from speech and from the live history.

If replies feel clipped, set it back to `0` or combine with a lower **Max Sentences per Response** instead.

## Send Only Bios

### Where to find it

**LLM** tab → **Send Only Bios (Single + Multi)**.

### What it does

When enabled, conversation **summaries / memories** (and the single-NPC `{private_thoughts}` block) are omitted from chat prompts. Bios still go out as usual, including a personal reflection that is attached to the bio.

Useful when you want to test a bio or tag setup without old memory steering the model, or when a summary file has gone messy and you need a clean conversation without deleting files.

Radiant conversations and other non-chat prompts are not the point of this toggle; it applies to **single-NPC and multi-NPC** player conversations.

### Quick start

Enable it in the **LLM** tab, start (or continue, with hot swap) a conversation, and confirm the prompt has bios but no “summary of past events” / thought block. Turn it off to send memories again.

## Reload Character Data

### Where to find it

**Other** tab → **Reload Character Data** → **Reload** button.

### What it does

Character CSVs, character overrides, bio templates, and lorebook files are loaded into memory when Mantella starts. Editing those files on disk does **not** update a running session by itself.

**Reload Character Data** recreates game data from disk so your latest edits apply without fully restarting Mantella. It refreshes:

- Base character CSV + character overrides
- Bio templates (character tags)
- Lorebook CSVs

### Quick start

Suppose you just added a tag in `Documents\\My Games\\Mantella\\data\\Skyrim\\bio_templates\\my_custom_tags.csv` and assigned it on an NPC override CSV.

1. Open the **Other** tab.
2. Find **Reload Character Data**.
3. Click **Reload**.
4. Start a **new** conversation with that NPC (or re-select them in **Bio Editor**) and confirm the change (e.g. **Runtime Tags** / bio text).

**Notes**

- If a conversation is active, Reload **ends that conversation first**, then reloads.
- The game / Mantella must already be started for the button to work.
- A full Mantella restart also reloads everything; Reload is the faster option while the UI is open.

## Save Summary Now

### Where to find it

**Other** tab → **Save Summary Now** → **Save Summary** button, with nested toggles **Also Save Inner Thoughts** and **Also Save Personal Reflection**.

The same tab also has **Save Inner Thoughts Now** and **Save Personal Reflection Now** (those do **not** write a new summary).

### What it does

Normally Mantella writes a conversation summary (and log, if enabled) when a conversation **ends**. **Save Summary Now** triggers that save **immediately** while the conversation **keeps going**.

The two nested toggles (both **on** by default) only affect **this button**. They do **not** change what happens when a conversation ends — that is still **Save Private Thoughts** / **Save Personal Reflection** on the LLM tab.


| Nested toggle                     | Extra work on this click                                                                                       |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Also Save Inner Thoughts**      | After the summary, generate a [private thought](#private-thoughts) for NPCs in the chat                        |
| **Also Save Personal Reflection** | After the summary, generate a [personal reflection](#personal-reflection) for NPCs that already have summaries |


**Save Inner Thoughts Now** / **Save Personal Reflection Now** skip the summary step: thoughts can be written from the live conversation even without a new summary; reflections still need existing summary files on disk (NPCs with none are skipped).

**Use cases**

- **Crash / unexpected quit:** the game crashes, freezes, or you quit without Mantella receiving a normal end-conversation event — you can still preserve memory for the NPC before you lose the session.
- **Testing summary LLMs:** you want to find the best model for summaries. Keep the same conversation open, switch the summary LLM in settings, click **Save Summary**, and compare the written summary directly — no need to end and restart the chat for each candidate.
- **Testing thoughts / reflections** the same way, without ending the conversation or flipping the conversation-end toggles.

### Quick start

1. Have an **active** conversation in-game (at least enough dialogue to summarize).
2. Open the **Other** tab.
3. Set the nested toggles if you also want thoughts and/or reflections.
4. Click **Save Summary**.
5. Confirm the UI message (something like "Summary/log save triggered") and/or check the NPC's summary / thoughts / reflection files.

You can keep talking afterward. When the conversation later ends normally, Mantella may generate **another** summary (and thoughts/reflections, if those conversation-end toggles are on) — so you might get both the mid-conversation save and the end-of-conversation save.

**Notes**

- Requires an active conversation; otherwise the button reports there is nothing to summarize.
- Uses the currently selected summary model / settings (including recent UI changes to the summary LLM when possible).
- After a manual save, a normal end-of-conversation summary may still run later — keep that in mind when comparing test summaries.
- Manual thought / reflection buttons still work when **Save Private Thoughts** / **Save Personal Reflection** are off.

## Real World Timestamp

### Where to find it

**Other** tab → **Real World Timestamp** → **Get Timestamp** button.

### What it does

Generates the current **Unix timestamp** (seconds since epoch, UTC) so you can paste it into places that need a real-world time marker — most often **dynamic event** lines in bio templates.

## Hot Swap

### Where to find it

**Other** tab → **Enable Hot-Swap Settings** (default: on).

### What it does

When you change settings in the UI while Mantella is running, those changes need to reach the live game session. **Hot swap** applies many setting updates **without ending the current conversation**.


| Setting               | Behavior                                                                                                                                                                             |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Enabled** (default) | LLM model settings, prompts, [prompt profiles](#prompt-profiles), bio filter, sequential/random pools, and similar config apply on the next game request; the conversation continues |
| **Disabled**          | Settings changes fall back to classic behavior: the conversation is ended and the route restarts with the new config                                                                 |


Character CSV / bio template / lorebook file edits are different — those still need **Reload Character Data** (or a restart), which ends an active conversation. Hot swap is for **config/UI settings**, not for reloading character files from disk.

### Quick start

**Example: toggle the bio section filter mid-chat**

1. Confirm **Other → Enable Hot-Swap Settings** is on.
2. Start (or continue) a conversation with an NPC.
3. Open the **LLM** tab and turn **Enable Bio Section Filter (Single + Multi)** on or off (optionally edit **Bio Sections to Exclude**).
4. Keep talking in-game — on the next reply, the prompt uses the new filter state without ending the conversation.

**Another example:** change a prompt or LLM parameter while chatting; with hot swap on, the next turn uses the updated settings instead of restarting the conversation.

**Notes**

- Hot swap runs when Mantella next processes a game request after config values have changed.
- If hot swap fails or is disabled, Mantella reinitializes the route (classic restart behavior).
- Use [Reload Character Data](#reload-character-data) when you edited CSVs/templates on disk; use hot swap when you changed settings in the UI. See [Reload Character Data](#reload-character-data).
- Activating a prompt profile (or saving the one that is already active) is picked up the same way as editing the Prompts tab.

## Live Conversation

### Where to find it

The **Live Conversation** tab in the Mantella UI (not inside Settings).

### What it does

Shows the **active conversation as JSON** so you can inspect it, edit a bad turn, or undo without ending the chat.

When a model returns garbage, a duplicated line, or you misspoke, you do not have to live with that text in history (and later in the summary). Reload the current thread, fix it, save it back.


| Button                       | What it removes / does                                                                      |
| ---------------------------- | ------------------------------------------------------------------------------------------- |
| **Reload**                   | Fetch the current in-memory conversation into the editor                                    |
| **Save**                     | Apply your edited JSON as the live history                                                  |
| **Undo last round**          | Remove the last **player** turn **and everything after it** (player line + NPC reply)       |
| **Undo NPC reply**           | Keep the last player line; drop only the NPC response                                       |
| **Remove last user message** | Drop the last message only if it is from the player (the most recent message must be yours) |


The game / Mantella must already be running with an **active** conversation that has at least some messages.

### Quick start

**Example: the NPC just output nonsense**

1. Open **Live Conversation**.
2. Click **Reload**.
3. Either click **Undo NPC reply** (keeps your last line so they can answer again), or edit the JSON by hand and click **Save**.
4. Continue in-game. The next request uses the cleaned history.

**Example: you regret the last exchange**

Click **Undo last round** to roll back both sides of that beat, then speak again.

**Notes**

- There is no conversation if the game has not started, or if the thread is still empty — Reload will say so.
- Saving malformed JSON fails; check the status line / log and Reload to get a known-good copy.
- Undo buttons refresh the editor with the new JSON so you can confirm what is left.

## bios_and_summaries Prompt Variable

### Where to use it

**Prompts** tab — put `{bios_and_summaries}` in multi-NPC prompts (for example **Skyrim Multi-NPC Prompt** or **Skyrim Multi-NPC Director Prompt**) wherever you would otherwise put `{bios}` and `{conversation_summaries}` separately.

### What it does

`{bios_and_summaries}` builds **one block per NPC**: that character's bio (including a [personal reflection](#personal-reflection) when load mode is Latest), then their conversation summary / memory (including that NPC's [private thought](#private-thoughts) in multi-NPC chats), kept together, with delimiters so other speakers are told not to use private info.

Instead of a pile of all bios followed by a pile of all summaries, each person gets their own paired section.

### Why it is better than separate bios + summary

The older / default style often looks like:

```
Here are their backgrounds:
{bios}
{conversation_summaries}
```

That **splits** who someone is from what they remember into two distant prompt regions. With several NPCs, the model sees every bio first, then every memory afterward.

In practice, lots of coherence issues are noticed, including context leaking (NPC A talks about NPC B's past memories although NPC A should've never known anything about it), easily mixing up which summary belongs to which person, or treating “background” and “memory” as unrelated piles.

`{bios_and_summaries}` keeps each NPC's identity and history **in one place**. 

After repeated experiments, it greatly improves coherence (tone, relationships, and past events stay attached to the right speaker) and reduces the LLM confusing or cross-wiring characters.


| Approach                              | Layout                           | Typical issue                                                      |
| ------------------------------------- | -------------------------------- | ------------------------------------------------------------------ |
| `{bios}` + `{conversation_summaries}` | All bios, then all memories      | Model can lose which memory goes with which NPC; weaker continuity |
| `{bios_and_summaries}`                | Per NPC: bio + that NPC's memory | Clearer pairing → more coherent replies                            |


You do **not** need both. If you use `{bios_and_summaries}`, drop `{bios}` and `{conversation_summaries}` from that prompt so you are not duplicating the same text.

### Example

Suppose Lydia and Serana are in the conversation.

**Split variables** (`{bios}` then `{conversation_summaries}`) expand roughly like:

```
[This is the beginning of Lydia's bio]
Lydia is a loyal housecarl of Whiterun...
[This is the end of Lydia's bio]

[This is the beginning of Serana's bio]
Serana is a vampire from Castle Volkihar...
[This is the end of Serana's bio]

Lydia: Met {player_name} in Dragonsreach. Agreed to travel together.
Serana: Escaped Dimhollow Crypt with {player_name}. Distrusts the Dawnguard.
```

The bios and memories are in separate stacks — easy for the model to attach Serana's memory to Lydia, or ignore pairing entirely.

`{bios_and_summaries}` expands roughly like:

```
[This is the beginning of Lydia's information...]
[This is the beginning of Lydia's bio...]
Lydia is a loyal housecarl of Whiterun...
[This is the end of Lydia's bio...]

[This is the beginning of Lydia's memory...]
Met {player_name} in Dragonsreach. Agreed to travel together.
[This is the end of Lydia's memory...]
[This is the end of Lydia's information...]

[This is the beginning of Serana's information...]
[This is the beginning of Serana's bio...]
Serana is a vampire from Castle Volkihar...
[This is the end of Serana's bio...]

[This is the beginning of Serana's memory...]
Escaped Dimhollow Crypt with {player_name}. Distrusts the Dawnguard.
[This is the end of Serana's memory...]
[This is the end of Serana's information...]
```

Each NPC's bio and memory stay attached — clearer who knows what, better group-chat coherence.

### Quick start

1. Open the **Prompts** tab.
2. Edit a multi-NPC prompt (for example **Skyrim Multi-NPC Prompt** or **Skyrim Multi-NPC Director Prompt**).
3. Replace the split variables with one combined variable.

**Before:**

```
Here are their backgrounds:
{bios}
{conversation_summaries}
```

**After:**

```
Character backgrounds:

{bios_and_summaries}
```

1. Save / leave the field (hot swap will apply on the next request if enabled). Start or continue a multi-NPC conversation and check the prompt log: each NPC should show bio and memory together.

**Notes**

- Bio section filtering still applies inside the bio portion of `{bios_and_summaries}`.
- The director-style multi-NPC prompt already uses `{bios_and_summaries}` by default — that is the recommended pattern for group chats.
- In multi-NPC chats, do not add `{private_thoughts}`; thoughts ride along inside each NPC's memory half of `{bios_and_summaries}`. In single-NPC chats, use `{private_thoughts}` on the one-on-one prompt instead.

