(issues-qna)=
# Issues Q&A
## {doc}`/pages/installation`
## {doc}`/pages/installation_fallout4`
### [Discord](https://discord.gg/Q4BJAdtGUE)
<br>

#### SKYRIM : "Warning: Could not find _mantella__skyrim_folder.txt" in Mantella.exe
<details>
<summary>Details</summary>

This is either an issue with the path set for `skyrim_folder` in MantellaSoftware/config.ini, an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it). If it is either of the latter two issues an error should display in-game when you cast the spell. 

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscellaneous Files section of the Nexus download page). To put it another way, if you have `PapyrusUtil AE SE - Scripting Utility Function` in your modlist, you have the wrong version. 

If you are an SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path.

If you have the required mods installed, then this issue might instead be caused by the `skyrim_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Organizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__skyrim_folder.txt`. If you find this file, then please set its folder as your `skyrim_folder` path.
</details>
<br>

#### SKYRIM : "There is an error with your PapyrusUtil installation" when spell is cast
<details>
<summary>Details</summary>

This is either an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it).  

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscellaneous Files section of the Nexus download page). To put it another way, if you have `PapyrusUtil AE SE - Scripting Utility Function` in your modlist, you have the wrong version. 

If you are an SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path. 
</details>
<br>

#### SKYRIM : "There is an error with your installation of Mantella (or one of its dependent mods)" when spell is cast
<details>
<summary>Details</summary>

Please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. Mantella's required mods must match your Skyrim version, or else they won't work. Note that there have recently (end of 2023) been updates to Skyrim, which either requires new versions of many mods to be installed. You can also downgrade your Skyrim version (it is best to search online on how to do so).
</details>
<br>

#### SKYRIM : Conversation ends as soon as spell is cast / [Errno 2] No such file or directory: 'path\to\Skyrim Special Edition/some_text_file.txt' 
<details>
<summary>Details</summary>

