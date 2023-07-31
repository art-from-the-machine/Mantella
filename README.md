# Mantella
Mantella is a Skyrim mod which allows you to naturally speak to NPCs using Whisper (speech-to-text), ChatGPT (text generation), and xVASynth (text-to-speech). See here for a video demonstration:

https://www.youtube.com/watch?v=fJPY6sD527A

The mod is currently undergoing testing before release. The mod's files can be downloaded via Discord:  

https://discord.gg/Q4BJAdtGUE


## Requirements
### Hardware Requirements
There are no discovered minimum requirements at the time of writing, but there has been a report of Mantella crashing when running a modlist of 2000 mods. Mantella needs a certain amount of hardware allocation to run successfully, and if this is being soaked up by other hardware intensive mods, it may crash.


### Storage Requirements
This mod requires ~17GB of space when all voice models are installed. A total of ~32GB is needed to unpack the voice models.


### Compatability
- Mantella has been confirmed to work with the FUS (by pointing skyrim_folder to Skyrim), Librum (by pointing skyrim_folder to overwrite/root), and Wildlands (by pointing skyrim_folder to Wildlander/SKSE) Wabbajack modlists.
- If you have the Unofficial Skyrim Special Edition Patch (USSEP) installed, Mantella needs to be loaded after this mod

## Installation
### Video Walkthrough
A video walking through the installation of Mantella can be found below (kindly provided by Lucien Lachance on Discord):

https://www.youtube.com/watch?v=8axcIZPKu5g

This can be used as a visual reference to the below instructions.

### Skyrim
As Mantella accesses and writes to files within your Skyrim folder, it is unlikely to work correctly if you have Skyrim stored in Program Files. Please ensure that you have Skyrim stored outside of this folder (Such as C:\Games\Steam for example).


### MantellaSoftware
Extract this folder somewhere convenient to you.


### MantellaSpell.zip
This zip file can be installed in the same way as other mods. If you haven't installed a mod manually before, on Mod Organizer 2 there is a disc icon on the top left corner of the UI where you can point to the zipped mod MantellaSpell.zip to install. For Vortex, you should be able to drag the zipped mod into the Vortex panel.


