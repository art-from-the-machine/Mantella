(adding-modded-npcs)=
# Adding Modded NPCs
Mantella allows you to talk to any NPC. If you cast the Mantella spell on an unknown / modded NPC, a message will display in Mantella.exe asking you to restart Skyrim or Fallout 4. Once this is done, the NPC will be able to speak to you. 

If a given NPC cannot be found in `MantellaSoftware/data/skyrim_characters.csv` or `MantellaSoftware/data/fallout4_characters.csv` (depending on your game install), Mantella will try its best to fill in the blanks on the NPC, making an educated guess on the NPC's background based on their name (eg Whiterun Guard) and on their voice model based on various factors such as race and sex.

Of course, if you are unhappy with Mantella's assumptions, you can add full support for modded NPCs to `MantellaSoftware/data/skyrim_characters.csv` or `MantellaSoftware/data/fallout4_characters.csv` by adding a new row containing the NPC's name (`name`), background description (`bio`), and voice model (`voice_model`). The rest of the column entries can be left blank (as long as the name isn't duplicated elsewhere in the list). If you don't have Excel, you can open this CSV file with [LibreOffice](https://www.libreoffice.org/). 

Note that if the modded NPC is custom voiced there may not be an xVASynth model available, and you will need to assign the NPC a vanilla voice. By default, Mantella does not create memories for NPCs missing from `skyrim_characters.csv` or `fallout4_characters.csv` as they are assumed to be generic (eg there are many NPCs called "Whiterun Guard" so it does not make sense for them all to share the same memory).

For further support and examples of how other users have added modded NPCs, see the [custom-npcs channel on Discord](https://discord.gg/Q4BJAdtGUE).
