(issues-qna)=
# Issues Q&A
## {doc}`/pages/installation`
## {doc}`/pages/installation_fallout4`
### [Discord](https://discord.gg/Q4BJAdtGUE)
<br>

#### SKYRIM : NPCs keep repeating the same line of dialogue
<details>
<summary>Details</summary>

If you are experiencing this issue with no changes in dialogue than this is likely a permissions issue with Mantella accessing your Skyrim folder. If your Skyrim folder is installed in Program Files, please move it to a [different folder](https://art-from-the-machine.github.io/Mantella/pages/installation.html#skyrim). 

If this only happens occasionally, it is likely because the next voiceline is being activated before the voiceline file is ready. You can mitigate this by increasing the value of `Wait Time Buffer` in the `Large Language Model -> Advanced` tab in the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui).
</details>
<br>

#### SKYRIM : Mantella spells have not been added to my inventory
<details>
<summary>Details</summary>

This is an issue with the way the Mantella mod has been installed. Please ensure any previous versions of Mantella have been completely removed before installing the new version:

Open Skyrim, end all Mantella conversations and unequip the Mantella spell, and create a save. In your mod manager, disable the old Mantella mod. Open your newly created save and create another save (now with no Mantella mod). Finally, in your mod manager enable the new Mantella mod. This should effectively "reset" the mod. When you next open your recent save, you should see a notification that the Mantella spell has been added to your inventory.
</details>
<br>

#### SKYRIM : Voicelines are being displayed in Mantella.exe but are not being said in-game
<details>
<summary>Details</summary>

Try creating a save and then reloading that save. This ensures that the Mantella voice files get registered correctly. 

If the above fails, a more unlikely reason for voicelines not playing is if you have updated the Mantella mod with a more recent version by replacing files in the mod's folder. If this is the case, open Skyrim, end all Mantella conversations and unequip the Mantella spell, and create a save. In your mod manager, disable the old Mantella mod. Open your newly created save and create another save (now with no Mantella mod). Finally, in your mod manager enable the new Mantella mod. This should effectively "reset" the mod. When you next open your recent save, you should see a notification that the Mantella spell has been added to your inventory.
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

4: Double check that you installed the correct version of the Mantella Mod : desktop or VR.

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

#### ALL GAMES : API Error: cannot access local variable 'audio_file' where it is not associated with a value
<details>
<summary>Details</summary>

This error occurs when something has failed in a previous step (likely an issue with xVASynth / not having FaceFXWrapper installed). Please check your Documents/My Games/Mantella/logging.log file to see the error which occurred before this, which should provide more clarification. If you are still ensure, please share your logging.log file to the Discord's issues channel.
</details>
<br>

#### ALL GAMES : RuntimeError('PytorchStreamReader failed reading zip archive: failed finding central directory')
<details>
<summary>Details</summary>

If an xVASynth voice model is corrupted, this error will display in Documents/My Games/Mantella/logging.log. Please re-download the voice model in this case. You may alternatively need to redownload xVASynth.

A way to check for other corrupted voice models, is to compare the file sizes within /models/skyrim/ folder of xVASynth. If they diverge from the norms, redownload **just** those. The norms for voice model sizes are **~54 MB** and/or **~90 MB** (v2 voice models) & **~220 MB** or **~260 MB** (v3 voice models).
</details>
<br>

#### ALL GAMES : Loading voice model... xVASynth Error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))
<details>
<summary>Details</summary>

If this xVASynth Error occurs after the "Loading voice model..." message (as can be seen in your Documents/My Games/Mantella/logging.log file), this is likely an issue with a corrupted voice model. Please try redownloading the model from [here](https://www.nexusmods.com/skyrimspecialedition/mods/44184) for Skyrim or [here](https://www.nexusmods.com/fallout4/mods/49340) for Fallout 4. If you have `use_cleanup` enabled, try setting this value to 0 in MantellaSoftware/config.ini.

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

This either means the LLM servers you have connected to are currently down or the API key has not been set up correctly / is missing payment information. If it is the latter issue, please check Documents/My Games/Mantella/logging.log to see the exact error.
</details>
<br>

#### ALL GAMES : Microphone is not picking up sound / exe stuck on "Listening..."
<details>
<summary>Details</summary>

Make sure that your mic is picking up correctly on other software and that it is set as your default. For example, you can go to User Settings -> Voice & Video on Discord to test your mic. Otherwise, try adjusting the `Audio Threshold` setting under the `Speech-to-Text` tab of the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui) (following the instructions provided for that setting). If all else fails, make sure that no other microphones are plugged in except the one you want to use. There may be a rogue microphone such as a webcam picking up as your default!
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

This is an issue related to CUDA. Please try setting `Process Device` to "cpu" under the `Speech-to-Text -> Advanced` tab of the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui).
</details>
<br>

#### ALL GAMES : Mantella.exe opens, but does not display any text
<details>
<summary>Details</summary>

Ensure that you are not running Mantella.exe via a Vortex / Mod Organizer 2 shortcut, as this does not start the program properly. Otherwise, it may take some time to start when running for the first time.
</details>
<br>

#### ALL GAMES : ERROR: xVASynth Error: [WinError 5] Access is denied
<details>
<summary>Details</summary>

This happens when your antivirus is blocking Mantella.exe from working. Please add Mantella.exe to your safe list or try running as administrator.
</details>
<br>

#### ALL GAMES : Cannot start new conversation after ending previous conversation (conversation ended message)
<details>
<summary>Details</summary>

You might need to say something in the mic / type something in the text box for Mantella to realize that the conversation has ended (while it is on "Listening..." / "Waiting for player input..." it does not actively look out for the conversation ending). It is best to end conversations by simply saying / typing "goodbye" to avoid this issue.
</details>
<br>

#### ALL GAMES : RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work
<details>
<summary>Details</summary>

xVASynth related warning when started by Mantella. Thus far has not impacted Mantella so it can be safely ignored.

You can also download [ffmpeg](https://ffmpeg.org/download.html) and put a copy of ffmpeg.exe in the same folder as Mantella and xVASynth and the error will be resolved, since ffmpeg will be found.
</details>
<br>

#### ALL GAMES : Error: [Errno 2] No such file or directory: 'data/skyrim_characters.csv' or 'data/fallout4_characters.csv'
<details>
<summary>Details</summary>

This may be caused by `Mantella.exe` being ran through MO2 or Vortex. `Mantella.exe` will start itself automatically when you start the game.
</details>
<br>