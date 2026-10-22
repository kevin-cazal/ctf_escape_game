# Stéganographie
<!-- ws: {type: chapter, topology: linear} -->

## Entrée dans la salle
<!-- ws: {type: exercise, id: porte, validation: checkpoint, points: 0} -->

Appelle un encadrant : il ouvre la salle pour ton équipe et ton chrono démarre.

## Faux texte
<!-- ws: {type: exercise, id: faux_texte, validation: flag, points: 60} -->

Un fichier texte a été trouvé, mais il contient des caractères très étranges… Est-ce vraiment un fichier texte?

format: ctf{solution}

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

Les types de fichiers n'est pas forcément lié à son extension

</details>

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

Essayez de trouver le type de fichier en utilisant les méthodes de détection de fichiers

</details>

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

La majorité des fichiers binaires comportent une 'entête': quelques octets au début du fichier qui déterminent son type

</details>
