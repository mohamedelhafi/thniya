# Dépannage

Les problèmes déjà rencontrés sur ce projet, et leur solution.

## Installation et Docker

**Sous Windows, un chemin comme `/tiles` devient `C:/Program Files/Git/tiles`.**
Git Bash convertit les chemins. Préfixez la commande :

```bash
MSYS_NO_PATHCONV=1 docker compose --profile tasks run --rm pmtiles extract …
```

**La construction du graphe OTP s'arrête, ou le PC rame.**
Elle a besoin de mémoire. Dans Docker Desktop, donnez au moins 8 Go (Settings → Resources). La mémoire de Java est
réglée dans `infra/.env` (`OTP_BUILD_XMX`, `OTP_SERVE_XMX`).

**`failed to connect to the docker API`**
Docker Desktop n'est pas démarré. Lancez-le et attendez qu'il soit prêt.

**`curl http://127.0.0.1:8090/api/v1/meta` ne répond pas juste après `up -d`.**
Les services mettent environ 30 secondes à démarrer, OTP un peu plus. Vérifiez leur état :

```bash
docker compose -f compose.yml -f compose.local.yml ps
```

**La recherche ne trouve aucune adresse, seulement des arrêts.**
L'index Photon n'est pas construit : lancez `bash scripts/photon-import.sh` depuis `infra/`. Sans index, l'API
continue avec les arrêts seuls, ce qui est voulu.

**Le fond de carte reste vide.**
Le fichier `data/build/tiles/tunisie.pmtiles` manque : refaites l'étape `pmtiles extract` du guide d'installation.

## Les données

**Ma nouvelle ligne n'apparaît pas dans les trajets.**
Dans l'ordre :

1. `lint` affiche `0 erreur(s)` ?
2. La ligne, son réseau, son mode et ses arrêts sont-ils tous en `status: active` ?
3. Avez-vous relancé `build`, `otp-prepare`, `otp-build`, puis redémarré OTP ?
4. Avez-vous attendu 5 minutes, ou cherché un trajet à une heure où la ligne circule ?

**L'app montre encore les anciennes données.**
L'API recharge `app-meta.json` en environ 30 secondes, et la passerelle garde certaines réponses en cache jusqu'à
5 minutes. Le numéro de version des données est affiché dans Réglages.

**Les messages de `lint` s'affichent avec des caractères bizarres (`�`) sous Windows.**
C'est l'encodage de la console, pas une erreur dans vos données. Lancez la commande dans le conteneur `tools`, ou
définissez `PYTHONIOENCODING=utf-8`.

## L'app

**« Pas de connexion » sur un vrai téléphone.**
La redirection USB a sauté (elle disparaît à chaque installation ou débranchement). Relancez :

```bash
adb reverse tcp:8090 tcp:8090
```

**« Pas de connexion » sur l'émulateur.**
Vérifiez que l'app a été lancée avec `--dart-define=API_BASE_URL=http://10.0.2.2:8090` et que l'API répond sur le PC.

**Des bandes jaunes et noires apparaissent (« RenderFlex overflowed »).**
C'est un débordement de mise en page, visible seulement en mode debug. Le message dans la console donne le fichier et
la ligne. Cause fréquente : un `IntrinsicHeight` autour d'un contenu animé (voir [L'app Flutter](09-app-flutter.md)).

**L'app est lente.**
Le mode debug est bien plus lent que la version finale. Pour juger de la fluidité, utilisez `flutter run --release`.

**Le fond de carte est clair alors que l'app est en thème sombre.**
Les anciennes versions partageaient le cache de tuiles entre les styles. Mettez l'app à jour, ou videz ses données
dans les réglages Android.

## Toujours bloqué ?

Ouvrez un ticket **« Bug »** sur GitHub, avec les étapes pour reproduire le problème, le message d'erreur complet et
votre système (Windows, macOS, Linux ; version de Docker et de Flutter).