### xVASynth
1. Download xVASynth via Steam (https://store.steampowered.com/app/1765720/xVASynth/) or Nexus (https://www.nexusmods.com/skyrimspecialedition/mods/44184).

2. Download all voice models under "Optional" (not "Old") from https://www.nexusmods.com/skyrimspecialedition/mods/44184?tab=files and store the zipped files in a folder. Open xVAsynth and drag all zipped voice model files from the folder into the voices panel. Wait for the installation to complete (this may take some time, a popup will display when finished saying "x models installed successfully"). If this method doesn't work for you, you can also unzip the models manually into the correct xVASynth folder (xVASynth\resources\app\models\skyrim). Once the extraction is complete, you can delete the zipped voice model files. As an alternative to manually installing, if you have Nexus Premium, open xVASynth and select "Get More Voices" from the bottom left corner. Unselect all games except for Skyrim and download all models. Note that this may require restarting a few times for the downloads to properly complete.

3. Download the .lip plugin for xVASynth here: https://www.nexusmods.com/skyrimspecialedition/mods/55605 and download FaceFXWrapper from here (you do not need to download CK64Fixes): https://www.nexusmods.com/skyrimspecialedition/mods/20061. Instructions on how to install these are on the .lip plugin Nexus page. Make sure to place FaceFXWrapper in the plugins folder as stated on the .lip plugin page.

4. Download the Elder Scrolls pronunciation dictionary from here, and follow the instructions to install: https://www.nexusmods.com/skyrimspecialedition/mods/56778/

5. On the navigation bar on the top right of the xVASynth UI, click on the "ae" icon. Once opened, click on the CMUDict dictionary and select "Enable All" in the bottom left corner. Once done, close this menu and navigate to the settings menu by selecting the gear icon in the top right corner and ensure that "Audio sample rate (Hz)" is set to 44100. You can also select whether to process voicelines via you CPU or (NVIDIA) GPU from this menu.


### Required Mods
Please follow the installation instructions on each of the linked pages:

SKSE (there is a separate VR version): http://skse.silverlock.org/

VR Address Library for SKSEVR: https://www.nexusmods.com/skyrimspecialedition/mods/58101  
or Address Library for SKSE Plugins: https://www.nexusmods.com/skyrimspecialedition/mods/32444

PapyrusUtil SE (the VR version can be found under "Optional Files"): https://www.nexusmods.com/skyrimspecialedition/mods/13048


### Optional Mods
No NPC Greetings (recommended so that Mantella voicelines are not interrupted by vanilla voicelines): https://www.nexusmods.com/skyrim/mods/746


## Setup & Configuration
1. Set up the config.ini file with your paths to Skyrim (`skyrim_folder`), xVASynth (`xvasynth_folder`), and the Mantella Skyrim mod (`mod_folder`). If you are using a Wabbajack modlist, you may need to try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path and set this as your `skyrim_folder` path. If you are using Mod Organizer 2, you can find the mod folder by right clicking the mod in the Mod Organizer 2 UI and selecting "Open in Explorer". If you are instead using Vortex, you need to point mod_folder to your Skyrim/Data folder. So Vortex users essentially need to take the Skyrim folder path they have set in `skyrim_folder` and add "\Data" to the end of it.

2. Copy your OpenAI secret API key (see here if you need help finding it (you will need to set up an account if you haven't already): https://help.openai.com/en/articles/4936850-where-do-i-find-my-secret-api-key) and paste into GPT_SECRET_KEY.txt. Do not share this key with anyone.

3. The applications should be started in this order: Run xVASynth -> Run Mantella.exe (found in the MantellaSoftware folder). It will say "Waiting for player to select an NPC..." when it is ready -> Run Skyrim

4. When you first load the mod, MAKE SURE TO CREATE A SAVE AND RELOAD THAT SAVE. The voicelines will not play otherwise! I learned this the hard way.

5. The Mantella spell should be added to your inventory under the Illusion category in the Magic menu once you install the mod. Conversations can be started by selecting an NPC with the spell. You can end a conversation by selecting an NPC with the spell again, or by simply saying "goodbye". If the NPC responds with "safe travels" then the conversation has ended correctly via this latter method. Note that conversations can only be saved to memory (MantellaSoftware/data/conversations/NPC_Name) by either using the spell or by saying "goodbye". If the NPC is unavailable to the mod, the message "Conversation ended." should immediately pop up in the top left corner and the conversation will exit. If the only message you see from the spell is "Conversation ended", please refer to the "Issues Q&A" section for common solutions to this.

6. Voicelines are cached in the MantellaSoftware/data/voicelines/ folder. If this data takes up too much space over time, the contents of voicelines/ can be periodically deleted.

7. If you are experiencing errors, please share the details of the errors and your MantellaSoftware/logging.log file on the Mantella Discord #issues channel: https://discord.gg/Q4BJAdtGUE. You can also try enabling debugging in the config.ini. This allows Mantella.exe to run without Skyrim needing to be open. There are a few extra options in the debugging section to play around with which are applied when the debugging option is enabled.


## Issues Q&A
### Conversation ends as soon as spell is cast / [Errno 2] No such file or directory: 'path\to\Skyrim Special Edition/some_text_file.txt' 
This is either an issue with the path set for `skyrim_folder` in MantellaSoftware/config.ini, an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it). 

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscallaneous Files section of the Nexus download page). If you are a SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods.

If you have the required mods installed, then this issue might instead be caused by the `skyrim_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Orgnanizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__skyrim_folder.txt`. If you find this file, then please set its folder as your `skyrim_folder` path.

### NPCs keep repeating the same line of dialogue
This is an issue with `mod_folder` not being set to the correct path in MantellaSoftware/config.ini. If you are using Mod Organizer 2, you can find the correct path by right-clicking the Mantella mod in the Mod Organizer 2 UI and selecting "Open in Explorer". If you are using Vortex, you should instead set this `mod_folder` path to your Skyrim/Data folder.

### NPCs all use the same voice model
Open xVASynth and go to your settings. Ensure that the paths for WaveGlow and BIG Waveglow end in /models/skyrim/ and not the path to a particular voice model

### No message box displayed to say spell has been added / Mantella spell is not in spell inventory
This is an issue with the way the spell mod itself has been installed. Please check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you have Skyrim AE. If it is below 1.6, you have Skyrim SE. If you are using VR, there are separate versions of the required mods for VR (PapyrusUtil tends to catch out a lot of VR users, the VR version of this file is under "Miscellaneous Files" on the download page). If you are running the mod via the GOG version of Skyrim, there are slight differences in setting up a mod manager as discussed in this tutorial: https://www.youtube.com/watch?v=EJYddISZdeo

### RuntimeError('PytorchStreamReader failed reading zip archive: failed finding central directory')
If an xVASynth voice model is corrupted, this error will display in MantellaSoftware/logging.log. Please re-download the voice model in this case. You may alternatively need to redownload xVASynth.

### Voicelines are being displayed in Mantella.exe but are not being said in-game
Try creating a save and then reloading that save. This ensures that the Mantella voice files get registered correctly

### NPC 'XYZ' could not be found in skyrim_characters.csv
This means that the NPC's name exactly as written in the error message could not be found in skyrim_characters.csv. If you are running Skyrim in another language, sometimes the NPC's name in this language does not match up to the English name, causing this error. It might also mean that the character is missing from skyrim_characters.csv. Please reach out on the Discord's issues channel if this is the case

### NPCs only respond with "I can't find the right words at the moment."
This either means the ChatGPT servers are currently down or the API key has not been set up correctly / is missing payment information. If it is the latter issue, please check MantellaSoftware/logging.log to see the exact error

### Microphone is not picking up sound
Make sure that your mic is picking up correctly on other software and that it is set as your default. For example, you can go to User Settings -> Voice & Video on Discord to test your mic. Otherwise, try adjusting the `audio_threshold` setting in MantellaSoftware/config.ini (instructions on how to do so are inluded in config.ini)

### "Invalid start byte" error
This error occurs when you introduce character symbols that can't be recognised either in config.ini or skyrim_characters.csv. Please try re-downloading these files.

### Mantella.exe closes after "VAD filter removed 00:00.000 of audio" statement
This is an issue related to CUDA. Please try setting `process_device` to "cpu".

### Mantella.exe opens, but does not display any text
Ensure that you are not running Mantella.exe via a Vortex / Mod Organizer 2 shortcut, as this does not start the program properly.


## Attributions
Mantella uses material from the "[Skyrim: Characters](https://elderscrolls.fandom.com/wiki/Category:Skyrim:_Characters)" articles on the [Elder Scrolls wiki](https://elderscrolls.fandom.com/wiki/The_Elder_Scrolls_Wiki) at [Fandom](https://www.fandom.com/) and is licensed under the [Creative Commons Attribution-Share Alike License](https://creativecommons.org/licenses/by-sa/3.0/).