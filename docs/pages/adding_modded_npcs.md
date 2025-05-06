(adding-modded-npcs)=
# Add or Edit NPCs
Character override files can be used to either make new characters available to Mantella or override existing NPC bios and/or voice models.

Character overrides can be added to this folder:  
`..\Documents\My Games\Mantella\data\{game}\character_overrides\`

```{admonition} Note
:class: seealso

If you are a mod creator and want to include the bio of your NPC with your mod, please instead add your character override to `{mod location}\SKSE or F4SE\Plugins\MantellaSoftware\data\{game}\character_overrides\`.
```

Any `.csv` or `.json` file placed in your overrides folder will be loaded on start-up of Mantella. Removing a file will remove the override on the next start of Mantella.

If you intend to override an existing entry, you only need to include the columns/fields that are required to uniquely identify the row/entry you want to override in the original database as well as the fields you want to replace.

If you are creating a new entry for an NPC not included in the database yet, make sure that your entry is unique and that it includes all the fields that Mantella requires like the bio and the voice model.

**Example 1:**  

`Lydia.json`
```json
{
    "name": "Lydia",
    "voice_model": "FemaleEvenToned",
    "bio": "Lydia is a Bosmer thief. Her stew is horrible.",
    "race": "Bosmer",
    "species": "Elf"
}
```

`Lydia.csv`
```csv
name,voice_model,bio,race,species
Lydia,FemaleEvenToned,Lydia is a Bosmer thief. Her stew is horrible.,Bosmer,Elf
```

Both of these examples are identical. The first is in `.json` format the second one is `.csv`. Both files override Lydia's entry in the database, replacing her bio, race and species columns/fields. Her other fields like the voice model will stay as they are.

Both formats can have multiple entries in one file.

**Example 2:**  

`Lydias.json`
```json
[
    {
        "name": "Lydia",
        "bio": "Lydia is a Bosmer thief. Her stew is horrible.",
        "race": "Bosmer",
        "species": "Elf"
    },
    {
        "name": "Lydia's evil twin",
        "voice_model": "FemaleEvenToned",
        "skyrim_voice_folder": "FemaleEvenToned",
        "bio": "Where does she come from? Or is this just Lydia after she tasted her own stew?",
        "race": "Nord",
        "gender": "Female",
        "species": "Human"
    }
]
```

`Lydias.csv`
```csv
name,voice_model,skyrim_voice_folder,bio,race,species
Lydia,FemaleEvenToned,,Lydia is a Bosmer thief. Her stew is horrible.,Bosmer,Elf
Lydia's evil twin,FemaleEvenToned,FemaleEvenToned,Where does she come from? Or is this just Lydia after she tasted her own stew?,Nord,Female,Human
```

The first entry/row will work exactly as in Example 1. The second entry will add a new NPC to the database as there is no entry for Lydia's evil twin that could be overwritten.

For further support and examples of how other users have added modded NPCs, see the [custom-npcs channel on Discord](https://discord.gg/Q4BJAdtGUE).