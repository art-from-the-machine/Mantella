# Mantella
Nexus: https://www.nexusmods.com/skyrimspecialedition/mods/98631

Mantella is a Skyrim mod which allows you to naturally speak to NPCs using OpenAI's [Whisper](https://github.com/openai/whisper) (speech-to-text), OpenAI's ChatGPT (text generation), and [xVASynth](https://github.com/DanRuta/xVA-Synth) (text-to-speech). See here for a video demonstration:

https://www.youtube.com/watch?v=fJPY6sD527A

If you get stuck anywhere in the process, please see the [`#Issues Q&A`](#issues-qa) below or reach out on the Discord:  

https://discord.gg/Q4BJAdtGUE


## Requirements
### Hardware Requirements
There are no discovered minimum requirements at the time of writing for Mantella, but there has been a report of Mantella crashing when running a modlist of 2000 mods. Mantella needs a certain amount of hardware allocation to run successfully, and if this is being soaked up by other hardware intensive mods, it may crash.

The minimum requirements for xVASynth can be found on its [Steam page](https://store.steampowered.com/app/1765720/xVASynth/). It runs in CPU mode by default, using a single CPU core/thread. Only supports GPU acceleration on NVIDIA cards that have CUDA. Using the same GPU as the game will produce stutter. You may try using an older NVIDIA card if you have a free PCI-Express slot for your PC and run Whisper & xVASynth on that.

### Storage Requirements
This mod requires ~27GB of space when xVASynth and all voice models are installed. Temporarily another ~17GB is needed to unpack the voice models.


### Compatability
- Mantella requires Windows 10 / 11
- Mantella has been confirmed to work with the FUS (by pointing skyrim_folder to Skyrim), Librum (by pointing skyrim_folder to overwrite/root), and Wildlands (by pointing skyrim_folder to Wildlander/SKSE) Wabbajack modlists.
- If you have the Unofficial Skyrim Special Edition Patch (USSEP) installed, Mantella needs to be loaded after this mod

## Installation
### Video Walkthrough
A video walking through the installation of Mantella by JackTheFallout can be found below:

https://youtu.be/_mZFkTchwEo

Just a couple of notes, the PapyrusUtil issue mentioned in this video can be resolved by installing the VR version of the file (under "Miscellaneous") if you are a VR user. You also do not need to download the voice models manually if you have Nexus Premium (see below for instructions).


### Skyrim
As Mantella accesses and writes to files within your Skyrim folder, it is unlikely to work correctly if you have Skyrim stored in Program Files. Please ensure that you have Skyrim stored outside of this folder (Such as C:\Games\Steam for example).

### Mantella Files
The Mantella files can be downloaded from Nexus: https://www.nexusmods.com/skyrimspecialedition/mods/98631

#### Mantella Software
Extract this folder somewhere convenient to you.

#### Mantella Spell
This file can be installed in the same way as other mods with your mod manager.


### xVASynth
1. Download xVASynth via Steam (https://store.steampowered.com/app/1765720/xVASynth/) or Nexus (https://www.nexusmods.com/skyrimspecialedition/mods/44184).

2. Download xVASynth trained voice models of Skyrim for all or any characters that you are likely to encounter. You will have to do this manually through the Nexus Mods page or automatically using Nexus Premium, whose API is implemented within xVASynth.

* Under "Optional" (not "Old") from https://www.nexusmods.com/skyrimspecialedition/mods/44184?tab=files and store the zipped files in a folder. Open xVASynth and drag all zipped voice model files from the folder into the voices panel. Wait for the installation to complete (this may take some time; a popup will display when finished saying "x models installed successfully"). If this method doesn't work for you, you can also unzip the models manually into the correct xVASynth folder (xVASynth\resources\app\models\skyrim). Once the extraction is complete, you can delete the zipped voice model files.

* If you are subscribed to Nexus Premium, open xVASynth and select "Get More Voices" from the bottom left corner. Unselect all games except for Skyrim and download all models. Note that this may require restarting a few times for the downloads to properly complete.

3. Download the .lip plugin for xVASynth here: https://www.nexusmods.com/skyrimspecialedition/mods/55605 and download FaceFXWrapper from here (you do not need to download CK64Fixes): https://www.nexusmods.com/skyrimspecialedition/mods/20061. Instructions on how to install these are on the .lip plugin Nexus page. Make sure to place FaceFXWrapper in the plugins folder as stated on the .lip plugin page.

4. Download the Elder Scrolls pronunciation dictionary from here, and follow the instructions to install: https://www.nexusmods.com/skyrimspecialedition/mods/56778/

5. In the xVASynth UI, if "Skyrim" is not already selected, please do so by clicking the arrows symbol in the top left corner. On the navigation bar on the top right of the xVASynth UI, click on the "ae" icon. Once opened, click on the CMUDict dictionary and select "Enable All" in the bottom left corner. Do the same for "xVADict - Elder Scrolls" received from the above step. Once done, close this menu and navigate to the settings menu by selecting the gear icon in the top right corner and ensure that "Audio sample rate (Hz)" is set to 44100. You can also select whether to process voicelines via you CPU or (NVIDIA) GPU from this menu.


### Required Mods
Please follow the installation instructions on each of the linked pages:

SKSE (there is a separate VR version): http://skse.silverlock.org/

VR Address Library for SKSEVR: https://www.nexusmods.com/skyrimspecialedition/mods/58101  
or Address Library for SKSE Plugins: https://www.nexusmods.com/skyrimspecialedition/mods/32444

PapyrusUtil SE (the VR version can be found under "Miscellaneous Files"): https://www.nexusmods.com/skyrimspecialedition/mods/13048


### Optional Mods
These mods aren't strictly necessary for Mantella to work, but they do greatly improve the experience.

No NPC Greetings (recommended so that Mantella voicelines are not interrupted by vanilla voicelines): https://www.nexusmods.com/skyrim/mods/746

World Encounter Hostility Fix - Performance Version (stops certain NPCs from turning hostile when you cast the Mantella spell on them): https://www.nexusmods.com/skyrimspecialedition/mods/91403  
Note that this mod requires the Unofficial Skyrim Special Edition Patch (USSEP). Mantella needs to be loaded after USSEP in your load order.


## Setup & Configuration
1. Set up the MantellaSoftware/config.ini file with your paths to Skyrim (`skyrim_folder`), xVASynth (`xvasynth_folder`), and the Mantella Skyrim mod (`mod_folder`). If you are using a Wabbajack modlist, you may need to try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path and set this as your `skyrim_folder` path. If you are using Mod Organizer 2, you can find the mod folder by right clicking the mod in the Mod Organizer 2 UI and selecting "Open in Explorer". If you are instead using Vortex, you need to point mod_folder to your Skyrim/Data folder. So Vortex users essentially need to take the Skyrim folder path they have set in `skyrim_folder` and add "\Data" to the end of it.

2. Copy your OpenAI secret API key (see here if you need help finding it (you will need to set up an account if you haven't already): https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key) and paste into GPT_SECRET_KEY.txt. Do not share this key with anyone. While there is a free trial, you will need to set up your payment details for the API to work.

3. The applications should be started in this order: Run Mantella.exe (found in the MantellaSoftware folder). It will say "Waiting for player to select an NPC..." when it is ready -> Run Skyrim

4. When you first load the mod, MAKE SURE TO CREATE A SAVE AND RELOAD THAT SAVE. The voicelines will not play otherwise! I learned this the hard way. You do not have to create a new game to do this, you can also create a new save in an existing game. While there have not been issues reported with using Mantella in an existing save so far, please be aware that adding mods mid-game can cause problems.

5. The Mantella spell should be added to your inventory under the Illusion category in the Magic menu once you install the mod. Conversations can be started by selecting an NPC with the spell. You can end a conversation by selecting an NPC with the spell again, or by simply saying "goodbye". If the NPC responds with "safe travels" then the conversation has ended correctly via this latter method. Note that conversations can only be saved to memory (MantellaSoftware/data/conversations/NPC_Name) by either using the spell or by saying "goodbye". If the NPC is unavailable to the mod, the message "Conversation ended." should immediately pop up in the top left corner and the conversation will exit. If the only message you see from the spell is "Conversation ended", please refer to the "Issues Q&A" section for common solutions to this.

6. Voicelines are cached in the MantellaSoftware/data/voicelines/ folder. If this data takes up too much space over time, the contents of voicelines/ can be periodically deleted.

7. If you are experiencing errors, please see the issues Q&A below. Otherwise, please share the details of the errors and your MantellaSoftware/logging.log file on the Mantella Discord #issues channel: https://discord.gg/Q4BJAdtGUE. You can also try enabling debugging in MantellaSoftware/config.ini. This allows Mantella.exe to run without Skyrim needing to be open. There are a few extra options in the debugging section to play around with which are applied when the debugging option is enabled.


## Issues Q&A
### Conversation ends as soon as spell is cast / [Errno 2] No such file or directory: 'path\to\Skyrim Special Edition/some_text_file.txt' 
This is either an issue with the path set for `skyrim_folder` in MantellaSoftware/config.ini, an issue with your Skyrim folder being in Program Files, an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it). 

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscallaneous Files section of the Nexus download page). If you are a SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path.

If you have the required mods installed, then this issue might instead be caused by the `skyrim_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Orgnanizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__skyrim_folder.txt`. If you find this file, then please set its folder as your `skyrim_folder` path.

### ChatGPT API Error: cannot access local variable 'audio_file' where it is not associated with a value
This error occurs when something has failed in a previous step (likely xVASynth). Please check your MantellaSoftware/logging.log file to see the error which occurred before this, which should provide more clarification. If you are still ensure, please share your logging.log file to the Discord's issues channel.

### NPCs keep repeating the same line of dialogue
This is an issue with `mod_folder` not being set to the correct path in MantellaSoftware/config.ini. If you are using Mod Organizer 2, you can find the correct path by right-clicking the Mantella mod in the Mod Organizer 2 UI and selecting "Open in Explorer". If you are using Vortex, you should instead set this `mod_folder` path to your Skyrim/Data folder.

### No message box displayed to say spell has been added / Mantella spell is not in spell inventory
This is an issue with the way the spell mod itself has been installed. Please check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you have Skyrim AE. If it is below 1.6, you have Skyrim SE. If you are using VR, there are separate versions of the required mods for VR (PapyrusUtil tends to catch out a lot of VR users, the VR version of this file is under "Miscellaneous Files" on the download page). If you are running the mod via the GOG version of Skyrim, there are slight differences in setting up a mod manager as discussed in this tutorial: https://www.youtube.com/watch?v=EJYddISZdeo

### RuntimeError('PytorchStreamReader failed reading zip archive: failed finding central directory')
If an xVASynth voice model is corrupted, this error will display in MantellaSoftware/logging.log. Please re-download the voice model in this case. You may alternatively need to redownload xVASynth.

A way to check for other corrupted voice models, is to compare the file sizes within /models/skyrim/ folder of xVASynth. If they diverge from the norms, redownload **just** those. The norms for voice model sizes are **~54 MB** and/or **~90 MB** (v2 voice models) & **~220 MB** or **~260 MB** (v3 voice models)

### Loading voice model... xVASynth Error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
If this xVASynth Error occurs after the "Loading voice model..." message (as can be seen in your MantellaSoftware/logging.log file), this is likely an issue with a corrupted voice model. Please try redownloading the model from https://www.nexusmods.com/skyrimspecialedition/mods/44184. If this does not resolve your issue, please share the text found in your xVASynth/server.log file on the Discord's #issues channel for further support.

### Voicelines are being displayed in Mantella.exe but are not being said in-game
Try creating a save and then reloading that save. This ensures that the Mantella voice files get registered correctly

### NPC 'XYZ' could not be found in skyrim_characters.csv
This means that the NPC's name exactly as written in the error message could not be found in skyrim_characters.csv. If you are running Skyrim in another language, sometimes the NPC's name in this language does not match up to the English name, causing this error. It might also mean that the character is missing from skyrim_characters.csv. Please reach out on the Discord's issues channel if this is the case

### NPCs only respond with "I can't find the right words at the moment."
This either means the ChatGPT servers are currently down or the API key has not been set up correctly / is missing payment information. If it is the latter issue, please check MantellaSoftware/logging.log to see the exact error

### Microphone is not picking up sound / exe stuck on "Listening..."
Make sure that your mic is picking up correctly on other software and that it is set as your default. For example, you can go to User Settings -> Voice & Video on Discord to test your mic. Otherwise, try adjusting the `audio_threshold` setting in MantellaSoftware/config.ini (instructions on how to do so are inluded in config.ini). If all else fails, make sure that no other microphones are plugged in except the one you want to use. There may be a rogue microphone such as a webcam picking up as your default!

### 'NoneType' object has no attribute 'close'
This error means that Whisper is unable to find a connected microphone. Please ensure that you have a working microphone plugged in and enabled.

### "Invalid start byte" error
This error occurs when you introduce character symbols that can't be recognised either in MantellaSoftware/config.ini or skyrim_characters.csv. Please try re-downloading these files.

### Mantella.exe closes after "VAD filter removed 00:00.000 of audio" statement
This is an issue related to CUDA. Please try setting `process_device` to "cpu".

### Mantella.exe opens, but does not display any text
Ensure that you are not running Mantella.exe via a Vortex / Mod Organizer 2 shortcut, as this does not start the program properly.

### ERROR: xVASynth Error: [WinError 5] Access is denied
This happens when your antivirus is blocking Mantella.exe from working. Please add Mantella.exe to your safe list or try running as administrator.


## Contribute
The source code for Mantella is included in this repo. Here are the quick steps to get set up:

1. Clone the repo to your machine
2. Create a virtual environment via `py -3.11 -m venv MantellaEnv` in your console (Mantella requires Python 3.11)
3. Start the environment in your console (`.\MantellaEnv\Scripts\Activate`)
4. Install the required packages via `pip install -r requirements.txt`
5. Create a file called `GPT_SECRET_KEY.txt` and paste your secret key in this file
6. Set up your paths / any other required settings in the `config.ini`

If you have any trouble in getting the repo set up, please reach out on Discord!: https://discord.gg/Q4BJAdtGUE


## Attributions
Mantella uses material from the "[Skyrim: Characters](https://elderscrolls.fandom.com/wiki/Category:Skyrim:_Characters)" articles on the [Elder Scrolls wiki](https://elderscrolls.fandom.com/wiki/The_Elder_Scrolls_Wiki) at [Fandom](https://www.fandom.com/) and is licensed under the [Creative Commons Attribution-Share Alike License](https://creativecommons.org/licenses/by-sa/3.0/).
