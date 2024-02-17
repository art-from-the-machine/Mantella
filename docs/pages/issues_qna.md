(issues-qna)=
# Issues Q&A
## {doc}`/pages/installation`
### [Discord](https://discord.gg/Q4BJAdtGUE)
<br>

#### "Warning: Could not find _mantella__skyrim_folder.txt" in Mantella.exe
<details>
<summary>Details</summary>

This is either an issue with the path set for `skyrim_folder` in MantellaSoftware/config.ini, an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it). If it is either of the latter two issues an error should display in-game when you cast the spell. 

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscallaneous Files section of the Nexus download page). To put it another way, if you have `PapyrusUtil AE SE - Scripting Utility Function` in your modlist, you have the wrong version. 

If you are an SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path.

If you have the required mods installed, then this issue might instead be caused by the `skyrim_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Organizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__skyrim_folder.txt`. If you find this file, then please set its folder as your `skyrim_folder` path.
</details>
<br>

#### "There is an error with your PapyrusUtil installation" when spell is cast
<details>
<summary>Details</summary>

This is either an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it).  

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscallaneous Files section of the Nexus download page). To put it another way, if you have `PapyrusUtil AE SE - Scripting Utility Function` in your modlist, you have the wrong version. 

If you are an SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path. 
</details>
<br>

#### "There is an error with your installation of Mantella (or one of its dependent mods)" when spell is cast
<details>
<summary>Details</summary>

Please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. Mantella's required mods must match your Skyrim version, or else they won't work. Note that there have recently (end of 2023) been updates to Skyrim, which either requires new versions of many mods to be installed. You can also downgrade your Skyrim version (it is best to search online on how to do so).
</details>
<br>

#### Conversation ends as soon as spell is cast / [Errno 2] No such file or directory: 'path\to\Skyrim Special Edition/some_text_file.txt' 
<details>
<summary>Details</summary>

This is either an issue with the path set for `skyrim_folder` in MantellaSoftware/config.ini, an issue with your Skyrim folder being in Program Files, an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it). 

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscallaneous Files section of the Nexus download page). To put it another way, if you have `PapyrusUtil AE SE - Scripting Utility Function` in your modlist, you have the wrong version. 

If you are an SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path.

If you have the required mods installed, then this issue might instead be caused by the `skyrim_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Organizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__skyrim_folder.txt`. If you find this file, then please set its folder as your `skyrim_folder` path.
</details>
<br>

#### ChatGPT API Error: cannot access local variable 'audio_file' where it is not associated with a value
<details>
<summary>Details</summary>

This error occurs when something has failed in a previous step (likely an issue with xVASynth / not having FaceFXWrapper installed). Please check your MantellaSoftware/logging.log file to see the error which occurred before this, which should provide more clarification. If you are still ensure, please share your logging.log file to the Discord's issues channel.
</details>
<br>

#### NPCs keep repeating the same line of dialogue
<details>
<summary>Details</summary>

This is an issue with `mod_folder` not being set to the correct path in MantellaSoftware/config.ini. If you are using Mod Organizer 2, you can find the correct path by right-clicking the Mantella mod in the Mod Organizer 2 UI and selecting "Open in Explorer". If you are using Vortex, you should instead set this `mod_folder` path to your Skyrim/Data folder.
</details>
<br>

#### No message box displayed to say spell has been added / Mantella spell is not in spell inventory
<details>
<summary>Details</summary>