This is either an issue with the path set for `skyrim_folder` in MantellaSoftware/config.ini, an issue with your Skyrim folder being in Program Files, an issue with the installation of PapyrusUtil, or you are not running Skyrim via SKSE (please see the included readme.txt file in SKSE's downloaded folder for instructions on how to use it). 

Some VR users miss that there is a separate VR version of PapyrusUtil, double check that you have downloaded this version of the mod if you are a VR user (it should be under the Miscellaneous Files section of the Nexus download page). To put it another way, if you have `PapyrusUtil AE SE - Scripting Utility Function` in your modlist, you have the wrong version. 

If you are an SE user, please double check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you actually have Skyrim AE, not SE (its confusing I know), so please download the AE versions of the required mods. You can tell if PapyrusUtil is working by checking if you have a file called `_mantella__skyrim_folder.txt` in your `skyrim_folder` path.

If you have the required mods installed, then this issue might instead be caused by the `skyrim_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Organizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__skyrim_folder.txt`. If you find this file, then please set its folder as your `skyrim_folder` path.
</details>
<br>

#### SKYRIM : NPCs keep repeating the same line of dialogue
<details>
<summary>Details</summary>

This is an issue with `mod_folder` not being set to the correct path in MantellaSoftware/config.ini. If you are using Mod Organizer 2, you can find the correct path by right-clicking the Mantella mod in the Mod Organizer 2 UI and selecting "Open in Explorer". If you are using Vortex, you should instead set this `mod_folder` path to your Skyrim/Data folder.
</details>
<br>

#### SKYRIM : No message box displayed to say spell has been added / Mantella spell is not in spell inventory
<details>
<summary>Details</summary>

This is an issue with the way the spell mod itself has been installed. Please check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details. The "File version" should be listed here. If it is 1.6 or above, you have Skyrim AE. If it is below 1.6, you have Skyrim SE. If you are using VR, there are separate versions of the required mods for VR (PapyrusUtil tends to catch out a lot of VR users, the VR version of this file is under "Miscellaneous Files" on the download page). If you are running the mod via the GOG version of Skyrim, there are slight differences in setting up a mod manager as discussed in [this tutorial](https://www.youtube.com/watch?v=EJYddISZdeo).
</details>
<br>

#### SKYRIM : Voicelines are being displayed in Mantella.exe but are not being said in-game
<details>
<summary>Details</summary>

Try creating a save and then reloading that save. This ensures that the Mantella voice files get registered correctly. 

If the above fails, a more unlikely reason for voicelines not playing is if you have updated the Mantella spell with a more recent version by replacing files in the mod's folder. If this is the case, open Skyrim, end all Mantella conversations and unequip the Mantella spell, and create a save. In your mod organizer, disable the Mantella spell plugin. Open your newly created save and create another save (now with no Mantella mod). Finally, in your mod organizer re-enable the Mantella spell plugin. This should effectively "reset" the mod. When you next open your recent save, you should see a notification that the Mantella spell has been added to your inventory.
</details>
<br>

#### SKYRIM : 'Starting conversation with' without the NPC name is displayed in game and nothing happens after
<details>
<summary>Details</summary>

Make sure Skyrim Script Extender (SKSE) is started before Skyrim itself.
[SKSE ReadME](https://skse.silverlock.org/skse_readme.txt)
</details>
<br>

#### FALLOUT 4 : "Warning: Could not find _mantella__fallout4_folder.txt" in Mantella.exe
<details>
<summary>Details</summary>

This is either an issue with the path set for `fallout4_folder` or `fallout4VR_folder` in MantellaSoftware/config.ini, an issue with the installation of SUP_F4SE, or something is wrong with the install of F4SE (make sure you have the correct version : desktop or VR). If it is either of the latter two issues an error should display in Fallout 4 when you load a save game. This might also be caused by the wrong game being set in the config.ini for `game = ` .

Double check your Fallout 4 version by right-clicking its exe file in your Fallout 4 folder and going to Properties -> Details. The "File version" should be listed here and it should be 1.10.163.0 (for Fallout 4 desktop) or 1.2.72.0 (for Fallout 4 VR).

If you have the required mods installed, then this issue might instead be caused by the `fallout4_folder` or `fallout4VR_folder` being set incorrectly. This only seems to be an issue for Mod Organizer 2 / Wabbajack modlist users. Some Mod Organizer 2 setups move the text files created by the Mantella spell to another folder. Try searching for a folder called overwrite/root or "Stock Game" in your Mod Organizer 2 / Wabbajack installation path to try to find these Mantella text files, specifically a file called `_mantella__fallout4_folder.txt`. If you find this file, then please set its folder as your `fallout4_folder` or `fallout4VR_folder` path.
</details>
<br>

#### FALLOUT 4 : On game load the following message is displayed : "F4SE or SUP_F4SE not properly installed, Mantella will not work correctly"
<details>
<summary>Details</summary>

Multiples reasons can cause this issue:

1: Invalid or absent F4SE install, make sure to download the one from this link : [F4SE](https://f4se.silverlock.org/). Make sure to download the appropriate version (desktop or VR).

2: Incorrect FO4 version number. Mantella is supposed to run with version 1.10.163.0 (for Fallout 4 desktop) or 1.2.72.0 (for Fallout 4 VR).

3: [SUP F4SE](https://www.nexusmods.com/fallout4/mods/55419) or [SUP F4SEVR](https://www.nexusmods.com/fallout4/mods/64420) (whichever is appropriate for your game) isn't correctly installed.

4: Make sure you're actually launching the game with : f4se_loader.exe

5: If you are running the mod via the GOG version of Fallout 4, you might encounter issues getting F4SE to load, see [this workaround](https://github.com/ModOrganizer2/modorganizer/issues/1856#issuecomment-1685925528)

</details>
<br>

#### FALLOUT 4 : Lip sync isn't working at all after adding a new NPC
<details>
<summary>Details</summary>

Lip files need to be present at launch for the game to register it. Restarting Fallout 4 should correct the issue. The Mantella Mod on the Mod Nexus will cover all the base game and all the main DLCs but any other NPC will need to have a lip file named 00001ED2_1.lip present at launch in its voice type folder in data\Sound\Voice\Mantella.esp
</details>
<br>

#### FALLOUT 4 : The NPC is lip syncing a different line than the one said in game
<details>
<summary>Details</summary>

This might be caused by an invalid mod file path (ex: a file path pointing to for another game's data folder). Double check the file paths. Please note that there is a known issue in Fallout 4 that causes lip sync to be cut short for longer lines.
</details>
<br>

#### FALLOUT 4 : Every time a conversation is started the notification is : "NPC not added. Please try again after your next response."
<details>
<summary>Details</summary>

Multiples reasons can cause this issue:

1: Invalid game file path in the config.ini. Double check your filepath for `fallout4_folder` or `fallout4VR_folder`.

2: Wrong game set in the config.ini, double check the value for `game = ` 

3: If you're running a modlist that uses Root builder, there might be a sync issue between Mantella and your game. Make sure you load the game first then load Mantella after to avoid the _Mantella text files getting out of sync.

</details>
<br>

#### FALLOUT 4 : After trying to start a conversation, the notification says "Starting a conversation with NPCNAME", but nothing happens in Fallout 4 or the Mantella console
<details>
<summary>Details</summary>

Multiples reasons can cause this issue:

1: Invalid game file path in the config.ini. Double check your filepath for `fallout4_folder` or `fallout4VR_folder`.

2: Wrong game set in the config.ini. Double check the value for `game = ` 

</details>
<br>

#### FALLOUT 4 : The text input menu isn't showing up when the hotkey is pressed after the notification "Awaiting user input for X seconds"
<details>
<summary>Details</summary>

Multiples reasons can cause this issue:

1: Double check that the install for [Textinputmenu](https://www.nexusmods.com/fallout4/mods/27347) is correct.

2: Try resetting the text input hotkey in the settings holotape under `Main settings`. You will need to enter a [DirectX scan code](https://falloutck.uesp.net/wiki/DirectX_Scan_Codes)

</details>
<br>

#### FALLOUT 4 : The Mantella gun & holotape do not get added on load and are not available at the Chem Station in UTILITY
<details>
<summary>Details</summary>

This is an issue with the way the Mantella esp mod itself has been installed. Please check your Fallout 4 version by right-clicking its exe file in your Fallout 4 folder and going to Properties -> Details . The "File version" should be listed here and it should be 1.10.163.0 (for Fallout 4 desktop) or 1.2.72.0 (for Fallout 4 VR). If you are using VR, there are separate versions of the required mods for SUP_F4SE : [SUP F4SEVR](https://www.nexusmods.com/fallout4/mods/64420). If you are running the mod via the GOG version of Fallout 4, you might encounter issue getting F4Se to load, see [this workaround](https://github.com/ModOrganizer2/modorganizer/issues/1856#issuecomment-1685925528).
</details>
<br>

#### FALLOUT 4 : The NPC subtitles play in-game but no audio can be heard.
<details>
<summary>Details</summary>

Double check the config ini to make sure that the value of `FO4_NPC_response_volume = ` is high enough to be audible. Make sure that the volume of python in Windows Volume mixer is set to an audible level. 
</details>
<br>

#### FALLOUT 4 : The mod is enabled but the gun doesn't appear in game at game load
<details>
<summary>Details</summary>

This might be caused by multiple reasons:
1. Make sure you are past the intro and first Vault.
2. Try to fast travel on the map.
3. Check that MantellaQuest is running by using the console and typing 'sqv MantellaQuest'. Make sure that the ini files have been modified to allow modding: [Howto: Enable Modding - Archive Invalidation](https://www.nexusmods.com/fallout4/articles/3831).
4. Double check that [Fallout 4 Version Check Patcher](https://www.nexusmods.com/fallout4/mods/42497?tab=description) has been installed.

</details>
<br>

#### ALL GAMES : ChatGPT API Error: cannot access local variable 'audio_file' where it is not associated with a value
<details>
<summary>Details</summary>

This error occurs when something has failed in a previous step (likely an issue with xVASynth / not having FaceFXWrapper installed). Please check your MantellaSoftware/logging.log file to see the error which occurred before this, which should provide more clarification. If you are still ensure, please share your logging.log file to the Discord's issues channel.
</details>
<br>

#### ALL GAMES : RuntimeError('PytorchStreamReader failed reading zip archive: failed finding central directory')
<details>
<summary>Details</summary>

If an xVASynth voice model is corrupted, this error will display in MantellaSoftware/logging.log. Please re-download the voice model in this case. You may alternatively need to redownload xVASynth.

A way to check for other corrupted voice models, is to compare the file sizes within /models/skyrim/ folder of xVASynth. If they diverge from the norms, redownload **just** those. The norms for voice model sizes are **~54 MB** and/or **~90 MB** (v2 voice models) & **~220 MB** or **~260 MB** (v3 voice models).
</details>
<br>

#### ALL GAMES : Loading voice model... xVASynth Error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
<details>
<summary>Details</summary>

If this xVASynth Error occurs after the "Loading voice model..." message (as can be seen in your MantellaSoftware/logging.log file), this is likely an issue with a corrupted voice model. Please try redownloading the model from [here](https://www.nexusmods.com/skyrimspecialedition/mods/44184) for Skyrim or [here](https://www.nexusmods.com/fallout4/mods/49340) for Fallout 4. If you have `use_cleanup` enabled, try setting this value to 0 in MantellaSoftware/config.ini.

If this does not resolve your issue, please share the text found in your xVASynth/server.log file on the [Discord's #issues channel](https://discord.gg/Q4BJAdtGUE) for further support.
</details>
<br>

#### ALL GAMES : NPC 'XYZ' could not be found in skyrim_characters.csv or fallout4_characters.csv
<details>
<summary>Details</summary>

This means that the NPC's name exactly as written in the error message could not be found in the characters.csv. If you are running your game in another language, sometimes the NPC's name in this language does not match up to the English name, causing this error. It might also mean that the character is missing from characters.csv. Please reach out on the Discord's issues channel if this is the case
</details>
<br>

#### ALL GAMES : NPCs only respond with "I can't find the right words at the moment."
<details>
<summary>Details</summary>

This either means the ChatGPT servers are currently down or the API key has not been set up correctly / is missing payment information. If it is the latter issue, please check MantellaSoftware/logging.log to see the exact error.
</details>
<br>

#### ALL GAMES : Microphone is not picking up sound / exe stuck on "Listening..."
<details>
<summary>Details</summary>

Make sure that your mic is picking up correctly on other software and that it is set as your default. For example, you can go to User Settings -> Voice & Video on Discord to test your mic. Otherwise, try adjusting the `audio_threshold` setting in MantellaSoftware/config.ini (instructions on how to do so are included in config.ini). If all else fails, make sure that no other microphones are plugged in except the one you want to use. There may be a rogue microphone such as a webcam picking up as your default!
</details>
<br>

#### ALL GAMES : 'NoneType' object has no attribute 'close'
<details>
<summary>Details</summary>

This error means that Whisper is unable to find a connected microphone. Please ensure that you have a working microphone plugged in and enabled.
</details>
<br>

#### ALL GAMES : "Invalid start byte" error
<details>
<summary>Details</summary>

This error occurs when you introduce character symbols that can't be recognized either in MantellaSoftware/config.ini, skyrim_characters.csv or fallout4_characters.csv. Please try re-downloading these files. Note that if you are using Excel to edit the CSV, Excel often likes to corrupt CSVs when saving these files. If you are experiencing issues with Excel, there are free CSV editors available such as [LibreOffice](https://www.libreoffice.org/). 
</details>
<br>

#### ALL GAMES : Mantella.exe closes after "VAD filter removed 00:00.000 of audio" statement
<details>
<summary>Details</summary>

This is an issue related to CUDA. Please try setting `process_device` to "cpu".
</details>
<br>

#### ALL GAMES : Mantella.exe opens, but does not display any text
<details>
<summary>Details</summary>

Ensure that you are not running Mantella.exe via a Vortex / Mod Organizer 2 shortcut, as this does not start the program properly.
</details>
<br>

#### ALL GAMES : ERROR: xVASynth Error: [WinError 5] Access is denied
<details>
<summary>Details</summary>

This happens when your antivirus is blocking Mantella.exe from working. Please add Mantella.exe to your safe list or try running as administrator.
</details>
<br>

#### ALL GAMES :Cannot start new conversation after ending previous conversation (conversation ended message)
<details>
<summary>Details</summary>

You might need to say something in the mic for Mantella.exe to realize that the conversation has ended (while it is on "Listening..." it does not look out for the conversation ending). The exe will check if the conversation has ended after 30 seconds by default. You can change this via the `listen_timeout`` setting in MantellaSoftware/config.ini, but just keep in mind if it is too short this will effect conversations as the exe will occasionally stop listening for mic input to check if the conversation has ended
</details>
<br>

#### ALL GAMES : RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
<details>
<summary>Details</summary>

xVASynth related warning when started by Mantella. Thus far has not impacted Mantella so it can be safely ignored.
</details>
<br>

#### ALL GAMES : Error: [Errno 2] No such file or directory: 'data/skyrim_characters.csv' or 'data/fallout4_characters.csv'
<details>
<summary>Details</summary>

This may be caused by `Mantella.exe` being ran through MO2 or Vortex. `Mantella.exe` must be started through Windows explorer like any other executable file.
</details>
<br>