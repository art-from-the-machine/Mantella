(issues-qna)=
# Issues Q&A
For detailed guides on Mantella setup and installation, see the {doc}`/pages/installation` and {doc}`/pages/installation_fallout4` pages. If you can't find your issue in the list below, please reach out on [Discord](https://discord.gg/Q4BJAdtGUE).

## Table of Contents
- [Mantella Exe](#mantella-exe)
- [Conversations](#conversations)
- [Text Input](#text-input)
- [Mic](#mic)
- [Skyrim](#skyrim)
- [Fallout 4](#fallout-4)
- [LLMs](#llms)
- [NPC and Prompt Editing](#npc-and-prompt-editing)
- [Text-to-Speech](#text-to-speech)

## Mantella Exe
<details>
<summary><strong>Mantella.exe opens, but does not display any text</strong></summary>

Ensure that you are not running Mantella.exe via a Vortex / Mod Organizer 2 shortcut, as this does not start the program properly. Otherwise, it may take some time to start when running for the first time.
</details>
<br>

<details>
<summary><strong>Mantella.exe shows an error "cannot connect to port 4999"</strong></summary>

This is likely an issue with your antivirus / firewall blocking Mantella from connecting to your game. Please allow Mantella.exe through your firewall and add it to your antivirus's whitelist. Mantella.exe can be found in `your mods folder\Mantella\SKSE\Plugins\MantellaSoftware\Mantella.exe`.
</details>
<br>

<details>
<summary><strong>Mantella.exe closes as soon as it opens</strong></summary>

This is likely an issue with your antivirus / firewall blocking Mantella from connecting to your game. Please allow Mantella.exe through your firewall and add it to your antivirus's whitelist. Mantella.exe can be found in `your mods folder\Mantella\SKSE\Plugins\MantellaSoftware\Mantella.exe`.
</details>
<br>

<details>
<summary><strong>The Mantella UI does not open automatically</strong></summary>

The Mantella UI should open in your browser when the Mantella exe starts, but if it does not, it can be accessed here: [http://localhost:4999/ui/?__theme=dark](http://localhost:4999/ui/?__theme=dark).

Note that in order to access the Mantella UI, the Mantella exe needs to be running.
</details>
<br>

<details>
<summary><strong>FileNotFoundError: [WinError 2] Unable to find the specified file</strong></summary>

This error often occurs if your Mantella save data is automatically storing on OneDrive. Please try navigating to `your mods folder\Mantella\SKSE\Plugins\MantellaSoftware\custom_user_folder.ini` and setting the path within this file to a folder that OneDrive does not have access to.
</details>
<br>

<details>
<summary><strong>Error: [Errno 2] No such file or directory: 'data/skyrim_characters.csv' or 'data/fallout4_characters.csv'</strong></summary>

This may be caused by `Mantella.exe` being ran through MO2 or Vortex. `Mantella.exe` will start itself automatically when you start the game.
</details>
<br>


## Conversations
<details>
<summary><strong>NPCs only respond with "I can't find the right words at the moment."</strong></summary>

This either means the LLM server is currently down or the API key has not been set up correctly / is missing payment information. If it is the latter issue, please check Documents/My Games/Mantella/logging.log to see the exact error.
</details>
<br>

<details>
<summary><strong>NPCs keep repeating the same line of dialogue</strong></summary>

This is likely a permissions issue with Mantella accessing your game folder. If your game folder is installed in Program Files, please move it to a [different folder](https://art-from-the-machine.github.io/Mantella/pages/installation.html#skyrim). 

If this only happens occasionally, it is likely because the next voiceline is being activated before the voiceline file is ready. You can mitigate this by increasing the value of `Wait Time Buffer` in the `Large Language Model -> Advanced` tab in the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui).
</details>
<br>

<details>
<summary><strong>Voicelines are displaying in the Mantella window but not playing in game</strong></summary>

Mantella adds new voiceline files to the game, and sometimes these fail to register correctly when you first launch Mantella. To fix this, once Mantella is installed and the mod's items have been added to your inventory, create a new save file in your game (you don't have to start a new game). Then load from that save. Voicelines should now play correctly in game.

For Skyrim players, if you have a mod called MinAI installed, please download `Mantella v0.13 - MGO Patch` from the "Optional files" section [here](https://www.nexusmods.com/skyrimspecialedition/mods/98631?tab=files).
</details>
<br>

<details>
<summary><strong>Cannot start new conversation after ending previous conversation (conversation ended message)</strong></summary>

You might need to say something in the mic / type something in the text box for Mantella to realize that the conversation has ended (while it is on "Listening..." / "Waiting for player input..." it does not actively look out for the conversation ending). It is best to end conversations by simply saying / typing "goodbye" to avoid this issue.
</details>
<br>


## Text Input
<details>
<summary><strong>Can text input be used instead of a mic?</strong></summary>

Yes. Go to Mantella's MCM menu in-game and disable mic input to enable text input. The default key to open the text box is H (this key can be changed in the MCM settings). [UIExtensions](https://www.nexusmods.com/skyrimspecialedition/mods/17561) is required for text input to work.
</details>
<br>

<details>
<summary><strong>How do I open the text box in-game?</strong></summary>

The default key to open the text box is H (this key can be changed in Mantella's MCM settings). [UIExtensions](https://www.nexusmods.com/skyrimspecialedition/mods/17561) is required for text input to work.
</details>
<br>


## Mic
<details>
<summary><strong>Microphone is not picking up sound / exe stuck on "Listening..."</strong></summary>

Make sure that your mic is picking up correctly on other software and that it is set as your default. For example, you can go to User Settings -> Voice & Video on Discord to test your mic. Otherwise, try adjusting the `Audio Threshold` setting under the `Speech-to-Text` tab of the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui) (following the instructions provided for that setting). If all else fails, make sure that no other microphones are plugged in except the one you want to use. There may be a rogue microphone such as a webcam picking up as your default.
</details>
<br>

<details>
<summary><strong>NPCs keep cutting me off mid-sentence</strong></summary>

You can increase the `Pause Threshold` (how many seconds of silence before your mic input is cut off) in the `Speech-to-Text` tab of the Mantella UI.
</details>
<br>

<details>
<summary><strong>'NoneType' object has no attribute 'close'</strong></summary>

This error means that Whisper is unable to find a connected microphone. Please ensure that you have a working microphone plugged in and enabled.
</details>
<br>

<details>
<summary><strong>Mantella.exe closes after "VAD filter removed 00:00.000 of audio" statement</strong></summary>

This is an issue related to CUDA. Please try setting `Process Device` to "cpu" under the `Speech-to-Text -> Advanced` tab of the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui).
</details>
<br>

<details>
<summary><strong>Mic input struggles with non-English languages</strong></summary>

The default speech-to-text model, Moonshine, struggles to transcribe non-English languages. Please try switching to Whisper via the `Speech-to-Text`->`STT Service` setting in the Mantella UI.
</details>
<br>

<details>
<summary><strong>Mantella.exe closes after "VAD filter removed 00:00.000 of audio" statement</strong></summary>

This is an issue related to CUDA. Please try setting `Process Device` to "cpu" under the `Speech-to-Text -> Advanced` tab of the [Mantella UI](https://art-from-the-machine.github.io/Mantella/pages/installation.html#mantella-ui).
</details>
<br>


## Skyrim
<details>
<summary><strong>Skyrim crashes as soon as an NPC begins speaking</strong></summary>

Mantella can sometimes have compatability issues with [Fuz Ro D'oh](https://www.nexusmods.com/skyrimspecialedition/mods/15109). Please try running Mantella with Fuz Ro D'oh disabled.
</details>
<br>

<details>
<summary><strong>Mantella spells have not been added to my inventory</strong></summary>

This is an issue with the way the Mantella mod has been installed. Please ensure any previous versions of Mantella have been completely removed before installing the new version:

Open Skyrim, end all Mantella conversations and unequip the Mantella spell, and create a save. In your mod manager, disable the old Mantella mod. Open your newly created save and create another save (now with no Mantella mod). Finally, in your mod manager enable the new Mantella mod. This should effectively "reset" the mod. When you next open your recent save, you should see a notification that the Mantella spell has been added to your inventory.
</details>
<br>

<details>
<summary><strong>Voicelines are being displayed in Mantella.exe but are not being said in-game</strong></summary>

Try creating a save and then reloading that save. This ensures that the Mantella voice files get registered correctly. 

If the above fails, a more unlikely reason for voicelines not playing is if you have updated the Mantella mod with a more recent version by replacing files in the mod's folder. If this is the case, open Skyrim, end all Mantella conversations and unequip the Mantella spell, and create a save. In your mod manager, disable the old Mantella mod. Open your newly created save and create another save (now with no Mantella mod). Finally, in your mod manager enable the new Mantella mod. This should effectively "reset" the mod. When you next open your recent save, you should see a notification that the Mantella spell has been added to your inventory.
</details>
<br>

<details>
<summary><strong>PapyrusUtil error / SKSE plugins fail to load</strong></summary>

Please ensure you have installed the correct versions of Mantella's required mods for your Skyrim version. You can check your Skyrim version by right-clicking its exe file in your Skyrim folder and going to Properties -> Details -> File version. VR users can just download the VR version of each mod if available, or SE if not.
</details>
<br>


## Fallout 4
<details>
<summary><strong>On game load the following message is displayed : "F4SE or SUP_F4SE not properly installed, Mantella will not work correctly"</strong></summary>

Multiples reasons can cause this issue:

1: Invalid or absent F4SE install, make sure to download the one from this link : [F4SE](https://f4se.silverlock.org/). Make sure to download the appropriate version (desktop or VR).

2: Incorrect FO4 version number. Mantella is supposed to run with version 1.10.163.0 (for Fallout 4 desktop) or 1.2.72.0 (for Fallout 4 VR).

3: [SUP F4SE](https://www.nexusmods.com/fallout4/mods/55419) or [SUP F4SEVR](https://www.nexusmods.com/fallout4/mods/64420) (whichever is appropriate for your game) isn't correctly installed.

4: Make sure you're actually launching the game with : f4se_loader.exe

5: If you are running the mod via the GOG version of Fallout 4, you might encounter issues getting F4SE to load, see [this workaround](https://github.com/ModOrganizer2/modorganizer/issues/1856#issuecomment-1685925528)

</details>
<br>

<details>
<summary><strong>Lip sync isn't working at all after adding a new NPC</strong></summary>

Lip files need to be present at launch for the game to register it. Restarting Fallout 4 should correct the issue. The Mantella Mod on the Mod Nexus will cover all the base game and all the main DLCs but any other NPC will need to have a lip file named 00001ED2_1.lip present at launch in its voice type folder in data\Sound\Voice\Mantella.esp
</details>
<br>

<details>
<summary><strong>The NPC is lip syncing a different line than the one said in game</strong></summary>

This might be caused by an invalid mod file path (ex: a file path pointing to for another game's data folder). Double check the file paths. Please note that there is a known issue in Fallout 4 that causes lip sync to be cut short for longer lines.
</details>
<br>

<details>
<summary><strong>Every time a conversation is started the notification is : "NPC not added. Please try again after your next response."</strong></summary>

Multiples reasons can cause this issue:

1: Invalid game file path in the config.ini. Double check your filepath for `fallout4_folder` or `fallout4VR_folder`.

2: Wrong game set in the config.ini, double check the value for `game = ` 

3: If you're running a modlist that uses Root builder, there might be a sync issue between Mantella and your game. Make sure you load the game first then load Mantella after to avoid the _Mantella text files getting out of sync.

4: Double check that you installed the correct version of the Mantella Mod : desktop or VR.

</details>
<br>

<details>
<summary><strong>After trying to start a conversation, the notification says "Starting a conversation with NPCNAME", but nothing happens in Fallout 4 or the Mantella console</strong></summary>

Multiples reasons can cause this issue:

1: Invalid game file path in the config.ini. Double check your filepath for `fallout4_folder` or `fallout4VR_folder`.

2: Wrong game set in the config.ini. Double check the value for `game = ` 

</details>
<br>

<details>
<summary><strong>The text input menu isn't showing up when the hotkey is pressed after the notification "Awaiting user input for X seconds"</strong></summary>

Multiples reasons can cause this issue:

1: Double check that the install for [Textinputmenu](https://www.nexusmods.com/fallout4/mods/27347) is correct.

2: Try resetting the text input hotkey in the settings holotape under `Main settings`. You will need to enter a [DirectX scan code](https://falloutck.uesp.net/wiki/DirectX_Scan_Codes)

</details>
<br>

<details>
<summary><strong>The Mantella gun & holotape do not get added on load and are not available at the Chem Station in UTILITY</strong></summary>

This is an issue with the way the Mantella esp mod itself has been installed. Please check your Fallout 4 version by right-clicking its exe file in your Fallout 4 folder and going to Properties -> Details . The "File version" should be listed here and it should be 1.10.163.0 (for Fallout 4 desktop) or 1.2.72.0 (for Fallout 4 VR). If you are using VR, there are separate versions of the required mods for SUP_F4SE : [SUP F4SEVR](https://www.nexusmods.com/fallout4/mods/64420). If you are running the mod via the GOG version of Fallout 4, you might encounter issue getting F4Se to load, see [this workaround](https://github.com/ModOrganizer2/modorganizer/issues/1856#issuecomment-1685925528).
</details>
<br>

<details>
<summary><strong>The mod is enabled but the gun doesn't appear in game at game load</strong></summary>

This might be caused by multiple reasons:
1. Make sure you are past the intro and first Vault.
2. Try to fast travel on the map.
3. Check that MantellaQuest is running by using the console and typing 'sqv MantellaQuest'. Make sure that the ini files have been modified to allow modding: [Howto: Enable Modding - Archive Invalidation](https://www.nexusmods.com/fallout4/articles/3831).
4. Double check that [Fallout 4 Version Check Patcher](https://www.nexusmods.com/fallout4/mods/42497?tab=description) has been installed.

</details>
<br>


## LLMs
<details>
<summary><strong>NPCs keep describing actions out loud in-game</strong></summary>

By default, LLMs are instructed to not describe actions in Mantella's system prompt. However, some smaller LLMs struggle with following instructions. To fix this, try switching to a larger LLM. You can also try adding more explicit instructions within the `Prompts` tab of the Mantella UI.
</details>
<br>

<details>
<summary><strong>LLM sometimes returns 0 tokens</strong></summary>

Sometimes certain LLMs can fail to generate a response. Try switching to a different LLM if this issue persists.
</details>
<br>

<details>
<summary><strong>ERROR: LLM API Error: An error occurred during streaming</strong></summary>

This can either be because of a temporary issue with your LLM provider, your account balance is too low, or free requests have reached their daily / hourly / etc limit. Please either try switching to a different LLM temporarily, or checking your account balance / free usage limits.
</details>
<br>

<details>
<summary><strong>NPCs do not follow / attack / show their inventory / etc</strong></summary>

Ensure that the action you are trying to get the NPC to carry out is both enabled under the `Other`->`Actions` setting in the Mantella UI as well as in Mantella's MCM menu in-game. If actions still fail to trigger correctly, try switching to a larger LLM (some smaller LLMS struggle to follow instructions). 

If no other options work, it is possible to force actions to trigger by simply stating the action and nothing else in your response. For example, to force an NPC to follow you, simply say / type "follow".
</details>
<br>


## NPC and Prompt Editing
Please see {doc}`/pages/adding_modded_npcs` for a detailed guide on how to add backstories and/or change the voice models of mod-added NPCs, generic NPCs, or edit existing NPCs.

<details>
<summary><strong>NPC 'XYZ' could not be found in skyrim_characters.csv or fallout4_characters.csv</strong></summary>

This means that the NPC's name exactly as written in the error message could not be found in the characters.csv. If you are running your game in another language, sometimes the NPC's name in this language does not match up to the English name, causing this error. It might also mean that the character is missing from characters.csv.
</details>
<br>

<details>
<summary><strong>"Invalid start byte" error</strong></summary>

This error occurs when you introduce character symbols that can't be recognized either in MantellaSoftware/config.ini, skyrim_characters.csv or fallout4_characters.csv. Please try re-downloading these files. Note that if you are using Excel to edit the CSV, Excel often likes to corrupt CSVs when saving these files. If you are experiencing issues with Excel, there are free CSV editors available such as [LibreOffice](https://www.libreoffice.org/). 
</details>
<br>


## Text-to-Speech
<details>
<summary><strong>API Error: cannot access local variable 'audio_file' where it is not associated with a value</strong></summary>

This error occurs when something has failed in a previous step (likely an issue with xVASynth / not having FaceFXWrapper installed). Please check your Documents/My Games/Mantella/logging.log file to see the error which occurred before this, which should provide more clarification. If you are still ensure, please share your logging.log file to the Discord's issues channel.
</details>
<br>

<details>
<summary><strong>ERROR: xVASynth Error: [WinError 5] Access is denied</strong></summary>

This happens when your antivirus is blocking Mantella.exe from working. Please add Mantella.exe to your safe list.
</details>
<br>

<details>
<summary><strong>RuntimeWarning: Couldn't find ffmpeg or avconv - defaulting to ffmpeg, but may not work</strong></summary>

xVASynth related warning when started by Mantella. Thus far has not impacted Mantella so it can be safely ignored.

You can also download [ffmpeg](https://ffmpeg.org/download.html) and put a copy of ffmpeg.exe in the same folder as Mantella and xVASynth and the error will be resolved.
</details>
<br>

<details>
<summary><strong>RuntimeError('PytorchStreamReader failed reading zip archive: failed finding central directory')</strong></summary>

If an xVASynth voice model is corrupted, this error will display in Documents/My Games/Mantella/logging.log. Please re-download the voice model in this case. You may alternatively need to redownload xVASynth.

A way to check for other corrupted voice models, is to compare the file sizes within /models/skyrim/ folder of xVASynth. If they diverge from the norms, redownload **just** those. The norms for voice model sizes are **~54 MB** and/or **~90 MB** (v2 voice models) & **~220 MB** or **~260 MB** (v3 voice models).
</details>
<br>

<details>
<summary><strong>Loading voice model... xVASynth Error: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))</strong></summary>

If this xVASynth Error occurs after the "Loading voice model..." message (as can be seen in your Documents/My Games/Mantella/logging.log file), this is likely an issue with a corrupted voice model. Please try redownloading the model from [here](https://www.nexusmods.com/skyrimspecialedition/mods/44184) for Skyrim or [here](https://www.nexusmods.com/fallout4/mods/49340) for Fallout 4. If you have `use_cleanup` enabled, try setting this value to 0 in MantellaSoftware/config.ini.

If this does not resolve your issue, please share the text found in your xVASynth/server.log file on the [Discord's #issues channel](https://discord.gg/Q4BJAdtGUE) for further support.
</details>
<br>

<details>
<summary><strong>ERROR:root:Could not run Piper. Ensure that the path "" is correct</strong></summary>

This error often occurs when attempting to start Mantella.exe manually instead of letting it launch automatically on game startup. Please copy the path to your Piper installation (which should be `your mods folder\Mantella\SKSE\Plugins\MantellaSoftware\piper`) and paste this path in the `Text-to-Speech`->`Piper Folder` setting in the Mantella UI.
</details>
<br>