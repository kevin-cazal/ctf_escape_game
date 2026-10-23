# Example room content

A room content is a **workshop subject** (the format of Manta-Epitech-Academy/ctfd-workshop-platform,
docs/CONTENT_CONVENTION.md), reduced to what a room needs. Zip this folder (or a folder like it)
and load it in the dashboard: Prepare > Room contents > "Or from a zip file". The same files at
the root of a public git repository load with "From a public git repository".

```
subject.yaml          name, slug, and the list of documents
intro.md              the entrypoint document (the dashboard replaces it with the room's welcome)
salle.md              the steps: one `## Title` + `<!-- ws: ... -->` marker per step
files/<step id>/...   the step's attachments (see "Files")
img/...               images shown in the text (see "Images in the text")
flags.yaml            one flag per step (see "Flags" below)
```

## Steps

In `salle.md`, every step is a level 2 title followed by its marker:

```
## Title of the step
<!-- ws: {type: exercise, id: etape1, validation: flag, points: 100} -->

Description in markdown. Use ### for titles inside a description.
```

- `id` is unique in the file; it is how the flag and the files find their step.
- `validation: flag` on every step: a room only holds flag steps.
- Steps are played in the order of the file, each one unlocking the next.
- Do **not** add the door step ("Entrée dans la salle"): the dashboard adds it.

A hint, free, under a step:

```
<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

Text of the hint.

</details>
```

## Files

A step's attachments are **all the files in `files/<step id>/`**, where `<step id>` is the `id` in
the step's `<!-- ws: ... -->` marker. Here, `files/etape1/indice.txt` belongs to the step
`id: etape1`.

Nothing else to write: no list of files, no download link in the text. When the room is pushed,
the dashboard adds a "Fichiers à télécharger" list under the step by itself, with one link per
file. A step with no folder has no attachment.

## Images in the text

To show an image inside a step's text (the duck in step 1), put it **anywhere outside `files/`**
(here `img/canard.png`) and use a normal markdown image, with a path relative to the `.md` file:

```
![Un canard](img/canard.png)
```

The dashboard keeps the image with the content, and the platform uploads it when the room is
pushed.

An image placed in `files/<step id>/` is an **attachment** instead: it is shown in the text *and*
offered as a download, both added by the dashboard. Do not link it a second time.

## Flags

`flags.yaml`, one entry per step:

```
flags:
  etape1:
    value: ctf{exemple}
    case_insensitive: true
```

In a public repository never commit it in plaintext: encrypt it with the usual passphrase and
commit only `flags.yaml.gpg`:

```
gpg -c --cipher-algo AES256 -o flags.yaml.gpg flags.yaml
```

The dashboard opens `flags.yaml.gpg` with its passphrase. A flag it cannot open is left empty, to be
typed in the editor. Optionally, `checkpoint_codes.yaml(.gpg)` sets the room code:
`codes: {porte: pingouin}`.

The easiest way to get a correct folder: create the room in the dashboard, then **Export zip**.