This is an issue with the way the spell mod itself has been installed. Please check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you have Skyrim AE. If it is below 1.6, you have Skyrim SE. If you are using VR, there are separate versions of the required mods for VR (PapyrusUtil tends to catch out a lot of VR users, the VR version of this file is under "Miscellaneous Files" on the download page). If you are running the mod via the GOG version of Skyrim, there are slight differences in setting up a mod manager as discussed in [this tutorial](https://www.youtube.com/watch?v=EJYddISZdeo).
</details>
<br>

#### RuntimeError('PytorchStreamReader failed reading zip archive: failed finding central directory')
<details>
<summary>Details</summary>

If an xVASynth voice model is corrupted, this error will display in MantellaSoftware/logging.log. Please re-download the voice model in this case. You may alternatively need to redownload xVASynth.

A way to check for other corrupted voice models, is to compare the file sizes within /models/skyrim/ folder of xVASynth. If they diverge from the norms, redownload **just** those. The norms for voice model sizes are **~54 MB** and/or **~90 MB** (v2 voice models) & **~220 MB** or **~260 MB** (v3 voice models).
</details>
<br>

#### Loading voice model... xVASynth Error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
<details>
<summary>Details</summary>

If this xVASynth Error occurs after the "Loading voice model..." message (as can be seen in your MantellaSoftware/logging.log file), this is likely an issue with a corrupted voice model. Please try redownloading the model from [here](https://www.nexusmods.com/skyrimspecialedition/mods/44184). If you have `use_cleanup` enabled, try setting this value to 0 in MantellaSoftware/config.ini.

If this does not resolve your issue, please share the text found in your xVASynth/server.log file on the [Discord's #issues channel](https://discord.gg/Q4BJAdtGUE) for further support.
</details>
<br>

#### Voicelines are being displayed in Mantella.exe but are not being said in-game
<details>
<summary>Details</summary>

Try creating a save and then reloading that save. This ensures that the Mantella voice files get registered correctly. 

If the above fails, a more unlikely reason for voicelines not playing is if you have updated the Mantella spell with a more recent version by replacing files in the mod's folder. If this is the case, open Skyrim, end all Mantella conversations and unequip the Mantella spell, and create a save. In your mod organizer, disable the Mantella spell plugin. Open your newly created save and create another save (now with no Mantella mod). Finally, in your mod organizer re-enable the Mantella spell plugin. This should effectively "reset" the mod. When you next open your recent save, you should see a notification that the Mantella spell has been added to your inventory.
</details>
<br>

#### 'Starting conversation with' without the NPC name is displayed ingame and nothing happens after
<details>
<summary>Details</summary>

Make sure Skyrim Script Extender (SKSE) is started before Skyrim itself.
[SKSE ReadME](https://skse.silverlock.org/skse_readme.txt)
</details>
<br>

#### NPC 'XYZ' could not be found in skyrim_characters.csv
<details>
<summary>Details</summary>

This means that the NPC's name exactly as written in the error message could not be found in skyrim_characters.csv. If you are running Skyrim in another language, sometimes the NPC's name in this language does not match up to the English name, causing this error. It might also mean that the character is missing from skyrim_characters.csv. Please reach out on the Discord's issues channel if this is the case
</details>
<br>

#### NPCs only respond with "I can't find the right words at the moment."
<details>
<summary>Details</summary>

This either means the ChatGPT servers are currently down or the API key has not been set up correctly / is missing payment information. If it is the latter issue, please check MantellaSoftware/logging.log to see the exact error.
</details>
<br>

#### Microphone is not picking up sound / exe stuck on "Listening..."
<details>
<summary>Details</summary>

Make sure that your mic is picking up correctly on other software and that it is set as your default. For example, you can go to User Settings -> Voice & Video on Discord to test your mic. Otherwise, try adjusting the `audio_threshold` setting in MantellaSoftware/config.ini (instructions on how to do so are inluded in config.ini). If all else fails, make sure that no other microphones are plugged in except the one you want to use. There may be a rogue microphone such as a webcam picking up as your default!
</details>
<br>

#### 'NoneType' object has no attribute 'close'
<details>
<summary>Details</summary>

This error means that Whisper is unable to find a connected microphone. Please ensure that you have a working microphone plugged in and enabled.
</details>
<br>

#### "Invalid start byte" error
<details>
<summary>Details</summary>

This error occurs when you introduce character symbols that can't be recognised either in MantellaSoftware/config.ini or skyrim_characters.csv. Please try re-downloading these files. Note that if you are using Excel to edit the CSV, Excel often likes to corrupt CSVs when saving these files. If you are experiencing issues with Excel, there are free CSV editors available such as [LibreOffice](https://www.libreoffice.org/). 
</details>
<br>

#### Mantella.exe closes after "VAD filter removed 00:00.000 of audio" statement
<details>
<summary>Details</summary>

This is an issue related to CUDA. Please try setting `process_device` to "cpu".
</details>
<br>

#### Mantella.exe opens, but does not display any text
<details>
<summary>Details</summary>

Ensure that you are not running Mantella.exe via a Vortex / Mod Organizer 2 shortcut, as this does not start the program properly.
</details>
<br>

#### ERROR: xVASynth Error: [WinError 5] Access is denied
<details>
<summary>Details</summary>

This happens when your antivirus is blocking Mantella.exe from working. Please add Mantella.exe to your safe list or try running as administrator.
</details>
<br>

#### Cannot start new conversation after ending previous conversation (conversation ended message)
<details>
<summary>Details</summary>

You might need to say something in the mic for Mantella.exe to realise that the conversation has ended (while it is on "Listening..." it does not look out for the conversation ending). The exe will check if the conversation has ended after 30 seconds by default. You can change this via the `listen_timeout`` setting in MantellaSoftware/config.ini, but just keep in mind if it is too short this will effect conversations as the exe will occasionally stop listening for mic input to check if the conversation has ended
</details>
<br>

#### RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
<details>
<summary>Details</summary>

xVASynth related warning when started by Mantella. Thus far has not impacted Mantella so it can be safely ignored.
</details>
<br>