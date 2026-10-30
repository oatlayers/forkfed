# Release output

`scripts/07_build_apkg.py` writes the built deck here:

```text
Forkfed_Chinese.apkg
```

The package is about 122 MB, so it is ignored by Git and published as a GitHub release asset instead. Download the latest package from [Releases](https://github.com/oatlayers/forkfed/releases/latest).

To rebuild:

```powershell
python scripts/07_build_apkg.py
python scripts/validate_deck.py
```
