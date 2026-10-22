# Encodage
<!-- ws: {type: chapter, topology: linear} -->

## Entrée dans la salle
<!-- ws: {type: exercise, id: porte, validation: checkpoint, points: 0} -->

Appelle un encadrant : il ouvre la salle pour ton équipe et ton chrono démarre.

## Hexadécimal
<!-- ws: {type: exercise, id: hex, validation: flag, points: 50} -->

Un agent a laissé ce message sur le tableau de la salle :

**0x50 0x49 0x52 0x41 0x54 0x45**

Chaque nombre qui commence par `0x` est écrit en hexadécimal (base 16). Chaque nombre correspond à une lettre.

Le flag est le mot caché.

format: ctf{mot}

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

En base 16, on compte avec 16 symboles : de 0 à 9, puis A, B, C, D, E et F.

</details>

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

Un ordinateur range chaque lettre sous un numéro, dans une table qui s'appelle la table ASCII. Cherche-la sur internet.

</details>

## Décimal
<!-- ws: {type: exercise, id: dec, validation: flag, points: 50} -->

Deuxième message, cette fois sans `0x` :

**84 82 69 83 79 82**

Ces nombres sont écrits en décimal, la base que tu utilises tous les jours. Ils se lisent avec la même table que le message précédent.

Le flag est le mot caché.

format: ctf{mot}

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

La table ASCII donne le numéro de chaque lettre en hexadécimal et en décimal. Regarde la bonne colonne.

</details>

## Le mélange
<!-- ws: {type: exercise, id: mixed, validation: flag, points: 100} -->

Le dernier message mélange les deux bases : certains nombres sont en hexadécimal, d'autres en décimal. Un même mot peut contenir les deux.

**0x62 114 97 118 0x6F 0x20 97 0x67 101 110 0x74 32 115 101 0x63 114 0x65 116**

Les espaces entre les mots sont codés eux aussi.

Le flag est la phrase cachée, en minuscules.

format: ctf{phrase}

<!-- ws: {type: hint, cost: 0} -->
<details><summary>Indice</summary>

Décode les nombres un par un. Le `0x` te dit dans quelle base lire chacun.

</details>
