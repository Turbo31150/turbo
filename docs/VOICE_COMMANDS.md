# JARVIS - Reference Commandes Vocales

> Genere automatiquement le 2026-03-15 19:49 | Cluster M1

## Statistiques

| Metrique | Valeur |
|----------|--------|
| Commandes vocales | 180 |
| Skills | 148 |
| Domino Pipelines | 494 |
| Macros | 30 |
| Corrections phonetiques | 325 |
| Triggers totaux | 1325 |

---

## Commandes Vocales

### advanced_apps (10 commandes)

- **adv_app_discord** [bash]
  - Description: Lance Discord
  - Triggers: `ouvre discord`, `lance discord`, `discord`
  - Action: `discord &>/dev/null &`
  - Utilisations: 0

- **adv_app_gimp** [bash]
  - Description: Lance GIMP
  - Triggers: `ouvre gimp`, `lance gimp`, `gimp`
  - Action: `gimp &>/dev/null &`
  - Utilisations: 0

- **adv_app_libreoffice** [bash]
  - Description: Lance LibreOffice
  - Triggers: `ouvre libre office`, `lance libreoffice`, `libre office`
  - Action: `libreoffice &>/dev/null &`
  - Utilisations: 0

- **adv_app_nautilus** [bash]
  - Description: Lance le gestionnaire de fichiers
  - Triggers: `ouvre le gestionnaire de fichiers`, `fichiers`, `nautilus`, `explorateur de fichiers`
  - Action: `nautilus &>/dev/null &`
  - Utilisations: 0

- **adv_app_obs** [bash]
  - Description: Lance OBS Studio
  - Triggers: `ouvre obs`, `lance obs studio`, `obs studio`
  - Action: `obs &>/dev/null &`
  - Utilisations: 0

- **adv_app_spotify** [bash]
  - Description: Lance Spotify
  - Triggers: `ouvre spotify`, `lance spotify`, `spotify`
  - Action: `spotify &>/dev/null &`
  - Utilisations: 0

- **adv_app_steam** [bash]
  - Description: Lance Steam
  - Triggers: `ouvre steam`, `lance steam`, `steam`
  - Action: `steam &>/dev/null &`
  - Utilisations: 0

- **adv_app_thunderbird** [bash]
  - Description: Lance Thunderbird email
  - Triggers: `ouvre thunderbird`, `lance thunderbird`, `ouvre les mails`
  - Action: `thunderbird &>/dev/null &`
  - Utilisations: 0

- **adv_app_vlc** [bash]
  - Description: Lance VLC media player
  - Triggers: `ouvre vlc`, `lance vlc`, `vlc`
  - Action: `vlc &>/dev/null &`
  - Utilisations: 0

- **adv_app_vscode** [bash]
  - Description: Lance Visual Studio Code
  - Triggers: `ouvre vscode`, `lance vscode`, `visual studio code`, `ouvre l'éditeur`
  - Action: `code &>/dev/null &`
  - Utilisations: 0


### advanced_audio (10 commandes)

- **adv_audio_bluetooth_devices** [bash]
  - Description: Liste les appareils bluetooth connectes
  - Triggers: `appareils bluetooth`, `bluetooth connectés`, `haut-parleur bluetooth`
  - Action: `bluetoothctl devices Connected 2>/dev/null || bluetoothctl paired-devices`
  - Utilisations: 0

- **adv_audio_list_sinks** [bash]
  - Description: Liste les peripheriques audio
  - Triggers: `périphériques audio`, `sorties audio`, `liste les sorties son`
  - Action: `pactl list sinks short`
  - Utilisations: 0

- **adv_audio_mute_toggle** [bash]
  - Description: Active ou desactive le son
  - Triggers: `mute`, `coupe le son`, `active le son`, `toggle mute`
  - Action: `pactl set-sink-mute @DEFAULT_SINK@ toggle`
  - Utilisations: 0

- **adv_audio_record_screen** [bash]
  - Description: Lance l'enregistrement d'ecran
  - Triggers: `enregistre l'écran`, `enregistrement écran`, `record screen`
  - Action: `gnome-screen-recorder &>/dev/null & || echo 'Utilisez Ctrl+Shift+Alt+R pour enregistrer sous GNOME'`
  - Utilisations: 0

- **adv_audio_screenshot** [bash]
  - Description: Prend une capture d'ecran
  - Triggers: `capture écran`, `screenshot`, `prends une capture`
  - Action: `gnome-screenshot -f /home/turbo/Images/screenshot_$(date +%Y%m%d_%H%M%S).png && echo 'Capture sauveg`
  - Utilisations: 0

- **adv_audio_screenshot_area** [bash]
  - Description: Prend une capture d'ecran d'une zone
  - Triggers: `capture d'une zone`, `screenshot zone`, `capture sélection`
  - Action: `gnome-screenshot -a -f /home/turbo/Images/screenshot_area_$(date +%Y%m%d_%H%M%S).png && echo 'Captur`
  - Utilisations: 0

- **adv_audio_volume_100** [bash]
  - Description: Met le volume au maximum
  - Triggers: `volume au max`, `volume maximum`, `volume à 100`
  - Action: `pactl set-sink-volume @DEFAULT_SINK@ 100%`
  - Utilisations: 0

- **adv_audio_volume_50** [bash]
  - Description: Met le volume a 50 pourcent
  - Triggers: `volume à 50`, `volume à cinquante`, `volume 50 pourcent`
  - Action: `pactl set-sink-volume @DEFAULT_SINK@ 50%`
  - Utilisations: 0

- **adv_audio_volume_down** [bash]
  - Description: Diminue le volume de 10 pourcent
  - Triggers: `baisse le volume`, `moins fort`, `diminue le son`, `volume down`
  - Action: `pactl set-sink-volume @DEFAULT_SINK@ -10%`
  - Utilisations: 0

- **adv_audio_volume_up** [bash]
  - Description: Augmente le volume de 10 pourcent
  - Triggers: `monte le volume`, `plus fort`, `augmente le son`, `volume up`
  - Action: `pactl set-sink-volume @DEFAULT_SINK@ +10%`
  - Utilisations: 0


### advanced_docker (10 commandes)

- **adv_docker_disk_usage** [bash]
  - Description: Affiche l'espace disque utilise par Docker
  - Triggers: `espace docker`, `docker disk usage`, `taille docker`
  - Action: `docker system df`
  - Utilisations: 0

- **adv_docker_images** [bash]
  - Description: Liste les images Docker
  - Triggers: `images docker`, `docker images`, `liste les images`
  - Action: `docker images --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'`
  - Utilisations: 0

- **adv_docker_logs** [bash]
  - Description: Affiche les logs du dernier container
  - Triggers: `logs container`, `docker logs`, `logs du container`
  - Action: `docker logs --tail 50 $(docker ps -q | head -1) 2>/dev/null || echo 'Aucun container actif'`
  - Utilisations: 0

- **adv_docker_networks** [bash]
  - Description: Liste les reseaux Docker
  - Triggers: `réseaux docker`, `docker networks`, `networks docker`
  - Action: `docker network ls`
  - Utilisations: 0

- **adv_docker_prune** [bash]
  - Description: Nettoie les ressources Docker inutilisees
  - Triggers: `nettoie docker`, `docker prune`, `clean docker`
  - Action: `docker system prune -f`
  - Utilisations: 0

- **adv_docker_ps** [bash]
  - Description: Liste les containers actifs
  - Triggers: `containers actifs`, `docker ps`, `containers en cours`
  - Action: `docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'`
  - Utilisations: 0

- **adv_docker_ps_all** [bash]
  - Description: Liste tous les containers
  - Triggers: `tous les containers`, `docker ps all`, `tous les dockers`
  - Action: `docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'`
  - Utilisations: 0

- **adv_docker_restart** [bash]
  - Description: Redémarre tous les containers
  - Triggers: `restart container`, `redémarre les containers`, `docker restart all`
  - Action: `docker restart $(docker ps -q) 2>/dev/null && echo 'Containers redemarres' || echo 'Aucun container `
  - Utilisations: 0

- **adv_docker_stats** [bash]
  - Description: Affiche les statistiques des containers
  - Triggers: `stats docker`, `statistiques containers`, `docker stats`
  - Action: `docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}'`
  - Utilisations: 0

- **adv_docker_volumes** [bash]
  - Description: Liste les volumes Docker
  - Triggers: `volumes docker`, `docker volumes`, `stockage docker`
  - Action: `docker volume ls`
  - Utilisations: 0


### advanced_files (10 commandes)

- **adv_files_count_by_type** [bash]
  - Description: Compte les fichiers par extension
  - Triggers: `fichiers par type`, `compte les fichiers par extension`, `types de fichiers`
  - Action: `find /home/turbo -type f -not -path '*/\.*' 2>/dev/null | sed 's/.*\.//' | sort | uniq -c | sort -rn`
  - Utilisations: 0

- **adv_files_disk_by_folder** [bash]
  - Description: Affiche l'espace utilise par dossier
  - Triggers: `espace par dossier`, `taille des dossiers`, `espace disque par dossier`
  - Action: `du -sh /home/turbo/*/ 2>/dev/null | sort -h`
  - Utilisations: 0

- **adv_files_duplicates** [bash]
  - Description: Cherche les fichiers dupliques dans le dossier personnel
  - Triggers: `fichiers dupliqués`, `doublons`, `trouve les doublons`
  - Action: `fdupes -r /home/turbo/Documents 2>/dev/null | head -50 || echo 'Installez fdupes: sudo apt install f`
  - Utilisations: 0

- **adv_files_empty** [bash]
  - Description: Trouve les fichiers vides
  - Triggers: `fichiers vides`, `trouve les fichiers vides`, `empty files`
  - Action: `find /home/turbo -type f -empty -not -path '*/\.*' 2>/dev/null | head -30`
  - Utilisations: 0

- **adv_files_empty_dirs** [bash]
  - Description: Trouve les dossiers vides
  - Triggers: `dossiers vides`, `trouve les dossiers vides`, `répertoires vides`
  - Action: `find /home/turbo -type d -empty -not -path '*/\.*' 2>/dev/null | head -30`
  - Utilisations: 0

- **adv_files_find_large** [bash]
  - Description: Trouve les fichiers de plus de 100 Mo
  - Triggers: `trouve les gros fichiers`, `gros fichiers`, `fichiers volumineux`
  - Action: `find /home/turbo -type f -size +100M -exec ls -lh {} \; 2>/dev/null | sort -k5 -h | tail -20`
  - Utilisations: 0

- **adv_files_oldest** [bash]
  - Description: Trouve les fichiers les plus anciens
  - Triggers: `fichiers les plus anciens`, `vieux fichiers`, `oldest files`
  - Action: `find /home/turbo -type f -not -path '*/\.*' -printf '%T+ %p\n' 2>/dev/null | sort | head -20`
  - Utilisations: 0

- **adv_files_permissions** [bash]
  - Description: Trouve les fichiers avec permissions larges
  - Triggers: `fichiers avec permissions larges`, `fichiers world writable`, `permissions ouvertes`
  - Action: `find /home/turbo -type f -perm -o+w -not -path '*/\.*' 2>/dev/null | head -20`
  - Utilisations: 0

- **adv_files_recent** [bash]
  - Description: Liste les fichiers modifies dans les dernieres 24h
  - Triggers: `derniers fichiers modifiés`, `fichiers récents`, `fichiers modifiés aujourd'hui`
  - Action: `find /home/turbo -type f -mtime -1 -not -path '*/\.*' 2>/dev/null | head -30`
  - Utilisations: 0

- **adv_files_symlinks** [bash]
  - Description: Liste les liens symboliques
  - Triggers: `liens symboliques`, `symlinks`, `liste les liens`
  - Action: `find /home/turbo -type l -not -path '*/\.*' 2>/dev/null | head -30`
  - Utilisations: 0


### advanced_git (10 commandes)

- **adv_git_branches** [bash]
  - Description: Liste toutes les branches git
  - Triggers: `branches`, `branches git`, `liste les branches`
  - Action: `git branch -a`
  - Utilisations: 0

- **adv_git_diff_stat** [bash]
  - Description: Affiche un resume des changements
  - Triggers: `diff des changements`, `résumé git diff`, `git changes`
  - Action: `git diff --stat`
  - Utilisations: 0

- **adv_git_last_commit** [bash]
  - Description: Affiche le dernier commit
  - Triggers: `dernier commit`, `dernier git commit`, `last commit`
  - Action: `git log -1 --format='%h - %s (%an, %ar)'`
  - Utilisations: 0

- **adv_git_log_graph** [bash]
  - Description: Affiche l'historique git en graphe
  - Triggers: `historique git`, `graphe git`, `git log graphique`
  - Action: `git log --oneline --graph --all -20`
  - Utilisations: 0

- **adv_git_pull** [bash]
  - Description: Telecharge les derniers changements
  - Triggers: `pull le code`, `git pull`, `télécharge le code`
  - Action: `git pull`
  - Utilisations: 0

- **adv_git_remote** [bash]
  - Description: Affiche les depots distants configures
  - Triggers: `remotes git`, `dépôts distants`, `git remote`
  - Action: `git remote -v`
  - Utilisations: 0

- **adv_git_stash** [bash]
  - Description: Met de cote les changements en cours
  - Triggers: `stash le travail`, `git stash`, `mets de côté`
  - Action: `git stash`
  - Utilisations: 0

- **adv_git_stash_list** [bash]
  - Description: Liste les stashs enregistres
  - Triggers: `liste des stashs`, `stash list`, `stashs enregistrés`
  - Action: `git stash list`
  - Utilisations: 0

- **adv_git_stash_pop** [bash]
  - Description: Restaure le dernier stash
  - Triggers: `restaure le stash`, `stash pop`, `récupère le stash`
  - Action: `git stash pop`
  - Utilisations: 0

- **adv_git_status** [bash]
  - Description: Affiche l'etat du depot git
  - Triggers: `status git`, `état du dépôt`, `git status`
  - Action: `git status -sb`
  - Utilisations: 0


### advanced_jarvis (10 commandes)

- **adv_jarvis_commands_count** [bash]
  - Description: Compte les commandes vocales JARVIS
  - Triggers: `combien de commandes jarvis`, `nombre de commandes vocales`, `jarvis commands count`
  - Action: `sqlite3 /home/turbo/jarvis/data/jarvis.db "SELECT category, COUNT(*) FROM voice_commands GROUP BY ca`
  - Utilisations: 0

- **adv_jarvis_db_size** [bash]
  - Description: Affiche la taille de la base JARVIS
  - Triggers: `taille base jarvis`, `taille db jarvis`, `jarvis database size`
  - Action: `ls -lh /home/turbo/jarvis/data/jarvis.db && echo '---' && sqlite3 /home/turbo/jarvis/data/jarvis.db `
  - Utilisations: 0

- **adv_jarvis_disk_usage** [bash]
  - Description: Affiche l'espace disque utilise par JARVIS
  - Triggers: `espace jarvis`, `taille dossier jarvis`, `jarvis disk usage`
  - Action: `du -sh /home/turbo/jarvis/ && echo '---' && du -sh /home/turbo/jarvis/*/ 2>/dev/null | sort -h`
  - Utilisations: 0

- **adv_jarvis_errors** [bash]
  - Description: Affiche les erreurs recentes de JARVIS
  - Triggers: `erreurs jarvis`, `jarvis errors`, `problèmes jarvis`
  - Action: `journalctl --user -u 'jarvis-*' -p err -n 20 --no-pager 2>/dev/null || echo 'Aucune erreur recente'`
  - Utilisations: 0

- **adv_jarvis_logs** [bash]
  - Description: Affiche les 50 derniers logs JARVIS
  - Triggers: `logs jarvis récents`, `journal jarvis récent`, `jarvis logs`
  - Action: `journalctl --user -u 'jarvis-*' -n 50 --no-pager 2>/dev/null || echo 'Pas de logs JARVIS trouves'`
  - Utilisations: 0

- **adv_jarvis_memory** [bash]
  - Description: Affiche la memoire utilisee par JARVIS
  - Triggers: `mémoire jarvis`, `ram jarvis`, `jarvis memory usage`
  - Action: `ps aux | grep -i jarvis | grep -v grep | awk '{sum+=$6} END {printf "JARVIS utilise %.1f Mo de RAM\n`
  - Utilisations: 0

- **adv_jarvis_processes** [bash]
  - Description: Liste les processus JARVIS actifs
  - Triggers: `processus jarvis`, `jarvis processes`, `services jarvis actifs`
  - Action: `ps aux | grep -i jarvis | grep -v grep`
  - Utilisations: 0

- **adv_jarvis_restart** [bash]
  - Description: Redemarre tous les services JARVIS
  - Triggers: `redémarre jarvis`, `restart jarvis`, `relance jarvis`
  - Action: `systemctl --user restart jarvis-full.target 2>/dev/null && echo 'JARVIS redémarre' || echo 'Target j`
  - Utilisations: 0

- **adv_jarvis_status** [bash]
  - Description: Affiche l'etat de tous les services JARVIS
  - Triggers: `status jarvis`, `état de jarvis`, `jarvis status`
  - Action: `systemctl --user status jarvis-* --no-pager 2>/dev/null | grep -E '(●|Active:|jarvis)' || echo 'Serv`
  - Utilisations: 0

- **adv_jarvis_version** [bash]
  - Description: Affiche la version de JARVIS
  - Triggers: `version jarvis`, `jarvis version`, `quelle version de jarvis`
  - Action: `head -5 /home/turbo/jarvis/CLAUDE.md 2>/dev/null || echo 'Fichier version non trouve'`
  - Utilisations: 0


### advanced_network (10 commandes)

- **adv_net_active_connections** [bash]
  - Description: Liste les connexions reseau actives
  - Triggers: `connexions actives`, `connexions réseau`, `active connections`
  - Action: `ss -tn state established`
  - Utilisations: 0

- **adv_net_bandwidth** [bash]
  - Description: Affiche la bande passante par processus
  - Triggers: `bande passante`, `bandwidth`, `consommation réseau`, `utilisation réseau`
  - Action: `sudo nethogs -t -c 3 2>/dev/null || sudo iftop -t -s 3 2>/dev/null || echo 'Installez nethogs: sudo `
  - Utilisations: 0

- **adv_net_dns_lookup** [bash]
  - Description: Effectue une resolution DNS
  - Triggers: `dns lookup`, `résolution dns`, `dig`, `nslookup`
  - Action: `dig google.com +short && echo '---' && cat /etc/resolv.conf | grep nameserver`
  - Utilisations: 0

- **adv_net_local_ip** [bash]
  - Description: Affiche les adresses IP locales
  - Triggers: `ip locale`, `mon ip locale`, `adresse ip locale`, `local ip`
  - Action: `ip -4 addr show | grep inet | grep -v 127.0.0.1 | awk '{print $NF": "$2}'`
  - Utilisations: 0

- **adv_net_ping_google** [bash]
  - Description: Teste la connectivite avec Google
  - Triggers: `ping google`, `teste la connexion`, `test internet`, `ping`
  - Action: `ping -c 4 8.8.8.8`
  - Utilisations: 0

- **adv_net_public_ip** [bash]
  - Description: Affiche l'adresse IP publique
  - Triggers: `ip publique`, `mon ip publique`, `adresse ip publique`, `public ip`
  - Action: `curl -s ifconfig.me && echo ''`
  - Utilisations: 0

- **adv_net_route_table** [bash]
  - Description: Affiche la table de routage
  - Triggers: `table de routage`, `routes réseau`, `routing table`
  - Action: `ip route show`
  - Utilisations: 0

- **adv_net_speed_test** [bash]
  - Description: Teste la vitesse de connexion internet
  - Triggers: `test de vitesse`, `speed test`, `vitesse internet`, `speedtest`
  - Action: `speedtest-cli --simple 2>/dev/null || echo 'Installez speedtest-cli: sudo apt install speedtest-cli'`
  - Utilisations: 0

- **adv_net_who_connected** [bash]
  - Description: Affiche qui est connecte au systeme
  - Triggers: `qui est connecté`, `utilisateurs connectés au système`, `who is logged in`
  - Action: `w`
  - Utilisations: 0

- **adv_net_wifi_info** [bash]
  - Description: Affiche les infos WiFi
  - Triggers: `info wifi`, `état wifi`, `wifi status`, `réseau wifi`
  - Action: `nmcli dev wifi list 2>/dev/null || iwconfig 2>/dev/null | grep -v 'no wireless'`
  - Utilisations: 0


### advanced_security (10 commandes)

- **adv_sec_audit_users** [bash]
  - Description: Liste les utilisateurs avec shell de connexion
  - Triggers: `audit utilisateurs`, `utilisateurs système`, `comptes utilisateurs`
  - Action: `awk -F: '$7 !~ /(nologin|false|sync|halt|shutdown)/' /etc/passwd`
  - Utilisations: 0

- **adv_sec_check_rootkits** [bash]
  - Description: Lance une verification anti-rootkit rapide
  - Triggers: `scan rootkit`, `cherche les rootkits`, `check rootkit`
  - Action: `sudo chkrootkit -q 2>/dev/null || echo 'Installez chkrootkit: sudo apt install chkrootkit'`
  - Utilisations: 0

- **adv_sec_failed_logins** [bash]
  - Description: Affiche les tentatives de connexion echouees
  - Triggers: `tentatives échouées`, `failed logins`, `connexions échouées`
  - Action: `sudo lastb -10 2>/dev/null || echo 'Acces refuse ou lastb non disponible'`
  - Utilisations: 0

- **adv_sec_last_logins** [bash]
  - Description: Affiche les 10 dernieres connexions
  - Triggers: `dernières connexions`, `last logins`, `qui s'est connecté`
  - Action: `last -10`
  - Utilisations: 0

- **adv_sec_logged_users** [bash]
  - Description: Affiche les utilisateurs actuellement connectes
  - Triggers: `utilisateurs connectés`, `who`, `qui est connecté maintenant`
  - Action: `who -u`
  - Utilisations: 0

- **adv_sec_open_ports** [bash]
  - Description: Liste les ports ouverts avec les processus
  - Triggers: `ports ouverts détaillés`, `ports et processus`, `listening ports`
  - Action: `sudo ss -tlnp | column -t`
  - Utilisations: 0

- **adv_sec_password_policy** [bash]
  - Description: Affiche la politique de mots de passe
  - Triggers: `politique mots de passe`, `password policy`, `règles mots de passe`
  - Action: `sudo chage -l turbo`
  - Utilisations: 0

- **adv_sec_ssh_keys** [bash]
  - Description: Liste les cles SSH configurees
  - Triggers: `clés ssh`, `ssh keys`, `liste les clés ssh`
  - Action: `ls -la ~/.ssh/ 2>/dev/null || echo 'Aucun dossier .ssh'`
  - Utilisations: 0

- **adv_sec_sudo_log** [bash]
  - Description: Affiche les dernieres commandes sudo
  - Triggers: `historique sudo`, `commandes sudo`, `sudo log`
  - Action: `sudo journalctl _COMM=sudo -n 20 --no-pager`
  - Utilisations: 0

- **adv_sec_suid_files** [bash]
  - Description: Trouve les fichiers avec permissions SUID
  - Triggers: `permissions sensibles`, `fichiers suid`, `fichiers setuid`
  - Action: `find /usr -perm -4000 -type f 2>/dev/null | head -20`
  - Utilisations: 0


### advanced_system (10 commandes)

- **adv_sys_battery** [bash]
  - Description: Affiche les infos batterie/alimentation
  - Triggers: `info batterie`, `état batterie`, `batterie`, `alimentation`
  - Action: `upower -i $(upower -e | grep battery) 2>/dev/null || echo 'Pas de batterie detectee (desktop)'`
  - Utilisations: 0

- **adv_sys_cpu_load** [bash]
  - Description: Affiche la charge CPU detaillee
  - Triggers: `charge cpu`, `charge processeur`, `cpu load`, `utilisation cpu`
  - Action: `mpstat -P ALL 1 1 2>/dev/null || top -bn1 | head -5`
  - Utilisations: 0

- **adv_sys_disk_io** [bash]
  - Description: Affiche les statistiques IO disque
  - Triggers: `io disque`, `activité disque`, `disk io`, `lecture écriture disque`
  - Action: `iostat -x 1 1 2>/dev/null || echo 'Installez sysstat: sudo apt install sysstat'`
  - Utilisations: 0

- **adv_sys_gpu_status** [bash]
  - Description: Affiche l'etat des GPU NVIDIA
  - Triggers: `état gpu`, `gpu status`, `nvidia status`, `utilisation gpu`
  - Action: `nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,no`
  - Utilisations: 0

- **adv_sys_kernel** [bash]
  - Description: Affiche la version du kernel Linux
  - Triggers: `version du kernel`, `kernel version`, `version noyau`, `quel kernel`
  - Action: `uname -r && uname -v`
  - Utilisations: 0

- **adv_sys_proc_by_cpu** [bash]
  - Description: Liste les processus tries par CPU
  - Triggers: `processus par cpu`, `top cpu`, `processus gourmands en cpu`
  - Action: `ps aux --sort=-%cpu | head -15`
  - Utilisations: 0

- **adv_sys_proc_by_mem** [bash]
  - Description: Liste les processus tries par memoire
  - Triggers: `processus par mémoire`, `top mémoire`, `processus gourmands en ram`
  - Action: `ps aux --sort=-%mem | head -15`
  - Utilisations: 0

- **adv_sys_services_failed** [bash]
  - Description: Affiche les services systemd en echec
  - Triggers: `services en échec`, `services failed`, `services en erreur`
  - Action: `systemctl --failed`
  - Utilisations: 0

- **adv_sys_temperatures** [bash]
  - Description: Affiche toutes les temperatures du systeme
  - Triggers: `températures`, `temperatures`, `température système`, `sensors`
  - Action: `sensors 2>/dev/null || echo 'Installez lm-sensors: sudo apt install lm-sensors'`
  - Utilisations: 0

- **adv_sys_uptime** [bash]
  - Description: Affiche le temps de fonctionnement du systeme
  - Triggers: `uptime`, `temps de fonctionnement`, `depuis quand le pc tourne`
  - Action: `uptime -p && echo 'Boot: ' && uptime -s`
  - Utilisations: 0


### advanced_windows (10 commandes)

- **adv_win_always_on_top** [bash]
  - Description: Garde la fenetre active toujours au premier plan
  - Triggers: `fenêtre toujours devant`, `always on top`, `premier plan`
  - Action: `wmctrl -r :ACTIVE: -b toggle,above`
  - Utilisations: 0

- **adv_win_close_all** [bash]
  - Description: Ferme toutes les fenetres ouvertes
  - Triggers: `ferme toutes les fenêtres`, `ferme tout`, `close all windows`
  - Action: `wmctrl -l | awk '{print $1}' | xargs -I{} wmctrl -ic {}`
  - Utilisations: 0

- **adv_win_fullscreen** [bash]
  - Description: Met la fenetre active en plein ecran
  - Triggers: `fenêtre plein écran`, `plein écran`, `fullscreen`, `maximise la fenêtre`
  - Action: `wmctrl -r :ACTIVE: -b add,maximized_vert,maximized_horz`
  - Utilisations: 0

- **adv_win_list_all** [bash]
  - Description: Liste toutes les fenetres ouvertes
  - Triggers: `liste les fenêtres`, `fenêtres ouvertes`, `list windows`
  - Action: `wmctrl -l`
  - Utilisations: 0

- **adv_win_minimize** [bash]
  - Description: Minimise la fenetre active
  - Triggers: `minimise la fenêtre`, `réduis la fenêtre`, `minimize`
  - Action: `xdotool getactivewindow windowminimize`
  - Utilisations: 0

- **adv_win_move_center** [bash]
  - Description: Centre la fenetre active sur l'ecran
  - Triggers: `centre la fenêtre`, `fenêtre au centre`, `center window`
  - Action: `wmctrl -r :ACTIVE: -e 0,$(xdpyinfo | grep dimensions | awk '{print $2}' | cut -dx -f1 | awk '{print `
  - Utilisations: 0

- **adv_win_restore** [bash]
  - Description: Restaure la fenetre active a sa taille normale
  - Triggers: `restaure la fenêtre`, `taille normale`, `unmaximize`
  - Action: `wmctrl -r :ACTIVE: -b remove,maximized_vert,maximized_horz`
  - Utilisations: 0

- **adv_win_snap_left** [bash]
  - Description: Place la fenetre active a gauche de l'ecran
  - Triggers: `mets cette fenêtre à gauche`, `fenêtre à gauche`, `snap gauche`
  - Action: `wmctrl -r :ACTIVE: -e 0,0,0,$(xdpyinfo | grep dimensions | awk '{print $2}' | cut -dx -f1 | awk '{pr`
  - Utilisations: 0

- **adv_win_snap_right** [bash]
  - Description: Place la fenetre active a droite de l'ecran
  - Triggers: `mets cette fenêtre à droite`, `fenêtre à droite`, `snap droite`
  - Action: `wmctrl -r :ACTIVE: -e 0,$(xdpyinfo | grep dimensions | awk '{print $2}' | cut -dx -f1 | awk '{print `
  - Utilisations: 0

- **adv_win_tile_mosaic** [bash]
  - Description: Arrange toutes les fenetres en mosaique
  - Triggers: `toutes les fenêtres en mosaïque`, `mosaïque`, `tile windows`
  - Action: `wmctrl -l | awk '{print $1}' | while read wid; do wmctrl -ir $wid -b remove,maximized_vert,maximized`
  - Utilisations: 0


### legacy (10 commandes)

- **affiche le dashboard** [bash]
  - Description: Legacy command affiche le dashboard
  - Triggers: `affiche le dashboard`
  - Action: `xdg-open http://localhost:8080`
  - Utilisations: 0

- **capture écran** [bash]
  - Description: Legacy command capture écran
  - Triggers: `capture écran`
  - Action: `gnome-screenshot`
  - Utilisations: 0

- **lance claude** [bash]
  - Description: Legacy command lance claude
  - Triggers: `lance claude`
  - Action: `cd /home/turbo/jarvis && claude`
  - Utilisations: 0

- **nettoie le système** [bash]
  - Description: Legacy command nettoie le système
  - Triggers: `nettoie le système`
  - Action: `sudo apt autoremove -y`
  - Utilisations: 0

- **ouvre le terminal** [bash]
  - Description: Legacy command ouvre le terminal
  - Triggers: `ouvre le terminal`
  - Action: `gnome-terminal`
  - Utilisations: 0

- **redémarre jarvis** [bash]
  - Description: Legacy command redémarre jarvis
  - Triggers: `redémarre jarvis`
  - Action: `systemctl --user restart jarvis-*`
  - Utilisations: 0

- **statut du cluster** [bash]
  - Description: Legacy command statut du cluster
  - Triggers: `statut du cluster`
  - Action: `/home/turbo/jarvis/jarvis-ctl.sh health`
  - Utilisations: 0

- **température gpu** [bash]
  - Description: Legacy command température gpu
  - Triggers: `température gpu`
  - Action: `nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader`
  - Utilisations: 0

- **usage mémoire** [bash]
  - Description: Legacy command usage mémoire
  - Triggers: `usage mémoire`
  - Action: `free -h`
  - Utilisations: 0

- **vérifie les agents** [bash]
  - Description: Legacy command vérifie les agents
  - Triggers: `vérifie les agents`
  - Action: `curl -s http://127.0.0.1:18789/health`
  - Utilisations: 0


### linux (15 commandes)

- **ask_ia** [bash]
  - Description: 
  - Triggers: `demande a l ia`, `question ia`
  - Action: `linux_ask_ia`
  - Utilisations: 0

- **bluetooth_connect** [bash]
  - Description: 
  - Triggers: `connecte le casque`, `connecte le bluetooth`
  - Action: `linux_bluetooth_connect`
  - Utilisations: 0

- **cpu_usage** [bash]
  - Description: 
  - Triggers: `usage cpu`, `charge cpu`, `processeur`
  - Action: `linux_cpu_usage`
  - Utilisations: 0

- **dark_mode** [bash]
  - Description: 
  - Triggers: `mode sombre`, `dark mode`
  - Action: `gsettings set org.gnome.desktop.interface color-scheme prefer-dark`
  - Utilisations: 0

- **datetime** [bash]
  - Description: 
  - Triggers: `quelle heure`, `quelle date`
  - Action: `linux_datetime`
  - Utilisations: 0

- **ferme_fenetre** [bash]
  - Description: 
  - Triggers: `ferme la fenetre`, `alt f4`, `quitte`
  - Action: `linux_close_app`
  - Utilisations: 0

- **gpu_info** [bash]
  - Description: 
  - Triggers: `info gpu`, `temperature gpu`, `carte graphique`
  - Action: `linux_gpu_info`
  - Utilisations: 0

- **lock** [bash]
  - Description: 
  - Triggers: `verrouille`, `lock`
  - Action: `loginctl lock-session`
  - Utilisations: 0

- **mute** [bash]
  - Description: 
  - Triggers: `coupe le son`, `mute`, `silence`
  - Action: `pactl set-sink-mute @DEFAULT_SINK@ toggle`
  - Utilisations: 0

- **ouvre_app** [bash]
  - Description: 
  - Triggers: `ouvre`, `lance`, `demarre`
  - Action: `linux_open_app`
  - Utilisations: 0

- **ram_usage** [bash]
  - Description: 
  - Triggers: `usage memoire`, `ram`, `combien de ram`
  - Action: `linux_memory_usage`
  - Utilisations: 0

- **screenshot** [bash]
  - Description: 
  - Triggers: `capture ecran`, `screenshot`
  - Action: `scrot ~/Pictures/Screenshots/screen_$(date +%s).png`
  - Utilisations: 0

- **services** [bash]
  - Description: 
  - Triggers: `services jarvis`, `liste les services`
  - Action: `linux_services_list`
  - Utilisations: 0

- **volume_down** [bash]
  - Description: 
  - Triggers: `baisse le volume`, `moins fort`, `volume moins`
  - Action: `pactl set-sink-volume @DEFAULT_SINK@ -5%`
  - Utilisations: 0

- **volume_up** [bash]
  - Description: 
  - Triggers: `monte le volume`, `plus fort`, `volume plus`
  - Action: `pactl set-sink-volume @DEFAULT_SINK@ +5%`
  - Utilisations: 0


### linux_config (5 commandes)

- **linux_config_taille_texte** [bash]
  - Description: Affiche le facteur de mise a l'echelle du texte
  - Triggers: `taille du texte`, `échelle du texte`, `scaling texte`
  - Action: `gsettings get org.gnome.desktop.interface text-scaling-factor`
  - Utilisations: 0

- **linux_config_theme_clair** [bash]
  - Description: Active le theme clair GNOME
  - Triggers: `thème clair`, `theme clair`, `mode clair`, `light mode`
  - Action: `gsettings set org.gnome.desktop.interface color-scheme prefer-light`
  - Utilisations: 0

- **linux_config_theme_sombre** [bash]
  - Description: Active le theme sombre GNOME
  - Triggers: `thème sombre`, `theme sombre`, `mode sombre`, `dark mode`
  - Action: `gsettings set org.gnome.desktop.interface color-scheme prefer-dark`
  - Utilisations: 0

- **linux_config_veilleuse_off** [bash]
  - Description: Desactive la veilleuse
  - Triggers: `désactive la veilleuse`, `desactive la veilleuse`, `veilleuse off`
  - Action: `gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled false`
  - Utilisations: 0

- **linux_config_veilleuse_on** [bash]
  - Description: Active la veilleuse (filtre bleu)
  - Triggers: `active la veilleuse`, `veilleuse on`, `filtre bleu`
  - Action: `gsettings set org.gnome.settings-daemon.plugins.color night-light-enabled true`
  - Utilisations: 0


### linux_journal (5 commandes)

- **linux_journal_cherche_logs** [bash]
  - Description: Cherche un terme dans les logs systeme
  - Triggers: `cherche dans les logs {terme}`, `recherche dans les logs {terme}`
  - Action: `journalctl --grep={terme}`
  - Utilisations: 0

- **linux_journal_erreurs_recentes** [bash]
  - Description: Affiche les erreurs de la derniere heure
  - Triggers: `erreurs récentes`, `erreurs recentes`, `erreurs système récentes`
  - Action: `journalctl -p err --since "1 hour ago"`
  - Utilisations: 0

- **linux_journal_logs_boot** [bash]
  - Description: Affiche les logs du demarrage actuel
  - Triggers: `logs du boot`, `logs de démarrage`, `journal du boot`
  - Action: `journalctl -b`
  - Utilisations: 0

- **linux_journal_logs_jarvis** [bash]
  - Description: Affiche les logs du service JARVIS
  - Triggers: `logs du service jarvis`, `logs jarvis`, `journal jarvis`
  - Action: `journalctl --user -u jarvis-* -n 30`
  - Utilisations: 0

- **linux_journal_logs_systeme** [bash]
  - Description: Affiche les 50 derniers logs systeme
  - Triggers: `montre les logs système`, `logs système`, `montre les logs systeme`
  - Action: `journalctl -n 50`
  - Utilisations: 0


### linux_packages (5 commandes)

- **linux_pkg_cherche_paquet** [bash]
  - Description: Recherche un paquet dans les depots
  - Triggers: `cherche le paquet {nom}`, `recherche le paquet {nom}`
  - Action: `apt search {nom}`
  - Utilisations: 0

- **linux_pkg_installe** [bash]
  - Description: Installe un paquet via apt
  - Triggers: `installe {paquet}`, `installe le paquet {paquet}`
  - Action: `sudo apt install -y {paquet}`
  - Utilisations: 0

- **linux_pkg_liste_paquets** [bash]
  - Description: Compte les paquets installes
  - Triggers: `liste les paquets installés`, `nombre de paquets`, `paquets installés`
  - Action: `dpkg --get-selections | wc -l`
  - Utilisations: 0

- **linux_pkg_snap_liste** [bash]
  - Description: Liste les paquets snap installes
  - Triggers: `paquets snap installés`, `liste des snaps`, `snap list`
  - Action: `snap list`
  - Utilisations: 0

- **linux_pkg_supprime** [bash]
  - Description: Supprime un paquet via apt
  - Triggers: `supprime {paquet}`, `supprime le paquet {paquet}`, `désinstalle {paquet}`
  - Action: `sudo apt remove {paquet}`
  - Utilisations: 0


### linux_power (5 commandes)

- **linux_power_economie** [bash]
  - Description: Active le mode economie d'energie
  - Triggers: `mode économie`, `mode economie`, `économie d'énergie`, `power saver`
  - Action: `powerprofilesctl set power-saver`
  - Utilisations: 0

- **linux_power_performance** [bash]
  - Description: Active le mode performance
  - Triggers: `mode performance`, `active le mode performance`, `performance maximale`
  - Action: `powerprofilesctl set performance`
  - Utilisations: 0

- **linux_power_profil** [bash]
  - Description: Affiche le profil d'energie actuel
  - Triggers: `profil d'énergie`, `profil d'energie`, `profil énergétique`
  - Action: `powerprofilesctl get`
  - Utilisations: 0

- **linux_power_temperature** [bash]
  - Description: Affiche la temperature du processeur
  - Triggers: `température processeur`, `temperature processeur`, `température cpu`, `temp cpu`
  - Action: `sensors | grep Core`
  - Utilisations: 0

- **linux_power_ventilateurs** [bash]
  - Description: Affiche l'etat des ventilateurs
  - Triggers: `état des ventilateurs`, `etat des ventilateurs`, `vitesse ventilateurs`
  - Action: `sensors | grep -i fan`
  - Utilisations: 0


### linux_security (5 commandes)

- **linux_sec_apparmor** [bash]
  - Description: Affiche l'etat des profils AppArmor
  - Triggers: `état apparmor`, `etat apparmor`, `statut apparmor`
  - Action: `sudo aa-status`
  - Utilisations: 0

- **linux_sec_parefeu** [bash]
  - Description: Affiche l'etat du pare-feu UFW
  - Triggers: `état du pare-feu`, `etat du pare-feu`, `statut ufw`, `firewall status`
  - Action: `sudo ufw status verbose`
  - Utilisations: 0

- **linux_sec_ports_ouverts** [bash]
  - Description: Liste les ports ouverts en ecoute
  - Triggers: `ports ouverts`, `ports en écoute`, `ports en ecoute`
  - Action: `ss -tlnp`
  - Utilisations: 0

- **linux_sec_scan_antivirus** [bash]
  - Description: Lance un scan antivirus ClamAV
  - Triggers: `scan antivirus`, `lance un scan`, `clamscan`
  - Action: `clamscan --recursive /home/turbo`
  - Utilisations: 0

- **linux_sec_tentatives_connexion** [bash]
  - Description: Affiche les tentatives de connexion bloquees
  - Triggers: `tentatives de connexion`, `fail2ban status`, `connexions bloquées`
  - Action: `sudo fail2ban-client status`
  - Utilisations: 0


### linux_share (5 commandes)

- **linux_share_deconnecte** [bash]
  - Description: Demonte les partages CIFS et NFS
  - Triggers: `déconnecte les partages`, `deconnecte les partages`, `unmount shares`
  - Action: `umount -t cifs,nfs -a 2>/dev/null && echo 'Partages deconnectes' || echo 'Aucun partage a deconnecte`
  - Utilisations: 0

- **linux_share_liste** [bash]
  - Description: Liste les partages reseau Samba
  - Triggers: `partages réseau`, `partages reseau`, `samba shares`, `network shares`
  - Action: `net usershare list`
  - Utilisations: 0

- **linux_share_monte_info** [bash]
  - Description: Info sur le montage de partage SMB
  - Triggers: `monte un partage`, `monter un partage`, `mount share`
  - Action: `echo 'Utilisez: smbclient //SERVEUR/PARTAGE -U utilisateur pour se connecter a un partage SMB'`
  - Utilisations: 0

- **linux_share_nfs** [bash]
  - Description: Liste les exports NFS locaux
  - Triggers: `partages NFS`, `partages nfs`, `exports nfs`, `nfs shares`
  - Action: `showmount -e 127.0.0.1`
  - Utilisations: 0

- **linux_share_ssh_actives** [bash]
  - Description: Affiche les connexions SSH actives
  - Triggers: `connexions SSH actives`, `connexions ssh actives`, `ssh connections`
  - Action: `ss -tn state established | grep :22`
  - Utilisations: 0


### linux_snapshots (5 commandes)

- **linux_snap_cree** [bash]
  - Description: Cree un snapshot systeme via timeshift
  - Triggers: `crée un snapshot`, `cree un snapshot`, `nouveau snapshot`
  - Action: `sudo timeshift --create --comments 'Snapshot JARVIS' --yes`
  - Utilisations: 0

- **linux_snap_espace** [bash]
  - Description: Affiche l'espace utilise par les volumes logiques
  - Triggers: `espace snapshots`, `espace lvm`, `taille snapshots`
  - Action: `sudo lvs 2>/dev/null || echo 'LVM non configure - Utilisation de timeshift' && sudo timeshift --list`
  - Utilisations: 0

- **linux_snap_liste** [bash]
  - Description: Liste les snapshots disponibles
  - Triggers: `liste les snapshots`, `snapshots disponibles`, `timeshift list`
  - Action: `sudo timeshift --list`
  - Utilisations: 0

- **linux_snap_restaure_info** [bash]
  - Description: Info sur la restauration de snapshot
  - Triggers: `restaure un snapshot`, `restore snapshot`
  - Action: `echo 'ATTENTION: La restauration necessite une confirmation manuelle. Utilisez: sudo timeshift --res`
  - Utilisations: 0

- **linux_snap_supprime_vieux** [bash]
  - Description: Supprime les anciens snapshots
  - Triggers: `supprime les vieux snapshots`, `nettoie les snapshots`, `delete old snapshots`
  - Action: `sudo timeshift --delete`
  - Utilisations: 0


### linux_swap (5 commandes)

- **linux_swap_etat** [bash]
  - Description: Affiche l'etat du swap
  - Triggers: `état du swap`, `etat du swap`, `swap status`
  - Action: `swapon --show`
  - Utilisations: 0

- **linux_swap_memoire_detail** [bash]
  - Description: Affiche les details de la memoire
  - Triggers: `utilisation mémoire détaillée`, `utilisation memoire detaillee`, `meminfo`
  - Action: `head -20 /proc/meminfo`
  - Utilisations: 0

- **linux_swap_memoire_dispo** [bash]
  - Description: Affiche la memoire disponible
  - Triggers: `mémoire disponible`, `memoire disponible`, `free memory`, `ram disponible`
  - Action: `free -h`
  - Utilisations: 0

- **linux_swap_vide** [bash]
  - Description: Vide et reactive le swap
  - Triggers: `vide le swap`, `flush swap`, `reset swap`
  - Action: `sudo swapoff -a && sudo swapon -a`
  - Utilisations: 0

- **linux_swap_zram** [bash]
  - Description: Affiche l'etat du zram
  - Triggers: `état zram`, `etat zram`, `zram status`
  - Action: `zramctl`
  - Utilisations: 0


### linux_trash (5 commandes)

- **linux_trash_contenu** [bash]
  - Description: Liste le contenu de la corbeille
  - Triggers: `contenu corbeille`, `liste corbeille`, `trash list`
  - Action: `gio trash --list`
  - Utilisations: 0

- **linux_trash_fichiers_temp** [bash]
  - Description: Supprime les fichiers temporaires JARVIS
  - Triggers: `supprime les fichiers temporaires`, `clean temp`, `nettoie les temporaires`
  - Action: `rm -rf /tmp/jarvis-* && echo 'Fichiers temporaires supprimes'`
  - Utilisations: 0

- **linux_trash_restaure_info** [bash]
  - Description: Infos sur la restauration depuis la corbeille
  - Triggers: `restaure depuis la corbeille`, `restaurer corbeille`
  - Action: `echo 'Utilisez: gio trash --restore FICHIER pour restaurer un element. Listez avec: gio trash --list`
  - Utilisations: 0

- **linux_trash_taille** [bash]
  - Description: Affiche la taille de la corbeille
  - Triggers: `taille de la corbeille`, `poids corbeille`, `trash size`
  - Action: `du -sh ~/.local/share/Trash/ 2>/dev/null || echo 'Corbeille vide'`
  - Utilisations: 0

- **linux_trash_vide** [bash]
  - Description: Vide la corbeille
  - Triggers: `vide la corbeille`, `corbeille vide`, `empty trash`
  - Action: `gio trash --empty`
  - Utilisations: 0


### linux_updates (5 commandes)

- **linux_update_disponibles** [bash]
  - Description: Liste les mises a jour disponibles
  - Triggers: `mises à jour disponibles`, `mises a jour disponibles`, `updates disponibles`
  - Action: `apt list --upgradable`
  - Utilisations: 0

- **linux_update_historique** [bash]
  - Description: Affiche l'historique des mises a jour
  - Triggers: `historique des mises à jour`, `historique des mises a jour`, `historique updates`
  - Action: `tail -50 /var/log/dpkg.log`
  - Utilisations: 0

- **linux_update_reboot_requis** [bash]
  - Description: Verifie si un redemarrage est necessaire
  - Triggers: `redémarre si nécessaire`, `reboot nécessaire`, `redémarrage requis`
  - Action: `cat /var/run/reboot-required 2>/dev/null || echo 'Aucun redemarrage requis'`
  - Utilisations: 0

- **linux_update_snaps** [bash]
  - Description: Met a jour les paquets snap
  - Triggers: `mets à jour les snaps`, `mets a jour les snaps`, `snap refresh`
  - Action: `sudo snap refresh`
  - Utilisations: 0

- **linux_update_systeme** [bash]
  - Description: Met a jour le systeme complet
  - Triggers: `mets à jour le système`, `mets a jour le systeme`, `update système`
  - Action: `sudo apt update && sudo apt upgrade -y`
  - Utilisations: 0


### linux_workspace (5 commandes)

- **linux_ws_deplace_fenetre** [bash]
  - Description: Deplace la fenetre active au bureau 2
  - Triggers: `déplace fenêtre au bureau 2`, `deplace fenetre au bureau 2`, `move window to desktop 2`
  - Action: `wmctrl -r :ACTIVE: -t 1`
  - Utilisations: 0

- **linux_ws_liste** [bash]
  - Description: Liste les bureaux virtuels
  - Triggers: `liste les bureaux`, `bureaux virtuels`, `workspaces`
  - Action: `wmctrl -d`
  - Utilisations: 0

- **linux_ws_nombre** [bash]
  - Description: Affiche le nombre de bureaux virtuels
  - Triggers: `nombre de bureaux`, `combien de bureaux`, `workspaces count`
  - Action: `gsettings get org.gnome.desktop.wm.preferences num-workspaces`
  - Utilisations: 0

- **linux_ws_precedent** [bash]
  - Description: Passe au bureau virtuel precedent
  - Triggers: `bureau précédent`, `bureau precedent`, `workspace précédent`, `previous desktop`
  - Action: `wmctrl -s $(expr $(wmctrl -d | grep '*' | cut -d' ' -f1) - 1)`
  - Utilisations: 0

- **linux_ws_suivant** [bash]
  - Description: Passe au bureau virtuel suivant
  - Triggers: `bureau suivant`, `workspace suivant`, `next desktop`
  - Action: `wmctrl -s $(expr $(wmctrl -d | grep '*' | cut -d' ' -f1) + 1)`
  - Utilisations: 0


---

## Skills

### accessibilite (1 skills)

- **mode_accessibilite_complet**
  - Description: Mode accessibilite complet: loupe + narrateur + contraste + clavier virtuel
  - Triggers: `mode accessibilite complet`, `accessibilite totale`, `active toute l'accessibilite`, `j'ai besoin d'aide visuelle`
  - Etapes:
    1. `bash_run` — Clavier virtuel
    1. `press_hotkey` — Loupe
    1. `notify` — Notification
  - Taux succes: 100%


### backup (2 skills)

- **backup_jarvis_linux**
  - Description: Backup complet JARVIS: bases de données, configs, scripts, git bundle
  - Triggers: `backup jarvis`, `sauvegarde jarvis`, `backup complet`, `fais un backup`, `sauvegarde tout`
  - Etapes:
    1. `bash` — Crée dossier backup du jour
    1. `bash` — Backup toutes les bases SQLite
    1. `bash` — Backup skills
    1. `bash` — Git bundle complet
    1. `bash` — Taille du backup
  - Taux succes: 100%

- **backup_complet_linux**
  - Description: Backup complet Linux: snapshot LVM, dump DBs, tar configs, sync backup, verification checksums
  - Triggers: `backup complet`, `backup complet linux`, `sauvegarde complete`, `fais un backup`, `sauvegarde tout`, `backup full linux`, `lance le backup`
  - Etapes:
    1. `bash_run` — Snapshot LVM du systeme
    1. `bash_run` — Dump des bases de donnees
    1. `bash_run` — Archivage des configurations
    1. `bash_run` — Synchronisation vers repertoire backup
    1. `bash_run` — Verification des checksums
  - Taux succes: 100%


### cluster (2 skills)

- **cluster_check_linux**
  - Description: Vérification complète du cluster JARVIS: M1, M2, M3, OL1, latences, modèles
  - Triggers: `vérifie le cluster`, `état du cluster`, `cluster check`, `teste les noeuds`, `santé du cluster`
  - Etapes:
    1. `bash` — Check M1
    1. `bash` — Check M2
    1. `bash` — Check M3
    1. `bash` — Check OL1
    1. `bash` — Test latences
  - Taux succes: 100%

- **model_manager_linux**
  - Description: Gestion modèles IA: lister, charger, décharger, benchmark modèles sur cluster
  - Triggers: `gère les modèles`, `modèles disponibles`, `charge un modèle`, `décharge le modèle`, `modèles ia`, `quel modèle tourne`
  - Etapes:
    1. `bash` — Modèles M1
    1. `bash` — Modèles OL1
    1. `bash` — Utilisation VRAM
  - Taux succes: 100%


### communication (2 skills)

- **mode_reunion**
  - Description: Mode reunion: ouvre Teams/Zoom, coupe micro, check camera, volume bas
  - Triggers: `mode reunion`, `lance la reunion`, `session visio`, `mode visio`, `visioconference`, `mode meeting`
  - Etapes:
    1. `app_open` — Ouvrir Teams
    1. `volume_down` — Baisser le volume
    1. `volume_down` — Baisser encore
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_communication**
  - Description: Mode communication: ouvre Discord, Telegram, Gmail
  - Triggers: `mode communication`, `ouvre les messageries`, `mode social`, `lance les messageries`, `session communication`
  - Etapes:
    1. `app_open` — Ouvrir Discord
    1. `app_open` — Ouvrir Telegram
    1. `open_url` — Ouvrir Gmail
    1. `notify` — Notification
  - Taux succes: 100%


### desktop (6 skills)

- **desktop_reset_linux**
  - Description: Reset bureau GNOME: restart shell, extensions, thème, résolution
  - Triggers: `reset le bureau`, `bureau planté`, `gnome planté`, `écran figé`, `redémarre gnome`, `desktop reset`
  - Etapes:
    1. `bash` — Restart GNOME Shell
    1. `bash` — Extensions actives
    1. `bash` — Thème et résolution
  - Taux succes: 100%

- **screenshot_ocr_linux**
  - Description: Capture écran avec OCR: screenshot, extraction texte, description IA
  - Triggers: `capture l'écran`, `screenshot`, `fais une capture`, `lis l'écran`, `texte à l'écran`, `ocr écran`
  - Etapes:
    1. `bash` — Capture écran
    1. `bash` — OCR extraction texte
  - Taux succes: 100%

- **notification_center_linux**
  - Description: Centre de notifications: envoyer, historique, activer/désactiver DND
  - Triggers: `notifications`, `ne pas déranger`, `mode dnd`, `envoie une notification`, `désactive les notifications`, `active les notifications`
  - Etapes:
    1. `bash` — État notifications
    1. `bash` — Test notification
  - Taux succes: 100%

- **theme_switcher_linux**
  - Description: Changer thème GNOME: sombre, clair, accent, icônes, curseur, fond d'écran
  - Triggers: `change le thème`, `thème sombre`, `thème clair`, `apparence du bureau`, `personnalise le bureau`
  - Etapes:
    1. `bash` — Thème actuel
    1. `bash` — Fond d'écran actuel
  - Taux succes: 100%

- **display_manager_linux**
  - Description: Gestion écrans: résolution, multi-écran, luminosité, orientation
  - Triggers: `gère les écrans`, `résolution écran`, `luminosité`, `multi écran`, `orientation écran`, `affichage`
  - Etapes:
    1. `bash` — Écrans connectés
    1. `bash` — Résolution actuelle
    1. `bash` — Luminosité
  - Taux succes: 100%

- **keyboard_layout_linux**
  - Description: Gestion clavier: layout, raccourcis personnalisés, vitesse de répétition
  - Triggers: `layout clavier`, `disposition clavier`, `change le clavier`, `clavier azerty`, `raccourcis clavier custom`
  - Etapes:
    1. `bash` — Layout clavier
    1. `bash` — Raccourcis personnalisés
  - Taux succes: 100%


### dev (27 skills)

- **mode_dev**
  - Description: Active le mode developpement: terminal, VSCode, status git
  - Triggers: `mode dev`, `mode developpement`, `session dev`, `lance le dev`, `mode code`, `mode programmation`
  - Etapes:
    1. `app_open` — Ouvrir Cursor IDE
    1. `app_open` — Ouvrir Terminal
    1. `lm_cluster_status` — Verifier le cluster IA
  - Taux succes: 100%

- **workspace_frontend**
  - Description: Workspace frontend: Chrome DevTools, VSCode, terminal, localhost
  - Triggers: `workspace frontend`, `mode frontend`, `session front`, `lance le front`, `workspace web`
  - Etapes:
    1. `app_open` — Ouvrir VSCode
    1. `app_open` — Ouvrir Terminal
    1. `open_url` — Ouvrir 127.0.0.1:3000
    1. `notify` — Notification
  - Taux succes: 100%

- **workspace_backend**
  - Description: Workspace backend: terminal, VSCode, Postman, LM Studio
  - Triggers: `workspace backend`, `mode backend`, `session back`, `lance le back`, `workspace api`
  - Etapes:
    1. `app_open` — Ouvrir VSCode
    1. `app_open` — Ouvrir Terminal
    1. `app_open` — Ouvrir LM Studio
    1. `lm_cluster_status` — Verifier le cluster
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_ia**
  - Description: Mode IA: lance LM Studio, check cluster, liste modeles
  - Triggers: `mode ia`, `mode intelligence artificielle`, `session ia`, `lance l'ia`, `active l'ia`, `mode cluster`
  - Etapes:
    1. `app_open` — Lancer LM Studio
    1. `lm_cluster_status` — Verifier le cluster
    1. `lm_models` — Lister les modeles charges
    1. `notify` — Notification
  - Taux succes: 100%

- **deploiement**
  - Description: Mode deploiement: terminal, status systeme, check services, monitoring
  - Triggers: `mode deploiement`, `lance le deploiement`, `session deploy`, `deploy`, `deploie`, `mode deploy`
  - Etapes:
    1. `app_open` — Ouvrir Terminal
    1. `system_info` — Check systeme
    1. `list_services` — Verifier les services
    1. `network_info` — Check reseau
    1. `notify` — Notification
  - Taux succes: 100%

- **workspace_turbo**
  - Description: Workspace JARVIS Turbo: ouvre le projet, terminal, cluster check
  - Triggers: `workspace turbo`, `ouvre turbo`, `session turbo`, `lance turbo`, `mode turbo`, `workspace jarvis`
  - Etapes:
    1. `app_open` — Ouvrir VSCode
    1. `app_open` — Ouvrir Terminal
    1. `open_url` — GitHub Turbo
    1. `lm_cluster_status` — Verifier le cluster
    1. `notify` — Notification
  - Taux succes: 100%

- **workspace_data**
  - Description: Workspace data science: Chrome, LM Studio, terminal, Jupyter
  - Triggers: `workspace data`, `mode data science`, `session data`, `lance le data`, `workspace analyse`
  - Etapes:
    1. `app_open` — Ouvrir Chrome
    1. `app_open` — Ouvrir LM Studio
    1. `app_open` — Ouvrir Terminal
    1. `open_url` — Ouvrir Jupyter
    1. `lm_cluster_status` — Verifier le cluster
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_docker**
  - Description: Mode Docker: liste conteneurs, images, espace disque
  - Triggers: `mode docker`, `check docker`, `etat docker`, `docker complet`, `environnement docker`
  - Etapes:
    1. `bash_run` — Conteneurs actifs
    1. `bash_run` — Images Docker
    1. `bash_run` — Espace Docker
    1. `notify` — Notification
  - Taux succes: 100%

- **git_workflow**
  - Description: Workflow Git: status, diff, log recent, pull
  - Triggers: `git workflow`, `check git`, `etat du repo`, `synchronise git`, `mise a jour git`
  - Etapes:
    1. `bash_run` — Git status
    1. `bash_run` — Git diff
    1. `bash_run` — Log recent
    1. `notify` — Notification
  - Taux succes: 100%

- **workspace_ml**
  - Description: Workspace ML: Jupyter + LM Studio + GPU check
  - Triggers: `workspace ml`, `mode machine learning`, `lance le workspace ml`, `mode ia`, `workspace ia locale`
  - Etapes:
    1. `bash_run` — Lancer LM Studio
    1. `app_open` — Ouvrir Chrome
    1. `bash_run` — Ouvrir Jupyter
    1. `gpu_info` — Check GPU
    1. `lm_cluster_status` — Statut cluster
    1. `notify` — Notification
  - Taux succes: 100%

- **debug_docker**
  - Description: Debug Docker: logs, restart conteneurs, nettoyage volumes
  - Triggers: `debug docker`, `probleme docker`, `docker ne marche pas`, `repare docker`, `clean docker`
  - Etapes:
    1. `bash_run` — Tous les conteneurs
    1. `bash_run` — Volumes Docker
    1. `bash_run` — Nettoyage Docker
    1. `notify` — Notification
  - Taux succes: 100%

- **backup_projet**
  - Description: Backup projet: compresse le dossier turbo + git status + timestamp
  - Triggers: `backup du projet`, `sauvegarde le projet`, `archive le projet`, `compresse turbo`, `backup turbo`
  - Etapes:
    1. `bash_run` — Git status
    1. `bash_run` — Compression
    1. `notify` — Notification
  - Taux succes: 100%

- **analyse_code**
  - Description: Analyse code: fichiers Python, lignes, taille, structure
  - Triggers: `analyse le code`, `stats du code`, `combien de lignes de code`, `metriques du projet`, `analyse le projet`
  - Etapes:
    1. `bash_run` — Fichiers Python
    1. `bash_run` — Lignes de code
    1. `bash_run` — Taille
    1. `notify` — Notification
  - Taux succes: 100%

- **forge_code**
  - Description: The Forge: M2 genere le code, M1 review logique, correction auto si erreur
  - Triggers: `forge du code`, `genere du code`, `code autonome`, `auto code`, `la forge`, `lance la forge`
  - Etapes:
    1. `lm_cluster_status` — Verifier cluster disponible
    1. `lm_query` — M2 genere le code
    1. `lm_query` — M1 review logique
    1. `notify` — Notification
  - Taux succes: 100%

- **shield_audit**
  - Description: The Shield: Audit securite multi-IA parallele (M1 + M2 analysent en parallele)
  - Triggers: `audit de securite`, `shield`, `scan de securite`, `verifie la securite du code`, `audit code`
  - Etapes:
    1. `lm_query` — M1 analyse securite
    1. `lm_query` — M2 analyse logique
    1. `notify` — Notification
  - Taux succes: 100%

- **brain_index**
  - Description: The Brain: Indexe le projet dans la memoire JARVIS via M1
  - Triggers: `indexe le projet`, `memorise le projet`, `brain index`, `mets a jour la memoire`, `apprends le projet`
  - Etapes:
    1. `bash_run` — Lister fichiers source
    1. `bash_run` — Compter les lignes
    1. `lm_query` — M1 resume le projet
    1. `notify` — Notification
  - Taux succes: 100%

- **consensus_mao**
  - Description: MAO Consensus: Question envoyee a M1 + M2 + OL1, synthese des reponses
  - Triggers: `consensus complet`, `mao consensus`, `avis de tous les agents`, `demande a tout le monde`, `consensus multi agent`
  - Etapes:
    1. `lm_cluster_status` — Verifier disponibilite agents
    1. `consensus` — Consensus M1+M2
    1. `lm_query` — Avis OL1
    1. `notify` — Notification
  - Taux succes: 100%

- **lab_tests**
  - Description: The Lab: M1 genere les tests, execute localement, M2 analyse les echecs
  - Triggers: `lance les tests`, `genere des tests`, `test automatique`, `lab tests`, `teste le code`, `pytest`
  - Etapes:
    1. `lm_query` — M1 genere les tests
    1. `bash_run` — Executer pytest
    1. `notify` — Notification
  - Taux succes: 100%

- **architect_diagram**
  - Description: The Architect: M1 analyse le code et genere un diagramme Mermaid de l'architecture
  - Triggers: `diagramme architecture`, `documente l'architecture`, `schema du projet`, `architect`, `mermaid`
  - Etapes:
    1. `bash_run` — Scanner structure code
    1. `lm_query` — M1 genere le diagramme
    1. `notify` — Notification
  - Taux succes: 100%

- **oracle_veille**
  - Description: The Oracle: Recherche web via OL1 cloud (minimax) + synthese M1
  - Triggers: `veille technologique`, `recherche sur le web`, `oracle`, `cherche des infos`, `renseigne toi sur`
  - Etapes:
    1. `ollama_web_search` — OL1 cloud recherche web
    1. `lm_query` — M1 synthetise
    1. `notify` — Notification
  - Taux succes: 100%

- **alchemist_transform**
  - Description: The Alchemist: M1 transforme des donnees d'un format a un autre (CSV, JSON, SQL...)
  - Triggers: `transforme les donnees`, `convertis le fichier`, `alchemist`, `change le format`, `csv vers json`, `json vers csv`
  - Etapes:
    1. `lm_query` — M1 transforme les donnees
    1. `notify` — Notification
  - Taux succes: 100%

- **git_status_jarvis**
  - Description: État git JARVIS: status, branches, derniers commits, diff résumé
  - Triggers: `état du git`, `git status`, `derniers commits`, `qu'est-ce qui a changé`, `historique git`
  - Etapes:
    1. `bash` — État git complet
    1. `bash` — Résumé des changements
  - Taux succes: 100%

- **mode_dev_linux**
  - Description: Mode developpement Linux: VSCode, terminal, git status, services, GPU, load model M1
  - Triggers: `mode developpement linux`, `mode dev linux`, `session dev linux`, `lance le dev linux`, `environnement dev`, `prepare le dev`, `mode programmation linux`
  - Etapes:
    1. `open_app` — Ouvrir VSCode
    1. `bash_run` — Ouvrir terminal JARVIS
    1. `bash_run` — Git status du projet JARVIS
    1. `bash_run` — Verification services actifs
    1. `gpu_info` — Statut GPU complet
    1. `lm_cluster_status` — Statut cluster IA et modeles M1
  - Taux succes: 100%

- **docker_manager_linux**
  - Description: Gestion Docker: containers, images, logs, restart, prune
  - Triggers: `gère docker`, `containers docker`, `images docker`, `docker status`, `docker actifs`
  - Etapes:
    1. `bash` — Containers actifs
    1. `bash` — Images Docker
    1. `bash` — Espace Docker
  - Taux succes: 100%

- **terminal_multiplexer_linux**
  - Description: Gestion tmux: sessions, fenêtres, panneaux, attach/detach
  - Triggers: `gère tmux`, `sessions tmux`, `ouvre tmux`, `nouvelle session`, `liste les sessions tmux`
  - Etapes:
    1. `bash` — Sessions tmux actives
    1. `bash` — Fenêtres tmux
  - Taux succes: 100%

- **pip_packages_linux**
  - Description: Gestion paquets Python: liste, install, outdated, vulnérabilités
  - Triggers: `paquets python`, `pip list`, `paquets périmés`, `vulnérabilités pip`, `dépendances python`
  - Etapes:
    1. `bash` — Nombre paquets
    1. `bash` — Paquets à mettre à jour
    1. `bash` — Audit sécurité
  - Taux succes: 100%

- **git_advanced_linux**
  - Description: Git avancé: stash, rebase, cherry-pick, bisect, reflog, blame
  - Triggers: `git avancé`, `stash le code`, `historique git détaillé`, `qui a écrit ce code`, `cherche le bug git`
  - Etapes:
    1. `bash` — Stash list
    1. `bash` — Reflog récent
    1. `bash` — Branches par date
    1. `bash` — Top contributeurs
  - Taux succes: 100%


### fichiers (1 skills)

- **nettoyage_fichiers**
  - Description: Nettoyage fichiers: doublons + gros fichiers + dossiers vides + temp
  - Triggers: `nettoyage fichiers`, `organise les fichiers`, `fais le menage`, `clean les fichiers`, `libere de l'espace`
  - Etapes:
    1. `bash_run` — Vider temp
    1. `bash_run` — Dossiers vides
    1. `bash_run` — Top 10 gros fichiers
    1. `notify` — Notification
  - Taux succes: 100%


### files (2 skills)

- **file_search_linux**
  - Description: Recherche de fichiers: par nom, contenu, taille, date, type
  - Triggers: `cherche un fichier`, `trouve le fichier`, `recherche fichier`, `où est le fichier`, `find file`
  - Etapes:
    1. `bash` — Fichiers modifiés dernière heure
    1. `bash` — Fichiers >500MB
  - Taux succes: 100%

- **compress_extract_linux**
  - Description: Compression/extraction: tar, zip, 7z, gzip — créer et extraire archives
  - Triggers: `compresse le dossier`, `extrais l'archive`, `crée une archive`, `décompresse`, `zip le dossier`
  - Etapes:
    1. `bash` — Aide compression/extraction
  - Taux succes: 100%


### fix (1 skills)

- **fix_audio_linux**
  - Description: Réparer le son: restart PipeWire/PulseAudio, vérifier sinks, volume
  - Triggers: `répare le son`, `pas de son`, `problème audio`, `le son marche pas`, `fix audio`, `son coupé`
  - Etapes:
    1. `bash` — Info serveur audio
    1. `bash` — Restart audio
    1. `bash` — Liste des sorties audio
    1. `bash` — Rétablit volume
  - Taux succes: 100%


### gpu (1 skills)

- **optimise_gpu_linux**
  - Description: Optimisation GPU: températures, VRAM, processus idle, persistence mode
  - Triggers: `optimise les gpu`, `optimise la vram`, `gpu optimize`, `libère la vram`, `performance gpu`
  - Etapes:
    1. `bash` — État GPU détaillé
    1. `bash` — Processus GPU actifs
    1. `bash` — Active persistence mode
    1. `bash` — Libère cache mémoire
  - Taux succes: 100%


### hardware (3 skills)

- **bluetooth_manager_linux**
  - Description: Gestion Bluetooth: scanner, connecter, déconnecter, info appareils
  - Triggers: `gère le bluetooth`, `bluetooth status`, `appareils bluetooth`, `connecte bluetooth`, `scanner bluetooth`
  - Etapes:
    1. `bash` — État Bluetooth
    1. `bash` — Appareils connus
    1. `bash` — Info appareil connecté
  - Taux succes: 100%

- **usb_devices_linux**
  - Description: Gestion USB: lister appareils, éjecter, monter clés USB
  - Triggers: `appareils usb`, `liste les usb`, `clé usb`, `éjecte la clé`, `périphériques connectés`
  - Etapes:
    1. `bash` — Appareils USB
    1. `bash` — Disques et partitions
    1. `bash` — Points de montage externes
  - Taux succes: 100%

- **printer_manager_linux**
  - Description: Gestion imprimantes: lister, imprimer, file d'attente, état
  - Triggers: `gère les imprimantes`, `imprimante status`, `liste les imprimantes`, `file d'impression`, `état imprimante`
  - Etapes:
    1. `bash` — Imprimantes disponibles
    1. `bash` — File d'impression
  - Taux succes: 100%


### info (1 skills)

- **weather_info_linux**
  - Description: Météo locale: température, conditions, prévisions via wttr.in
  - Triggers: `quelle météo`, `quel temps fait-il`, `météo`, `température dehors`, `prévisions météo`, `il fait combien`
  - Etapes:
    1. `bash` — Météo actuelle
    1. `bash` — Détails météo
  - Taux succes: 100%


### loisir (6 skills)

- **mode_gaming**
  - Description: Active le mode gaming: ferme Chrome, lance Steam, volume max
  - Triggers: `mode gaming`, `mode jeu`, `lance le gaming`, `session gaming`, `on joue`
  - Etapes:
    1. `close_app` — Fermer Chrome
    1. `app_open` — Lancer Steam
    1. `volume_up` — Monter le volume
    1. `volume_up` — Monter le volume
  - Taux succes: 100%

- **mode_musique**
  - Description: Mode musique: lance Spotify, volume agreable, mode nuit
  - Triggers: `mode musique`, `mets de la musique`, `ambiance musicale`, `lance la musique de fond`, `background music`
  - Etapes:
    1. `app_open` — Lancer Spotify
    1. `volume_down` — Baisser un peu le volume
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_stream**
  - Description: Mode streaming: lance OBS, Chrome, volume optimal, mode nuit off
  - Triggers: `mode stream`, `lance le stream`, `session stream`, `je stream`, `streaming mode`
  - Etapes:
    1. `app_open` — Lancer OBS Studio
    1. `app_open` — Ouvrir Chrome
    1. `volume_up` — Monter le volume
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_cinema**
  - Description: Mode cinema: ferme tout, volume max, luminosite min, plein ecran
  - Triggers: `mode cinema`, `mode film`, `lance un film`, `session cinema`, `regarde un film`
  - Etapes:
    1. `close_app` — Fermer Discord
    1. `close_app` — Fermer Telegram
    1. `volume_up` — Monter le volume
    1. `volume_up` — Volume max
    1. `bash_run` — Luminosite tamisee
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_confort**
  - Description: Mode confort: night light, luminosite agreable, volume moyen, focus assist
  - Triggers: `mode confort`, `ambiance confortable`, `mode relax`, `mode zen`, `ambiance douce`
  - Etapes:
    1. `bash_run` — Luminosite 50%
    1. `volume_down` — Volume moyen
    1. `press_hotkey` — Mode nuit
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_stream_pro**
  - Description: Mode stream pro: OBS + micro check + game bar + performance max
  - Triggers: `mode stream pro`, `prepare le stream`, `streaming pro`, `je vais streamer`
  - Etapes:
    1. `app_open` — Lancer OBS
    1. `press_hotkey` — Game Bar
    1. `bash_run` — Performance max
    1. `notify` — Notification
  - Taux succes: 100%


### maintenance (4 skills)

- **maintenance_complete_linux**
  - Description: Maintenance complete Linux: apt update/upgrade, snap refresh, autoremove, vacuum journaux, clean tmp, check services
  - Triggers: `fais une maintenance complete`, `maintenance complete linux`, `maintenance systeme`, `mets a jour et nettoie`, `entretien complet`, `maintenance full linux`, `apt update et nettoyage`
  - Etapes:
    1. `bash_run` — Mise a jour des paquets APT
    1. `bash_run` — Upgrade des paquets APT
    1. `bash_run` — Mise a jour des snaps
    1. `bash_run` — Suppression paquets orphelins
    1. `bash_run` — Nettoyage journaux systeme (7 jours)
    1. `bash_run` — Nettoyage fichiers tmp anciens
    1. `bash_run` — Verification services en echec
  - Taux succes: 100%

- **nettoyage_profond_linux**
  - Description: Nettoyage profond Linux: corbeille, autoremove, snap prune, journal vacuum, vieux logs, docker prune, tmp
  - Triggers: `nettoyage profond`, `nettoyage profond linux`, `clean profond`, `nettoie tout en profondeur`, `grand nettoyage`, `purge complete`, `libere de l'espace`
  - Etapes:
    1. `bash_run` — Vider la corbeille
    1. `bash_run` — APT autoremove et autoclean
    1. `bash_run` — Suppression anciennes revisions snap
    1. `bash_run` — Vacuum des journaux systeme (max 200M)
    1. `bash_run` — Nettoyage vieux logs comprimes
    1. `bash_run` — Docker prune complet
    1. `bash_run` — Nettoyage tmp et verification espace libere
  - Taux succes: 100%

- **database_manager_linux**
  - Description: Gestion bases de données JARVIS: tailles, intégrité, vacuum, stats
  - Triggers: `gère les bases de données`, `état des bases`, `database status`, `taille des bases`, `intégrité db`
  - Etapes:
    1. `bash` — Tailles des bases
    1. `bash` — Check intégrité
    1. `bash` — Tables jarvis.db
    1. `bash` — Compteurs
  - Taux succes: 100%

- **system_cleanup_aggressive**
  - Description: Nettoyage agressif: tout supprimer pour récupérer max d'espace disque
  - Triggers: `nettoyage agressif`, `libère tout l'espace`, `nettoyage maximum`, `vide tout`, `espace critique`
  - Etapes:
    1. `bash` — Espace avant
    1. `bash` — APT cleanup
    1. `bash` — Snap revisions
    1. `bash` — Journaux à 50MB max
    1. `bash` — Cache + corbeille + tmp
    1. `bash` — Docker total prune
    1. `bash` — Cache pip + npm
    1. `bash` — Espace après
  - Taux succes: 100%


### monitoring (8 skills)

- **linux_health_check**
  - Description: Diagnostic complet santé Linux: CPU, RAM, GPU, disques, services, réseau
  - Triggers: `vérifie la santé du système`, `health check linux`, `diagnostic système`, `comment va le système`, `état de santé`
  - Etapes:
    1. `bash` — Diagnostic complet système Linux
  - Taux succes: 100%

- **disk_analysis_linux**
  - Description: Analyse disque: espace, gros fichiers, SMART, IO
  - Triggers: `analyse le disque`, `espace disque`, `gros fichiers`, `santé du disque`, `disque plein`, `stockage`
  - Etapes:
    1. `bash` — Espace disque
    1. `bash` — Plus gros fichiers
    1. `bash` — Plus gros dossiers
    1. `bash` — Santé SMART
  - Taux succes: 100%

- **rapport_systeme_linux**
  - Description: Rapport systeme complet Linux: CPU/RAM/Disk, GPU, services, cluster, uptime, erreurs journal
  - Triggers: `rapport systeme complet`, `rapport systeme linux`, `etat du systeme`, `resume systeme`, `status complet linux`, `bilan systeme`, `comment va le systeme`
  - Etapes:
    1. `system_info` — Infos CPU/RAM/Disque
    1. `gpu_info` — Infos GPU complet (6 GPUs)
    1. `bash_run` — Services JARVIS actifs
    1. `lm_cluster_status` — Sante du cluster IA
    1. `bash_run` — Uptime et charge systeme
    1. `bash_run` — Erreurs journal des 24 dernieres heures
    1. `bash_run` — Resume formate du rapport
  - Taux succes: 100%

- **system_benchmark_linux**
  - Description: Benchmark système: CPU, RAM, disque, GPU, réseau
  - Triggers: `benchmark système`, `teste les performances`, `vitesse du système`, `benchmark`, `test de performance`
  - Etapes:
    1. `bash` — Benchmark CPU
    1. `bash` — Benchmark disque
    1. `bash` — Info GPU
    1. `bash` — Benchmark réseau
  - Taux succes: 100%

- **log_forensics_linux**
  - Description: Analyse forensique des logs: erreurs critiques, patterns, anomalies, timeline
  - Triggers: `analyse les logs`, `forensique logs`, `erreurs critiques`, `anomalies système`, `investigation logs`
  - Etapes:
    1. `bash` — Erreurs critiques
    1. `bash` — Erreurs kernel
    1. `bash` — Out of memory events
    1. `bash` — Segmentation faults
    1. `bash` — Erreurs GPU
  - Taux succes: 100%

- **jarvis_self_diagnostic**
  - Description: Auto-diagnostic complet JARVIS: services, DB, voice, brain, cluster, dashboard
  - Triggers: `auto diagnostic jarvis`, `diagnostic complet jarvis`, `santé de jarvis`, `vérifie que jarvis marche`, `self diagnostic`
  - Etapes:
    1. `bash` — Tous les services JARVIS
    1. `bash` — Intégrité DB
    1. `bash` — Dashboard web
    1. `bash` — MCP server
    1. `bash` — Whisper STT
    1. `bash` — Brain skills count
    1. `bash` — Cluster nodes
  - Taux succes: 100%

- **systemd_journal_live**
  - Description: Suivi en direct des logs système: journalctl follow, filtres par service/priorité
  - Triggers: `logs en direct`, `suivi des logs`, `journalctl follow`, `logs temps réel`, `surveille les logs`
  - Etapes:
    1. `bash` — Derniers logs utilisateur
    1. `bash` — Erreurs dernière heure
  - Taux succes: 100%

- **system_uptime_report**
  - Description: Rapport uptime: durée, dernier boot, reboots récents, charge moyenne
  - Triggers: `uptime`, `depuis combien de temps`, `dernier redémarrage`, `durée de fonctionnement`, `quand ai-je redémarré`
  - Etapes:
    1. `bash` — Rapport uptime complet
  - Taux succes: 100%


### navigation (1 skills)

- **navigation_rapide**
  - Description: Navigation rapide: nouveau tab + favoris + zoom reset
  - Triggers: `navigation rapide`, `chrome rapide`, `surf rapide`, `nouveau surf`
  - Etapes:
    1. `app_open` — Ouvrir Chrome
    1. `press_hotkey` — Nouvel onglet
    1. `press_hotkey` — Reset zoom
    1. `notify` — Notification
  - Taux succes: 100%


### network (4 skills)

- **wifi_manager_linux**
  - Description: Gestion WiFi: scanner, connecter, déconnecter, info connexion
  - Triggers: `gère le wifi`, `wifi status`, `scanner wifi`, `connecte au wifi`, `réseaux disponibles`, `problème wifi`
  - Etapes:
    1. `bash` — Connexion WiFi active
    1. `bash` — Réseaux disponibles
    1. `bash` — Adresse IP WiFi
  - Taux succes: 100%

- **diagnostic_reseau_linux**
  - Description: Diagnostic reseau complet Linux: IP, nmcli, DNS, ping, traceroute, connexions, bande passante
  - Triggers: `diagnostic reseau complet`, `diagnostic reseau linux`, `check le reseau`, `probleme reseau`, `analyse reseau`, `debug reseau linux`, `test reseau complet`
  - Etapes:
    1. `bash_run` — Adresses IP et interfaces
    1. `bash_run` — Statut NetworkManager
    1. `bash_run` — Verification DNS
    1. `bash_run` — Ping de la passerelle
    1. `bash_run` — Traceroute vers Google DNS
    1. `bash_run` — Connexions actives
    1. `bash_run` — Test de bande passante rapide
  - Taux succes: 100%

- **ssh_manager_linux**
  - Description: Gestion SSH: connexions, clés, tunnels, config
  - Triggers: `gère le ssh`, `connexions ssh`, `clés ssh`, `tunnel ssh`, `ssh config`
  - Etapes:
    1. `bash` — Clés publiques
    1. `bash` — Connexions SSH actives
    1. `bash` — Config SSH
  - Taux succes: 100%

- **ip_geolocation_linux**
  - Description: Géolocalisation IP: IP publique, localisation, ISP, VPN check
  - Triggers: `mon ip publique`, `où suis-je`, `géolocalisation`, `ip externe`, `quel est mon fournisseur`
  - Etapes:
    1. `bash` — Info IP publique
  - Taux succes: 100%


### performance (2 skills)

- **optimise_systeme_linux**
  - Description: Optimisation systeme Linux: swap, caches, GPU, zombies, compactage DB, espace disque
  - Triggers: `optimise le systeme`, `optimisation linux`, `boost le systeme`, `accelere le pc`, `optimise linux`, `rends le systeme plus rapide`, `performance systeme`
  - Etapes:
    1. `bash_run` — Reinitialisation du swap
    1. `bash_run` — Liberation des caches memoire
    1. `bash_run` — Optimisation GPU persistence mode
    1. `bash_run` — Suppression processus zombies
    1. `bash_run` — Compactage bases de donnees
    1. `bash_run` — Verification espace disque
  - Taux succes: 100%

- **startup_optimizer_linux**
  - Description: Optimiser le démarrage: analyser temps boot, apps autostart, services lents
  - Triggers: `optimise le démarrage`, `boot lent`, `temps de démarrage`, `analyse le boot`, `startup optimizer`
  - Etapes:
    1. `bash` — Temps de boot total
    1. `bash` — Services les plus lents
    1. `bash` — Apps au démarrage
    1. `bash` — Services activés
  - Taux succes: 100%


### productivite (14 skills)

- **mode_presentation**
  - Description: Mode presentation: mode nuit off, luminosite max, volume moyen, projeter ecran
  - Triggers: `mode presentation`, `lance la presentation`, `mode pres`, `je presente`, `active la presentation`
  - Etapes:
    1. `press_hotkey` — Ouvrir projection ecran
    1. `bash_run` — Luminosite max
    1. `volume_down` — Baisser le volume
    1. `press_hotkey` — Afficher le bureau
  - Taux succes: 100%

- **mode_focus**
  - Description: Mode focus: ferme les distractions, active ne pas deranger, plein ecran
  - Triggers: `mode focus`, `mode concentration`, `je bosse`, `pas de distraction`, `focus total`, `mode travail`
  - Etapes:
    1. `close_app` — Fermer Discord
    1. `close_app` — Fermer Spotify
    1. `close_app` — Fermer Telegram
    1. `volume_mute` — Couper le son
    1. `notify` — Notification
  - Taux succes: 100%

- **split_screen_travail**
  - Description: Ecran divise: navigateur a gauche, editeur a droite
  - Triggers: `ecran divise`, `split screen`, `deux fenetres`, `moitie moitie`, `cote a cote`, `ecran de travail`, `espace de travail`, `travail en split`
  - Etapes:
    1. `app_open` — Ouvrir Chrome
    1. `press_hotkey` — Chrome a gauche
    1. `app_open` — Ouvrir VSCode
    1. `press_hotkey` — VSCode a droite
  - Taux succes: 100%

- **backup_rapide**
  - Description: Sauvegarde rapide: save tout, screenshot, copier dans presse-papier
  - Triggers: `backup rapide`, `sauvegarde rapide`, `save all`, `tout sauvegarder`, `sauve tout`
  - Etapes:
    1. `press_hotkey` — Sauvegarder fichier actif
    1. `screenshot` — Capture d'ecran
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_lecture**
  - Description: Mode lecture: ferme distractions, mode nuit, volume bas, zoom texte
  - Triggers: `mode lecture`, `mode etude`, `session lecture`, `je lis`, `mode read`, `mode lire`
  - Etapes:
    1. `close_app` — Fermer Discord
    1. `close_app` — Fermer Spotify
    1. `press_hotkey` — Mode nuit
    1. `volume_down` — Baisser le volume
    1. `volume_down` — Volume minimal
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_recherche**
  - Description: Mode recherche: ouvre Chrome, Google, multiple onglets, presse-papier
  - Triggers: `mode recherche`, `session recherche`, `lance les recherches`, `mode investigation`, `je recherche`
  - Etapes:
    1. `app_open` — Ouvrir Chrome
    1. `open_url` — Google
    1. `open_url` — Perplexity
    1. `notify` — Notification
  - Taux succes: 100%

- **session_creative**
  - Description: Session creative: Spotify, mode focus, snap layout, luminosite agreable
  - Triggers: `session creative`, `mode creatif`, `inspiration`, `mode creation`, `lance la creation`
  - Etapes:
    1. `app_open` — Lancer Spotify
    1. `close_app` — Fermer Discord
    1. `bash_run` — Luminosite agreable
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_double_ecran**
  - Description: Mode double ecran: etend l'affichage, snap layout, navigateur + editeur
  - Triggers: `mode double ecran`, `deux ecrans`, `active le second ecran`, `dual screen`, `mode etendu`
  - Etapes:
    1. `bash_run` — Etendre l'affichage
    1. `app_open` — Ouvrir Chrome
    1. `press_hotkey` — Chrome a gauche
    1. `app_open` — Ouvrir VSCode
    1. `press_hotkey` — VSCode a droite
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_partage_ecran**
  - Description: Mode partage ecran: Miracast + luminosite max + mode presentation
  - Triggers: `mode partage ecran`, `partage d'ecran`, `diffuse l'ecran`, `lance le cast`, `envoie sur la tv`
  - Etapes:
    1. `press_hotkey` — Ouvrir Miracast
    1. `bash_run` — Luminosite max
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_nuit_complet**
  - Description: Mode nuit complet: mode sombre + night light + luminosite basse + volume bas
  - Triggers: `mode nuit complet`, `ambiance nuit`, `tout en sombre`, `active tout le mode nuit`, `nuit totale`
  - Etapes:
    1. `bash_run` — Mode sombre
    1. `bash_run` — Luminosite basse
    1. `volume_down` — Volume bas
    1. `volume_down` — Volume minimal
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_jour**
  - Description: Mode jour: mode clair + luminosite max + night light off
  - Triggers: `mode jour`, `mode journee`, `tout en clair`, `ambiance jour`, `reveil`
  - Etapes:
    1. `bash_run` — Mode clair
    1. `bash_run` — Luminosite haute
    1. `volume_up` — Volume normal
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_presentation_pro**
  - Description: Mode presentation pro: ecran etendu + volume off + focus assist + luminosite max
  - Triggers: `mode presentation pro`, `je vais presenter`, `prepare la presentation`, `powerpoint mode`
  - Etapes:
    1. `bash_run` — Ecran etendu
    1. `bash_run` — Luminosite max
    1. `press_hotkey` — Couper le son
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_dual_screen**
  - Description: Mode double ecran: etendre + snap fenetre + luminosite uniforme
  - Triggers: `mode double ecran`, `active les deux ecrans`, `mode dual screen`, `deux ecrans`, `branche l'ecran`
  - Etapes:
    1. `bash_run` — Ecran etendu
    1. `bash_run` — Luminosite 70%
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_4_fenetres**
  - Description: Mode 4 fenetres: snap en 4 coins + luminosite equilibree
  - Triggers: `mode 4 fenetres`, `quatre fenetres`, `snap en 4`, `4 coins`, `quadrillage`
  - Etapes:
    1. `press_hotkey` — Vue des taches
    1. `bash_run` — Luminosite equilibree
    1. `notify` — Notification
  - Taux succes: 100%


### productivity (2 skills)

- **focus_mode_linux**
  - Description: Mode focus: DND, ferme distractions, timer pomodoro, réduit notifications
  - Triggers: `mode focus`, `concentration`, `ne me dérange pas`, `pomodoro`, `mode travail`, `focus`
  - Etapes:
    1. `bash` — Désactive notifications
    1. `bash` — Ferme apps distrayantes
    1. `bash` — Timer pomodoro 25min
  - Taux succes: 100%

- **quick_note_linux**
  - Description: Prendre une note rapide: sauvegarder texte, lister notes, chercher
  - Triggers: `prends une note`, `note rapide`, `sauvegarde cette note`, `mes notes`, `liste les notes`
  - Etapes:
    1. `bash` — Notes existantes
    1. `bash` — Guide utilisation
  - Taux succes: 100%


### profil (8 skills)

- **profil_normal**
  - Description: Active le profil vocal normal: toutes commandes, comportement par defaut
  - Triggers: `mode normal`, `profil normal`, `retour normal`, `desactive le mode`, `mode par defaut`
  - Etapes:
    1. `bash_run` — Activer profil normal
  - Taux succes: 100%

- **profil_dev**
  - Description: Active le profil vocal dev: priorite git, docker, pytest, IDE
  - Triggers: `mode dev`, `profil dev`, `mode developpement`, `session dev`, `mode code`, `mode programmation`
  - Etapes:
    1. `bash_run` — Activer profil dev
    1. `app_open` — Ouvrir Cursor IDE
    1. `app_open` — Ouvrir Terminal
  - Taux succes: 100%

- **profil_trading**
  - Description: Active le profil vocal trading: priorite scans, alertes, pipelines
  - Triggers: `mode trading`, `profil trading`, `session trading`, `active le trading`, `demarre le trading`
  - Etapes:
    1. `bash_run` — Activer profil trading
    1. `app_open` — Ouvrir Chrome
    1. `open_url` — TradingView
    1. `trading_status` — Verifier le pipeline
  - Taux succes: 100%

- **profil_gaming**
  - Description: Active le profil vocal gaming: performance, son max, minimal
  - Triggers: `mode gaming`, `profil gaming`, `mode jeu`, `session gaming`, `on joue`
  - Etapes:
    1. `bash_run` — Activer profil gaming
    1. `close_app` — Fermer Chrome
    1. `app_open` — Lancer Steam
  - Taux succes: 100%

- **profil_presentation**
  - Description: Active le profil vocal presentation: DND, plein ecran, pas de notifications
  - Triggers: `mode presentation`, `profil presentation`, `mode prez`, `mode conference`, `mode meeting`
  - Etapes:
    1. `bash_run` — Activer profil presentation
    1. `bash_run` — Desactiver notifications
  - Taux succes: 100%

- **profil_sleep**
  - Description: Active le profil vocal sleep: economie energie, services reduits, verrouillage
  - Triggers: `mode sleep`, `profil sleep`, `mode veille`, `mode nuit`, `bonne nuit`, `mode economie`
  - Etapes:
    1. `bash_run` — Activer profil sleep
    1. `bash_run` — Verrouiller session
  - Taux succes: 100%

- **profil_debug**
  - Description: Active le profil vocal debug: logs verbeux, monitoring detaille
  - Triggers: `mode debug`, `profil debug`, `mode diagnostic`, `mode verbose`, `mode logs`
  - Etapes:
    1. `bash_run` — Activer profil debug
    1. `diagnostics_run` — Lancer diagnostics
  - Taux succes: 100%

- **profil_guest**
  - Description: Active le profil vocal invite: commandes limitees, pas d'actions destructives
  - Triggers: `mode invite`, `profil invite`, `mode guest`, `profil guest`, `mode visiteur`
  - Etapes:
    1. `bash_run` — Activer profil guest
  - Taux succes: 100%


### routine (8 skills)

- **rapport_matin**
  - Description: Rapport complet du matin: cluster, trading, systeme
  - Triggers: `rapport du matin`, `rapport matin`, `briefing matin`, `resume du matin`, `status complet`, `etat general`
  - Etapes:
    1. `lm_cluster_status` — Statut du cluster IA
    1. `system_info` — Infos systeme
    1. `trading_status` — Status pipeline trading
    1. `trading_pending_signals` — Signaux en attente
  - Taux succes: 100%

- **routine_soir**
  - Description: Routine du soir: sauvegarde, ferme apps, mode nuit, veille
  - Triggers: `routine du soir`, `bonne nuit`, `fin de journee`, `je vais dormir`, `routine nuit`, `au dodo`
  - Etapes:
    1. `press_hotkey` — Sauvegarder le travail en cours
    1. `close_app` — Fermer Chrome
    1. `close_app` — Fermer VSCode
    1. `close_app` — Fermer Discord
    1. `press_hotkey` — Activer mode nuit
    1. `bash_run` — Luminosite basse
    1. `notify` — Notification
  - Taux succes: 100%

- **pause_cafe**
  - Description: Pause cafe: sauvegarde, verrouille le PC, coupe le son
  - Triggers: `pause cafe`, `je fais une pause`, `pause`, `je reviens`, `brb`, `afk`
  - Etapes:
    1. `press_hotkey` — Sauvegarder
    1. `volume_mute` — Couper le son
    1. `lock_screen` — Verrouiller le PC
  - Taux succes: 100%

- **retour_pause**
  - Description: Retour de pause: reactive le son, check notifications, status rapide
  - Triggers: `retour de pause`, `je suis revenu`, `c'est bon je suis la`, `retour`, `de retour`, `je suis de retour`
  - Etapes:
    1. `volume_up` — Remettre le son
    1. `volume_up` — Volume normal
    1. `system_info` — Check systeme rapide
    1. `notify` — Notification
  - Taux succes: 100%

- **rapport_soir**
  - Description: Rapport du soir: bilan trading, cluster status, historique actions
  - Triggers: `rapport du soir`, `bilan du soir`, `briefing soir`, `resume de la journee`, `bilan journee`
  - Etapes:
    1. `trading_status` — Bilan trading
    1. `trading_positions` — Positions restantes
    1. `lm_cluster_status` — Status cluster
    1. `system_info` — Status systeme
    1. `action_history` — Historique des actions
  - Taux succes: 100%

- **fin_journee**
  - Description: Fin de journee: sauvegarde + ferme tout + planifie veille
  - Triggers: `fin de journee`, `j'ai fini`, `bonne nuit jarvis`, `c'est fini pour aujourd'hui`, `je m'en vais`
  - Etapes:
    1. `press_hotkey` — Sauvegarder
    1. `bash_run` — Heure de fin
    1. `notify` — Notification
  - Taux succes: 100%

- **director_standup**
  - Description: The Director: Rapport quotidien basé sur git log + status systeme + trading
  - Triggers: `rapport quotidien`, `standup`, `director`, `resume de la journee`, `qu'est ce qui s'est passe`
  - Etapes:
    1. `bash_run` — Git log 24h
    1. `system_info` — Status systeme
    1. `trading_status` — Status trading
    1. `lm_query` — M1 genere le rapport
    1. `notify` — Notification
  - Taux succes: 100%

- **bonne_nuit_linux**
  - Description: Bonne nuit Linux: sauvegarde, backup DBs, check crons, power-saver, reduce GPU, stop services, lock screen
  - Triggers: `bonne nuit jarvis linux`, `bonne nuit linux`, `mode nuit linux`, `dodo linux`, `eteins tout linux`, `fin de journee linux`, `jarvis bonne nuit`
  - Etapes:
    1. `bash_run` — Synchronisation ecritures disque
    1. `bash_run` — Backup des bases de donnees
    1. `bash_run` — Verification des taches planifiees
    1. `bash_run` — Activation mode economie CPU
    1. `bash_run` — Reduction puissance GPU
    1. `bash_run` — Arret des services non essentiels
    1. `bash_run` — Verrouillage de l'ecran
  - Taux succes: 100%


### security (1 skills)

- **securite_audit_linux**
  - Description: Audit de securite Linux: ufw, fail2ban, ports ouverts, apparmor, rootkits, permissions home
  - Triggers: `audit de securite`, `securite audit linux`, `check securite`, `verifie la securite`, `scan de securite`, `audit securite complet`, `analyse securite linux`
  - Etapes:
    1. `bash_run` — Statut du pare-feu UFW
    1. `bash_run` — Statut Fail2Ban
    1. `bash_run` — Ports ouverts et services a l'ecoute
    1. `bash_run` — Statut AppArmor
    1. `bash_run` — Verification rootkits
    1. `bash_run` — Verification permissions /home
  - Taux succes: 100%


### system (4 skills)

- **process_killer_linux**
  - Description: Gestion processus: top consommateurs, kill processus, zombies
  - Triggers: `tue le processus`, `processus bloqué`, `kill process`, `processus qui rame`, `top processus`, `application bloquée`
  - Etapes:
    1. `bash` — Top processus CPU
    1. `bash` — Top processus RAM
    1. `bash` — Processus zombies
  - Taux succes: 100%

- **service_manager_linux**
  - Description: Gestion services JARVIS: lister, redémarrer, activer, désactiver
  - Triggers: `gère les services`, `services jarvis`, `redémarre les services`, `services plantés`, `liste les services`
  - Etapes:
    1. `bash` — Services running
    1. `bash` — Services en échec
    1. `bash` — Timers actifs
    1. `bash` — Mémoire par service
  - Taux succes: 100%

- **cron_audit_linux**
  - Description: Audit des tâches planifiées: crons, timers systemd, at jobs
  - Triggers: `vérifie les crons`, `tâches planifiées`, `cron audit`, `timers actifs`, `jobs planifiés`
  - Etapes:
    1. `bash` — Crons utilisateur
    1. `bash` — Timers systemd user
    1. `bash` — Timers systemd système
    1. `bash` — Jobs AT
  - Taux succes: 100%

- **env_manager_linux**
  - Description: Gestion variables d'environnement: lister, vérifier, .env status
  - Triggers: `variables d'environnement`, `env vars`, `vérifie le env`, `dotenv status`, `environnement système`
  - Etapes:
    1. `bash` — Variables JARVIS (masquées)
    1. `bash` — Fichier .env
    1. `bash` — Premiers éléments du PATH
  - Taux succes: 100%


### systeme (30 skills)

- **diagnostic_complet**
  - Description: Diagnostic complet: systeme, GPU, cluster, reseau, disques
  - Triggers: `diagnostic complet`, `check complet`, `verification complete`, `tout verifier`, `health check`, `bilan complet`
  - Etapes:
    1. `system_info` — Infos systeme
    1. `gpu_info` — Infos GPU
    1. `lm_cluster_status` — Statut cluster
    1. `network_info` — Infos reseau
  - Taux succes: 100%

- **cleanup_ram**
  - Description: Nettoyer la RAM: lister les processus gourmands et suggerer
  - Triggers: `nettoie la ram`, `libere la memoire`, `cleanup ram`, `ram pleine`, `trop de ram utilisee`
  - Etapes:
    1. `system_info` — Verifier la RAM
    1. `list_processes` — Lister les processus
  - Taux succes: 100%

- **ferme_tout**
  - Description: Fermer toutes les applications non essentielles
  - Triggers: `ferme tout`, `tout fermer`, `clean desktop`, `bureau propre`, `ferme les applications`
  - Etapes:
    1. `close_app` — Fermer Chrome
    1. `close_app` — Fermer Discord
    1. `close_app` — Fermer Spotify
    1. `press_hotkey` — Afficher le bureau
  - Taux succes: 100%

- **optimiser_pc**
  - Description: Optimisation PC: vider corbeille, nettoyer RAM, diagnostic disque
  - Triggers: `optimise le pc`, `nettoie le pc`, `optimisation`, `accelere le pc`, `pc lent`, `boost pc`
  - Etapes:
    1. `system_info` — Diagnostic systeme
    1. `list_processes` — Lister processus gourmands
    1. `bash_run` — Vider la corbeille
    1. `gpu_info` — Verifier les GPU
    1. `notify` — Notification
  - Taux succes: 100%

- **monitoring_complet**
  - Description: Monitoring en temps reel: systeme, GPU, reseau, cluster, services
  - Triggers: `monitoring complet`, `surveillance complete`, `tout surveiller`, `dashboard monitoring`, `status global`
  - Etapes:
    1. `system_info` — Infos systeme
    1. `gpu_info` — Infos GPU
    1. `network_info` — Infos reseau
    1. `lm_cluster_status` — Cluster IA
    1. `screen_resolution` — Resolution ecran
    1. `wifi_networks` — Reseaux Wi-Fi
    1. `list_services` — Services Windows
  - Taux succes: 100%

- **debug_reseau**
  - Description: Debug reseau: info reseau, scan wifi, ping, services, IP
  - Triggers: `debug reseau`, `probleme reseau`, `diagnostique reseau`, `le reseau marche pas`, `pas d'internet`, `debug network`
  - Etapes:
    1. `network_info` — Infos reseau
    1. `wifi_networks` — Scanner Wi-Fi
    1. `ping` — Ping Google DNS
    1. `ping` — Ping gateway
    1. `notify` — Notification
  - Taux succes: 100%

- **update_systeme**
  - Description: Preparation mise a jour: sauvegarde, check updates, check espace disque
  - Triggers: `update systeme`, `mise a jour systeme`, `prepare les updates`, `mets a jour le pc`, `lance les mises a jour`
  - Etapes:
    1. `press_hotkey` — Sauvegarder le travail
    1. `system_info` — Check systeme
    1. `bash_run` — Espace disque
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_securite**
  - Description: Mode securite: mode avion, verrouillage, bluetooth off
  - Triggers: `mode securite`, `securise le pc`, `mode panique`, `coupe tout`, `mode offline`
  - Etapes:
    1. `press_hotkey` — Sauvegarder
    1. `bash_run` — Couper Bluetooth
    1. `volume_mute` — Couper le son
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_accessibilite**
  - Description: Mode accessibilite: loupe, narrateur, contraste eleve, clavier visuel
  - Triggers: `mode accessibilite`, `aide visuelle`, `active l'accessibilite`, `j'ai du mal a voir`, `mode malvoyant`
  - Etapes:
    1. `press_hotkey` — Activer la loupe
    1. `bash_run` — Ouvrir clavier visuel
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_economie_energie**
  - Description: Mode economie: plan eco, luminosite basse, bluetooth off, mode nuit
  - Triggers: `mode economie`, `economise la batterie`, `mode batterie`, `economie d'energie`, `mode eco`
  - Etapes:
    1. `bash_run` — Plan economie
    1. `bash_run` — Luminosite basse
    1. `bash_run` — Couper Bluetooth
    1. `press_hotkey` — Mode nuit
    1. `notify` — Notification
  - Taux succes: 100%

- **mode_performance_max**
  - Description: Mode performance: plan haute perf, luminosite max, bluetooth off
  - Triggers: `mode performance`, `performances max`, `full power`, `mode turbo pc`, `puissance maximale`
  - Etapes:
    1. `bash_run` — Plan haute performance
    1. `bash_run` — Luminosite max
    1. `notify` — Notification
  - Taux succes: 100%

- **clean_reseau**
  - Description: Nettoyage reseau complet: flush DNS, check IP, scan wifi, ping
  - Triggers: `clean reseau`, `nettoie le reseau`, `repare internet`, `flush dns complet`, `reset reseau`
  - Etapes:
    1. `bash_run` — Vider le cache DNS
    1. `network_info` — Infos reseau
    1. `wifi_networks` — Scanner Wi-Fi
    1. `ping` — Ping Google DNS
    1. `notify` — Notification
  - Taux succes: 100%

- **nettoyage_complet**
  - Description: Nettoyage complet: temp + corbeille + DNS + diagnostic
  - Triggers: `nettoyage complet`, `grand nettoyage`, `clean complet`, `nettoie tout`, `purge complete`
  - Etapes:
    1. `bash_run` — Vider temp
    1. `bash_run` — Vider corbeille
    1. `bash_run` — Vider DNS
    1. `system_info` — Diagnostic systeme
    1. `notify` — Notification
  - Taux succes: 100%

- **check_espace_disque**
  - Description: Verification espace disque + temp + diagnostic stockage
  - Triggers: `check espace disque`, `verifie l'espace`, `combien de place reste`, `disques pleins`, `espace restant`
  - Etapes:
    1. `bash_run` — Espace disque
    1. `bash_run` — Taille fichiers temp
    1. `notify` — Notification
  - Taux succes: 100%

- **audit_securite**
  - Description: Audit securite: Windows Security + pare-feu + services + confidentialite
  - Triggers: `audit securite`, `check securite`, `verification securite`, `securite du pc`, `scan securite`
  - Etapes:
    1. `app_open` — Ouvrir Windows Security
    1. `list_services` — Verifier les services
    1. `network_info` — Check reseau
    1. `notify` — Notification
  - Taux succes: 100%

- **maintenance_complete**
  - Description: Maintenance complete: nettoyage disque + temp + defrag + check espace
  - Triggers: `maintenance complete`, `entretien du pc`, `maintenance pc`, `entretien complet`, `soin du pc`
  - Etapes:
    1. `bash_run` — Vider temp
    1. `bash_run` — Vider corbeille
    1. `bash_run` — Espace disque
    1. `system_info` — Diagnostic systeme
    1. `gpu_info` — Check GPU
    1. `notify` — Notification
  - Taux succes: 100%

- **diagnostic_demarrage**
  - Description: Diagnostic demarrage: apps au demarrage + services + utilisation disque
  - Triggers: `diagnostic demarrage`, `le pc demarre lentement`, `demarrage lent`, `optimise le demarrage`, `pourquoi c'est lent`
  - Etapes:
    1. `bash_run` — Apps au demarrage
    1. `list_services` — Services actifs
    1. `system_info` — Diagnostic systeme
    1. `bash_run` — Espace disque
    1. `notify` — Notification
  - Taux succes: 100%

- **diagnostic_reseau_complet**
  - Description: Diagnostic reseau complet: IP, MAC, vitesse, tracert, netstat, DNS, ping
  - Triggers: `diagnostic reseau complet`, `analyse reseau complete`, `tout le reseau`, `deep network check`
  - Etapes:
    1. `network_info` — Infos reseau
    1. `bash_run` — Adaptateurs reseau
    1. `wifi_networks` — Reseaux Wi-Fi
    1. `ping` — Ping Google
    1. `bash_run` — Flush DNS
    1. `notify` — Notification
  - Taux succes: 100%

- **diagnostic_sante_pc**
  - Description: Diagnostic sante: CPU temp, uptime, espace disque, RAM, GPU
  - Triggers: `diagnostic sante`, `sante du pc`, `health check complet`, `comment va le pc`, `etat de sante`
  - Etapes:
    1. `system_info` — Infos systeme
    1. `gpu_info` — Infos GPU
    1. `bash_run` — Uptime
    1. `bash_run` — Espace disque
    1. `notify` — Notification
  - Taux succes: 100%

- **preparation_backup**
  - Description: Preparation sauvegarde: save tout, check espace, ouvre parametres backup
  - Triggers: `prepare le backup`, `preparation sauvegarde`, `avant la sauvegarde`, `pre-backup`
  - Etapes:
    1. `press_hotkey` — Sauvegarder fichier actif
    1. `bash_run` — Espace disque
    1. `system_info` — Check systeme
    1. `notify` — Notification
  - Taux succes: 100%

- **nettoyage_clipboard**
  - Description: Nettoyage complet: clipboard + temp + historique recent
  - Triggers: `nettoyage rapide`, `clean rapide`, `nettoie vite`, `nettoyage clipboard et temp`
  - Etapes:
    1. `bash_run` — Vider clipboard
    1. `bash_run` — Vider temp
    1. `notify` — Notification
  - Taux succes: 100%

- **inventaire_apps**
  - Description: Inventaire des applications installees et environnement dev
  - Triggers: `inventaire applications`, `quelles apps sont installees`, `liste toutes les applications`, `inventaire logiciels`
  - Etapes:
    1. `bash_run` — Apps installees
    1. `bash_run` — Versions dev
    1. `bash_run` — PATH
    1. `notify` — Notification
  - Taux succes: 100%

- **inventaire_hardware**
  - Description: Inventaire hardware complet: CPU, RAM, GPU, carte mere, BIOS, disques
  - Triggers: `inventaire hardware`, `specs completes`, `tout le hardware`, `details materiel`, `fiche technique pc`
  - Etapes:
    1. `bash_run` — CPU
    1. `bash_run` — RAM
    1. `gpu_info` — GPU
    1. `bash_run` — Carte mere
    1. `bash_run` — Disques
    1. `bash_run` — BIOS
    1. `notify` — Notification
  - Taux succes: 100%

- **check_performances**
  - Description: Check performances: CPU load, RAM, top processus, GPU temp
  - Triggers: `check performances`, `comment tourne le pc`, `performances`, `le pc rame`, `c'est lent`
  - Etapes:
    1. `bash_run` — CPU load
    1. `bash_run` — RAM
    1. `bash_run` — Top 5 RAM
    1. `gpu_info` — GPU
    1. `notify` — Notification
  - Taux succes: 100%

- **rapport_batterie**
  - Description: Rapport batterie complet: niveau, sante, estimation autonomie
  - Triggers: `rapport batterie`, `etat batterie complet`, `batterie detaillee`, `autonomie restante`, `check batterie`
  - Etapes:
    1. `bash_run` — Niveau batterie
    1. `bash_run` — Rapport batterie
    1. `notify` — Notification
  - Taux succes: 100%

- **audit_reseau**
  - Description: Audit reseau: IP publique, DNS, ports ouverts, ARP, vitesse
  - Triggers: `audit reseau`, `analyse le reseau`, `securite reseau`, `scan reseau complet`, `qui est sur mon reseau`
  - Etapes:
    1. `bash_run` — IP publique
    1. `network_info` — IP locale
    1. `bash_run` — Ports ouverts
    1. `bash_run` — Table ARP
    1. `bash_run` — Vitesse
    1. `notify` — Notification
  - Taux succes: 100%

- **optimise_dns**
  - Description: Optimisation DNS: flush + passage sur Cloudflare + test
  - Triggers: `optimise le dns`, `dns rapide`, `accelere le dns`, `internet lent`, `dns lent`
  - Etapes:
    1. `bash_run` — Flush DNS
    1. `bash_run` — DNS Cloudflare
    1. `ping` — Test connexion
    1. `notify` — Notification
  - Taux succes: 100%

- **diagnostic_connexion**
  - Description: Diagnostic connexion internet: ping, DNS, IP, vitesse, tracert
  - Triggers: `diagnostic connexion`, `internet ne marche pas`, `pas de connexion`, `probleme internet`, `debug internet`
  - Etapes:
    1. `bash_run` — Carte reseau
    1. `ping` — Ping Google DNS
    1. `bash_run` — Test DNS
    1. `bash_run` — IP publique
    1. `notify` — Notification
  - Taux succes: 100%

- **medic_repair**
  - Description: The Medic: Auto-reparation cluster — verifie et relance M1, M2, Ollama
  - Triggers: `medic`, `repare le cluster`, `auto reparation`, `le cluster est casse`, `relance les agents`, `repare les ia`
  - Etapes:
    1. `lm_cluster_status` — Check cluster complet
    1. `bash_run` — Check M1
    1. `bash_run` — Check M2
    1. `bash_run` — Check/Relance Ollama
    1. `notify` — Notification
  - Taux succes: 100%

- **sentinel_securite**
  - Description: The Sentinel: Scan ports ouverts, connexions actives, processus suspects
  - Triggers: `sentinel`, `scan de menaces`, `cyber defense`, `connexions suspectes`, `qui est connecte`, `scan securite reseau`
  - Etapes:
    1. `bash_run` — Ports en ecoute
    1. `bash_run` — Connexions externes
    1. `bash_run` — Regles pare-feu entrantes
    1. `notify` — Notification
  - Taux succes: 100%


### trading (4 skills)

- **mode_trading**
  - Description: Active le mode trading: ouvre Chrome sur les graphes, lance le scanner
  - Triggers: `mode trading`, `lance le trading`, `session trading`, `active le trading`, `demarre le trading`
  - Etapes:
    1. `app_open` — Ouvrir Chrome
    1. `open_url` — TradingView
    1. `trading_status` — Verifier le pipeline
    1. `lm_cluster_status` — Verifier le cluster IA
  - Taux succes: 100%

- **consensus_trading**
  - Description: Consensus multi-IA sur le marche crypto
  - Triggers: `consensus trading`, `avis du cluster`, `consensus crypto`, `que pensent les ia`, `analyse multi ia`
  - Etapes:
    1. `trading_status` — Status pipeline
    1. `consensus` — Consensus cluster
  - Taux succes: 100%

- **check_trading_complet**
  - Description: Check trading complet: status, positions, signaux, cluster, consensus
  - Triggers: `check trading complet`, `bilan trading`, `revue trading`, `analyse complete trading`, `tout le trading`
  - Etapes:
    1. `trading_status` — Status pipeline trading
    1. `trading_positions` — Positions ouvertes
    1. `trading_pending_signals` — Signaux en attente
    1. `lm_cluster_status` — Cluster IA
    1. `consensus` — Consensus multi-IA
  - Taux succes: 100%

- **preparation_trading_linux**
  - Description: Preparation trading Linux: check GPU temps, load models, cluster, TradingView, pipeline, connexions
  - Triggers: `prepare le trading`, `preparation trading`, `setup trading linux`, `lance la session trading linux`, `init trading`, `demarre le trading linux`, `pret pour le trading`
  - Etapes:
    1. `bash_run` — Verification temperatures GPU
    1. `lm_cluster_status` — Verification cluster IA
    1. `lm_load_model` — Chargement modele IA pour trading
    1. `open_url` — Ouvrir TradingView dans le navigateur
    1. `trading_pipeline_v2` — Demarrage pipeline trading V2
    1. `bash_run` — Verification connexions services
  - Taux succes: 100%


### utility (2 skills)

- **convert_units_linux**
  - Description: Convertir unités: température, taille fichier, monnaie, distance
  - Triggers: `convertis`, `conversion`, `combien fait`, `transforme en`, `calcule`
  - Etapes:
    1. `bash` — Aide conversion
  - Taux succes: 100%

- **calendar_time_linux**
  - Description: Date, heure, calendrier, timezone, timer, chronomètre
  - Triggers: `quelle heure est-il`, `quel jour sommes-nous`, `calendrier`, `date et heure`, `timezone`, `fuseau horaire`
  - Etapes:
    1. `bash` — Date et heure actuelles
    1. `bash` — Calendrier du mois
  - Taux succes: 100%


### voice (1 skills)

- **voice_test_linux**
  - Description: Test pipeline vocal: Vosk, Whisper, Piper TTS, microphone
  - Triggers: `teste la voix`, `test vocal`, `microphone marche`, `teste le micro`, `pipeline vocal`, `whisper fonctionne`
  - Etapes:
    1. `bash` — Détection microphone
    1. `bash` — Check Whisper
    1. `bash` — Check modèle Vosk
    1. `bash` — Check Piper TTS
    1. `bash` — Service vocal JARVIS
  - Taux succes: 100%


---

## Domino Pipelines (494 total)

### agile (3 dominos)

- **domino_sprint_review**
  - Description: Sprint review: weekly commits + stats + TODOs
  - Triggers: `sprint review`, `revue de sprint`, `sprint recap`, `bilan sprint detaille`

- **domino_agile_daily**
  - Description: Agile daily standup: yesterday + status + stats
  - Triggers: `daily agile`, `standup agile`, `matin agile`, `agile meeting`

- **domino_poc_start**
  - Description: POC start: check branch + environment
  - Triggers: `lance un poc`, `proof of concept`, `prototype rapide`, `poc start`


### ai_ml (5 dominos)

- **domino_ml_setup**
  - Description: ML setup check: PyTorch + GPU availability
  - Triggers: `setup ml`, `machine learning setup`, `prepare le ml`, `check ml`

- **domino_model_info**
  - Description: Model info: Ollama + LM Studio
  - Triggers: `info modeles`, `model info`, `details modeles`, `modeles charges`

- **domino_llm_status**
  - Description: LLM status: Ollama + LM Studio model counts
  - Triggers: `statut llm`, `modeles ia`, `ia status`, `llm overview`

- **domino_embedding_pipeline**
  - Description: Embedding pipeline: check M1 readiness
  - Triggers: `pipeline embedding`, `genere embeddings`, `vectorise`, `embedding batch`

- **domino_model_compare**
  - Description: Compare models: Ollama + LM Studio side by side
  - Triggers: `compare les modeles`, `model compare`, `benchmark modeles`, `quel modele`


### ai_orchestration (3 dominos)

- **domino_consensus_smart**
  - Description: Consensus intelligent: interroger M1+M2+OL1, vote pondere, synthese
  - Triggers: `consensus intelligent`, `avis du cluster`, `vote des modeles`

- **domino_model_hot_swap**
  - Description: Hot-swap modele: detecter latence, charger alternative, migrer trafic
  - Triggers: `change de modele`, `swap le modele`, `echange de modele`

- **domino_auto_benchmark**
  - Description: Auto-benchmark: tester tous noeuds, scorer, mettre a jour routing
  - Triggers: `benchmark automatique`, `teste tous les noeuds`, `benchmark cluster`


### api (1 dominos)

- **domino_graphql_check**
  - Description: GraphQL library check
  - Triggers: `check graphql`, `graphql status`, `verifie graphql`, `api graphql`


### api_testing (1 dominos)

- **domino_api_health**
  - Description: Health check all local APIs (M1 + OL1)
  - Triggers: `sante api`, `api health`, `check tous les endpoints`, `healthcheck api`


### architecture (1 dominos)

- **domino_architecture_review**
  - Description: Architecture review: LOC + categories + project summary
  - Triggers: `review architecture`, `archi review`, `revue architecture`, `check archi`


### automation (13 dominos)

- **domino_auto_commit**
  - Description: Auto commit: git add + commit avec timestamp
  - Triggers: `auto commit`, `commite automatiquement`, `sauvegarde le code`

- **domino_auto_push**
  - Description: Git push: verifier status + push
  - Triggers: `pousse le code`, `git push`, `envoie sur github`

- **domino_session_save**
  - Description: Sauvegarder la session: state + git snapshot
  - Triggers: `sauvegarde la session`, `save session`, `snapshot session`

- **domino_auto_screenshot**
  - Description: Capture ecran avec OCR optionnel
  - Triggers: `capture ecran`, `screenshot`, `prends une capture`, `fais un screenshot`, `capture l'ecran`, ``

- **domino_auto_clipboard_history**
  - Description: Historique du presse-papiers avec sauvegarde
  - Triggers: `historique presse-papiers`, `clipboard history`, `qu'est-ce que j'ai copie`, `historique copier coller`, `dernieres copies`, ``

- **domino_auto_file_organize**
  - Description: Organise le dossier Telechargements par type de fichier
  - Triggers: `organise les telechargements`, `range le dossier`, `file organize`, `trie les fichiers`, `nettoyage telechargements`, `organise les fichiers`, ``

- **domino_auto_wallpaper**
  - Description: Change le fond d'ecran avec une image aleatoire
  - Triggers: `change le fond d'ecran`, `nouveau wallpaper`, `wallpaper jarvis`, `change le papier peint`, `fond d'ecran aleatoire`, ``

- **domino_auto_notification_digest**
  - Description: Resume des notifications recentes
  - Triggers: `resume des notifications`, `notification digest`, `recap notifs`, `quelles notifications`, `montre les notifs`, ``

- **domino_auto_browser_tabs**
  - Description: Lister et compter les onglets navigateur ouverts
  - Triggers: `liste les onglets`, `combien d'onglets`, `browser tabs`, `ferme les onglets`, `gere les onglets`, `onglets ouverts`, ``

- **domino_auto_pdf_extract**
  - Description: Extraire le texte du PDF le plus recent
  - Triggers: `extrais le pdf`, `texte du pdf`, `pdf extract`, `lis le pdf`, `convertis le pdf en texte`, ``

- **domino_auto_compress**
  - Description: Compresser le projet JARVIS en archive tar.gz
  - Triggers: `compresse le dossier`, `fais une archive`, `compress`, `zip le dossier`, `tar le dossier`, `archive le dossier`, ``

- **domino_auto_sync_github**
  - Description: Synchroniser tous les repos Git sous /home/turbo
  - Triggers: `sync github`, `synchronise les repos`, `github sync`, `pull tous les repos`, `mets a jour les repos`, `git pull all`, ``

- **domino_auto_cron_audit**
  - Description: Audit complet des taches planifiees: cron, systemd timers, at
  - Triggers: `audit les crons`, `cron audit`, `quels crons tournent`, `verifie les taches planifiees`, `liste les crons`, ``


### backup_chain (6 dominos)

- **domino_backup_complet**
  - Description: Backup complet: DB + config + git bundle + verification
  - Triggers: `backup complet`, `sauvegarde totale`, `backup tout`

- **domino_backup_quick**
  - Description: Backup rapide: etoile.db seulement
  - Triggers: `backup rapide`, `sauvegarde rapide`, `quick backup`

- **domino_backup_restore**
  - Description: Restauration: lister + confirmer + restaurer + verifier integrite
  - Triggers: `restaure le backup`, `restore backup`, `recupere la sauvegarde`

- **domino_backup_full_system**
  - Description: Full system backup: all DBs + git commit
  - Triggers: `backup complet du systeme`, `sauvegarde totale`, `backup full`, `backup tout`

- **domino_emergency_save**
  - Description: Emergency save: instant commit + push + backup
  - Triggers: `sauvegarde urgence`, `emergency save`, `sauve tout vite`, `urgence backup`

- **domino_backup_incremental**
  - Description: Incremental backup: DB + git commit
  - Triggers: `backup incremental`, `sauvegarde rapide`, `quick backup`, `backup partiel`


### cache (2 dominos)

- **domino_redis_check**
  - Description: Redis connectivity check
  - Triggers: `check redis`, `redis status`, `teste redis`, `redis ping`

- **domino_cache_stats**
  - Description: Cache statistics overview
  - Triggers: `stats cache`, `cache status`, `statistiques cache`, `cache info`


### ci_cd (5 dominos)

- **domino_build_check**
  - Description: Full build check: syntax + imports verification
  - Triggers: `check build`, `verify build`, `est ce que ca compile`, `build status`

- **domino_ci_pipeline_check**
  - Description: Check CI pipeline: syntax + recent commits + counts
  - Triggers: `check ci`, `statut pipeline`, `ci pipeline`, `check build`

- **domino_deploy_staging**
  - Description: Deploy to staging: syntax check + commit + push
  - Triggers: `deploy staging`, `deploie staging`, `mise en staging`, `push staging`

- **domino_rollback_last**
  - Description: Rollback preparation: show last commits + diff stats
  - Triggers: `rollback`, `annuler dernier commit`, `revert dernier`, `git rollback`

- **domino_feature_flags**
  - Description: Scan feature flags in env and config files
  - Triggers: `feature flags`, `flags actifs`, `toggle features`, `activer feature`


### cloud (5 dominos)

- **domino_cloud_storage**
  - Description: Cloud storage check (S3 + MinIO)
  - Triggers: `check cloud storage`, `storage overview`, `stockage cloud`, `cloud storage`

- **domino_s3_usage**
  - Description: S3 storage usage overview
  - Triggers: `usage s3`, `s3 usage`, `espace s3`, `s3 disk usage`

- **domino_serverless_check**
  - Description: Serverless tools check
  - Triggers: `check serverless`, `serverless status`, `faas check`, `fonctions cloud`

- **domino_lambda_deploy**
  - Description: AWS Lambda deployment check
  - Triggers: `deploie lambda`, `lambda deploy`, `deploy lambda function`, `aws lambda deploy`

- **domino_vercel_preview**
  - Description: Vercel preview deployment check
  - Triggers: `preview vercel`, `vercel preview`, `deploie preview`, `vercel dev`


### cloud_infra (1 dominos)

- **domino_cloud_overview**
  - Description: Cloud infrastructure overview: APIs + disk + databases
  - Triggers: `statut cloud`, `cloud overview`, `infra cloud`, `resume cloud`


### cluster (15 dominos)

- **domino_quick_health**
  - Description: Health check rapide 3 steps: M1 + OL1 + GPU
  - Triggers: `health check rapide`, `tout va bien`, `check rapide`

- **domino_model_benchmark**
  - Description: Benchmark rapide M1 + OL1
  - Triggers: `benchmark modele`, `teste le modele`, `vitesse modele`

- **domino_api_latency_test**
  - Description: Test de latence API sur tous les noeuds
  - Triggers: `test latence api`, `ping les apis`, `latence des noeuds`

- **domino_cluster_monitor**
  - Description: Monitoring complet: M1 + OL1 + WS + GPU temperature
  - Triggers: `monitore le cluster`, `status cluster complet`, `check tous les noeuds`, `surveillance cluster`

- **domino_resource_allocation**
  - Description: Affiche la repartition des ressources et charges entre les noeuds
  - Triggers: `allocation des ressources`, `repartition cluster`, `charge des noeuds`, `qui fait quoi`, `resource allocation`

- **domino_cluster_rebalance**
  - Description: Reequilibrer la charge entre les noeuds du cluster
  - Triggers: `reequilibre le cluster`, `cluster rebalance`, `balance la charge`, `redistribue la charge`, `rebalance les noeuds`, ``

- **domino_cluster_model_swap**
  - Description: Lister et preparer le swap de modele IA sur le cluster
  - Triggers: `change le modele`, `swap le modele`, `model swap`, `remplace le modele`, `charge un autre modele`, ``

- **domino_cluster_benchmark**
  - Description: Benchmark complet du cluster: GPU, CPU, disque, reseau, memoire
  - Triggers: `benchmark le cluster`, `teste les performances cluster`, `cluster benchmark`, `benchmark tous les noeuds`, `performance cluster`, ``

- **domino_cluster_sync_configs**
  - Description: Synchroniser les configs de M1 vers M2/M3 via rsync
  - Triggers: `synchronise les configs`, `sync configs cluster`, `config sync`, `propage la config`, `deploie la config sur le cluster`, ``

- **domino_cluster_failover_test**
  - Description: Tester le failover entre noeuds du cluster
  - Triggers: `teste le failover`, `failover test`, `test basculement`, `simule une panne`, `teste la resilience`, ``

- **domino_cluster_vram_report**
  - Description: Rapport detaille VRAM: par GPU, par process, cluster entier
  - Triggers: `rapport vram`, `vram report`, `combien de vram`, `memoire gpu detaillee`, `vram disponible`, `etat de la vram`, ``

- **domino_cluster_latency_test**
  - Description: Tester les latences entre tous les noeuds du cluster
  - Triggers: `teste les latences`, `latency test`, `ping les noeuds`, `temps de reponse cluster`, `latence inter-noeuds`, ``

- **domino_cluster_restart_all**
  - Description: Redemarrer et verifier tous les services du cluster
  - Triggers: `redemarre tout le cluster`, `cluster restart`, `relance tous les services`, `restart all`, `redemarre les services cluster`, ``

- **domino_cluster_backup_models**
  - Description: Inventaire et preparation backup des modeles IA
  - Triggers: `backup les modeles`, `sauvegarde les modeles ia`, `model backup`, `copie les modeles`, `archive les modeles`, ``

- **domino_cluster_optimize_routing**
  - Description: Analyser et optimiser le routage des requetes sur le cluster
  - Triggers: `optimise le routage`, `routing optimize`, `ameliore le routage`, `optimise les requetes cluster`, `smart routing`, ``


### cluster_management (2 dominos)

- **domino_bilan_cluster_complet**
  - Description: Bilan complet: health check 4 noeuds + GPU details + VRAM
  - Triggers: `bilan cluster complet`, `rapport cluster`, `etat complet du cluster`

- **domino_cluster_rebalance**
  - Description: Analyser la charge du cluster pour reequilibrage
  - Triggers: `reequilibre le cluster`, `cluster rebalance`, `redistribue les modeles`


### code_generation (4 dominos)

- **domino_code_scaffold**
  - Description: Scaffold projet: verifier outils disponibles
  - Triggers: `scaffold un projet`, `cree un nouveau projet`, `initialise un repo`

- **domino_code_review_auto**
  - Description: Review auto: git diff + TODO count
  - Triggers: `revue de code`, `review le code`, `analyse le code recent`

- **domino_code_lint**
  - Description: Lint check: syntaxe Python + imports
  - Triggers: `lance le linter`, `verifie la qualite du code`, `lint le code`

- **domino_code_review**
  - Description: Code review: git status + diff + syntax check
  - Triggers: `revue de code`, `code review`, `review le code`, `analyse le code`


### code_quality (2 dominos)

- **domino_tech_debt_audit**
  - Description: Tech debt audit: TODOs + LOC count
  - Triggers: `audit dette technique`, `tech debt audit`, `montre les todos`, `code a ameliorer`

- **domino_code_quality**
  - Description: Code quality check: lint + syntax + LOC
  - Triggers: `qualite du code`, `code quality`, `lint et format`, `verifie le code`


### collaboration (8 dominos)

- **domino_collab_sync_cluster**
  - Description: Sync cluster: verifier tous les noeuds + rapport
  - Triggers: `synchronise le cluster`, `sync toutes les machines`, `cluster sync`

- **domino_collab_share_model**
  - Description: Partage modele: check local + cible VRAM + transfert config
  - Triggers: `partage le modele`, `distribue sur le cluster`, `model sharing`

- **domino_collab_consensus**
  - Description: Consensus: interroger M1+M2+OL1 + vote pondere
  - Triggers: `lance un consensus`, `vote multi agents`, `consensus cluster`

- **domino_collab_overview**
  - Description: Collaboration overview: contributors + branches + tags
  - Triggers: `overview collaboration`, `collaboration status`, `equipe status`, `collab overview`

- **domino_end_of_sprint**
  - Description: End of sprint review: weekly commits + stats + DB counts
  - Triggers: `fin de sprint`, `sprint review`, `cloture sprint`, `bilan sprint`

- **domino_standup_report**
  - Description: Daily standup: commits today + voice stats + cluster health
  - Triggers: `standup`, `daily standup`, `rapport standup`, `daily report`

- **domino_pull_request_prep**
  - Description: PR preparation: branch + diff + log + syntax check
  - Triggers: `prepare pr`, `pull request`, `prepare merge`, `pr prep`

- **domino_collab_sync**
  - Description: Sync project: fetch + status + check if behind
  - Triggers: `sync projet`, `synchroniser`, `git sync`, `mettre a jour projet`


### communication (3 dominos)

- **domino_messaging_status**
  - Description: Messaging apps status check
  - Triggers: `statut messaging`, `messaging check`, `communication status`, `apps communication`

- **domino_email_setup**
  - Description: Email setup check: SMTP module
  - Triggers: `setup email`, `configure email`, `smtp setup`, `email config`

- **domino_telegram_command**
  - Description: Execute une commande via le routeur Telegram
  - Triggers: `commande telegram`, `telegram command`, `envoie commande`


### containers (4 dominos)

- **domino_docker_overview**
  - Description: Docker complete overview: containers + images + volumes
  - Triggers: `overview docker`, `resume docker`, `docker resume`, `etat docker`

- **domino_docker_cleanup**
  - Description: Docker disk usage check before cleanup
  - Triggers: `clean docker`, `nettoie docker`, `docker prune`, `purge docker`

- **domino_container_health**
  - Description: Container health check with resource usage
  - Triggers: `sante containers`, `container health`, `check containers`, `docker health`

- **domino_docker_overview**
  - Description: Docker overview: running containers + images
  - Triggers: `statut docker`, `docker overview`, `containers actifs`, `docker status`


### data_analysis (9 dominos)

- **domino_db_export_csv**
  - Description: Export etoile.db vers CSV
  - Triggers: `exporte la base en csv`, `export csv`, `sauvegarde csv`

- **domino_db_row_count**
  - Description: Comptage lignes: etoile + jarvis + sniper
  - Triggers: `combien de lignes en base`, `comptage base`, `stats base de donnees`

- **domino_log_analysis**
  - Description: Analyse logs: erreurs recentes + taille fichiers log
  - Triggers: `analyse les logs`, `check les logs`, `log analysis`

- **domino_analytics_usage**
  - Description: Analytics: top commandes + stats DB jarvis
  - Triggers: `statistiques d'utilisation`, `analytics`, `quelles commandes j'utilise`

- **domino_db_optimize**
  - Description: DB optimize: VACUUM + ANALYZE sur toutes les bases
  - Triggers: `optimise les bases`, `db optimize`, `optimise la base`, `performance base`

- **domino_data_export_full**
  - Description: Full data export: all databases to CSV
  - Triggers: `exporte toutes les donnees`, `data export full`, `export complet`, `exporte tout en csv`

- **domino_db_migration**
  - Description: DB migration prep: backup + integrity check
  - Triggers: `migration de base`, `db migration`, `migre les donnees`, `database migration`

- **domino_db_integrity_check**
  - Description: DB integrity check: PRAGMA integrity_check on all DBs
  - Triggers: `verifie l'integrite`, `integrity check`, `check les bases`, `integrite des bases`

- **domino_voice_history_export**
  - Description: Voice history export: full stats dump
  - Triggers: `exporte l'historique vocal`, `voice history export`, `sauvegarde les commandes vocales`


### data_management (1 dominos)

- **domino_data_overview**
  - Description: Data overview: DB counts + JSON validation + disk
  - Triggers: `donnees overview`, `data overview`, `resume donnees`, `statut des donnees`


### data_pipeline (3 dominos)

- **domino_etl_complet**
  - Description: ETL complet: extract DB -> transform -> load -> verify
  - Triggers: `lance l'ETL`, `extraction donnees`, `pipeline de donnees`

- **domino_log_rotate**
  - Description: Rotation logs: collecter, archiver >7j, purger, rapport
  - Triggers: `rotation des logs`, `nettoie les logs`, `archive les logs`

- **domino_cache_refresh**
  - Description: Refresh cache: vider, reconstruire index, pre-charger
  - Triggers: `rafraichis le cache`, `vide le cache`, `rebuild le cache`


### data_validation (1 dominos)

- **domino_json_validate**
  - Description: Validate all JSON files in data directory
  - Triggers: `valide les json`, `check json`, `json valides`, `verifie les json`


### database (6 dominos)

- **domino_orm_overview**
  - Description: ORM tools overview: SQLAlchemy + Prisma
  - Triggers: `overview orm`, `check orm`, `orm status`, `database orm`

- **domino_migration_run**
  - Description: Database migration framework detection
  - Triggers: `lance les migrations`, `run migration`, `database migrate`, `migration`

- **domino_db_health**
  - Description: Database health check (SQLite)
  - Triggers: `sante base de donnees`, `database health`, `check db`, `sante db`

- **domino_sql_audit**
  - Description: SQL audit: table counts + integrity check
  - Triggers: `audit sql`, `sql audit`, `verifie les bases`, `database audit`

- **domino_db_vacuum_all**
  - Description: Vacuum all SQLite databases
  - Triggers: `vacuum toutes les bases`, `vacuum all`, `optimise les bases`, `compacte les databases`

- **domino_schema_check**
  - Description: Show database schema and table counts
  - Triggers: `schema base`, `montre le schema`, `tables database`, `structure base`


### debug_cascade (5 dominos)

- **domino_debug_cluster**
  - Description: Debug cluster: ping tous les noeuds + rapport
  - Triggers: `debug cluster`, `probleme cluster`, `cluster en panne`

- **domino_debug_gpu_thermal**
  - Description: Debug thermal GPU: temperatures + ventilateurs + throttle auto
  - Triggers: `debug gpu chaud`, `gpu surchauffe`, `thermal throttle`

- **domino_debug_network**
  - Description: Debug reseau complet: gateway + internet + DNS + cluster LAN
  - Triggers: `debug reseau`, `probleme connexion`, `reseau en panne`

- **domino_debug_db**
  - Description: Debug DB: integrite + taille + comptages + vacuum conditionnel
  - Triggers: `debug base de donnees`, `probleme database`, `check database`

- **domino_debug_api_cascade**
  - Description: Debug API: health check tous endpoints cluster + n8n
  - Triggers: `debug api`, `api en panne`, `test tous les endpoints`


### debugging (1 dominos)

- **domino_debug_session**
  - Description: Debug session start: errors + syntax + match test
  - Triggers: `session debug`, `debug session`, `commence le debug`, `debug mode`


### dependencies (4 dominos)

- **domino_pkg_audit**
  - Description: Package audit: pip + npm outdated
  - Triggers: `audit packages`, `check packages`, `packages audit`, `audit dependances`

- **domino_pkg_managers**
  - Description: All package managers check
  - Triggers: `check package managers`, `gestionnaires de paquets`, `pkg managers`, `all package managers`

- **domino_conda_envs**
  - Description: Conda environments list
  - Triggers: `conda envs`, `environnements conda`, `conda environments`, `liste conda`

- **domino_dependency_tree**
  - Description: Dependency tree overview
  - Triggers: `arbre dependances`, `dependency tree`, `deps tree`, `arbre des deps`


### deploy_flow (4 dominos)

- **domino_deploy_standard**
  - Description: Deploy standard: status + tests + commit + push
  - Triggers: `deploie le code`, `deploy standard`, `push en production`

- **domino_deploy_hotfix**
  - Description: Hotfix rapide: stash + fix + commit + push
  - Triggers: `hotfix urgent`, `deploy hotfix`, `correction urgente`

- **domino_deploy_rollback**
  - Description: Rollback: revert dernier commit + push
  - Triggers: `rollback deploy`, `annule le dernier deploy`, `reviens en arriere`

- **domino_deploy_with_backup**
  - Description: Deploy securise: backup DB + config + tests + commit + push
  - Triggers: `deploy avec backup`, `deploie en securite`, `deploy safe`


### deployment (4 dominos)

- **domino_helm_deploy**
  - Description: Helm chart deployment overview
  - Triggers: `deploie helm`, `helm deploy`, `helm install`, `install chart`

- **domino_hotfix_deploy**
  - Description: Hotfix preparation with syntax check
  - Triggers: `hotfix`, `deploie le hotfix`, `hot fix urgent`, `patch urgent`

- **domino_canary_deploy**
  - Description: Canary deploy preparation: syntax + test
  - Triggers: `canary deploy`, `deploie en canary`, `deploy canary`, `test en canary`

- **domino_deploy_full**
  - Description: Full deployment: syntax + add + push
  - Triggers: `deploiement complet`, `full deploy`, `deploy tout`, `mise en prod complete`


### desktop_control (2 dominos)

- **ferme_fenetre**
  - Description: Ferme la fenêtre active
  - Triggers: `ferme la fenetre`, `ferme cette fenetre`, `quitte la fenetre`

- **capture_ecran**
  - Description: Prend une capture d'écran et l'enregistre sur le bureau
  - Triggers: `prends une capture d'ecran`, `fais un screenshot`, `capture l'ecran`


### dev (11 dominos)

- **domino_git_status_complet**
  - Description: Statut git complet: status + log 10 + branches
  - Triggers: `statut git complet`, `git status complet`, `etat du repo`

- **domino_dev_git_cleanup**
  - Description: Nettoyage complet Git: prune branches mergees, gc agressif, fsck
  - Triggers: `nettoie git`, `nettoyage git`, `clean les branches`, `purge git`, `fais le menage git`, `git cleanup`, ``

- **domino_dev_docker_rebuild**
  - Description: Rebuild complet des containers Docker JARVIS
  - Triggers: `rebuild docker`, `reconstruis les containers`, `docker rebuild`, `relance docker`, `rebuild les images jarvis`, ``

- **domino_dev_test_all**
  - Description: Lance tous les tests pytest avec couverture
  - Triggers: `lance les tests`, `run tous les tests`, `pytest complet`, `teste tout`, `lance pytest`, `verification tests`, ``

- **domino_dev_lint_fix**
  - Description: Ruff check + fix + format sur tout le code source
  - Triggers: `lint et fix`, `corrige le code`, `ruff fix`, `lance le linter`, `verifie le style`, `nettoyage code`, ``

- **domino_dev_venv_rebuild**
  - Description: Reconstruction complete du virtualenv Python
  - Triggers: `recree le venv`, `rebuild virtualenv`, `reinstalle le venv`, `nouveau virtualenv`, `venv propre`, ``

- **domino_dev_pip_audit**
  - Description: Audit securite pip: vulnerabilites + paquets obsoletes
  - Triggers: `audit pip`, `verifie les vulnerabilites`, `securite pip`, `pip audit`, `check les deps`, `vulnerabilites python`, ``

- **domino_dev_code_stats**
  - Description: Statistiques code: lignes, fichiers, modules, TODOs
  - Triggers: `stats du code`, `combien de lignes`, `statistiques code`, `metriques code`, `code stats`, `taille du projet`, ``

- **domino_dev_db_migrate**
  - Description: Backup + optimize de la base SQLite JARVIS
  - Triggers: `migre la base`, `migration database`, `backup et migre`, `db migrate`, `sauvegarde et migre la base`, ``

- **domino_dev_log_analyze**
  - Description: Analyse des logs d'erreur systeme et JARVIS des 24 dernieres heures
  - Triggers: `analyse les logs`, `erreurs des logs`, `log analyze`, `resume des erreurs`, `qu'est-ce qui a plante`, `check les logs`, ``

- **domino_dev_profile_perf**
  - Description: Profiling Python: CPU, imports, memoire, IO
  - Triggers: `profile les performances`, `profiling python`, `benchmark python`, `mesure les perfs`, `performance profiling`, `analyse performances`, ``


### dev_environment (4 dominos)

- **domino_all_languages**
  - Description: All language versions: Python + Node + Rust + Go + Git
  - Triggers: `tous les langages`, `versions langages`, `programming languages`, `check langages`

- **domino_linux_tools**
  - Description: Check available shell/Linux tools
  - Triggers: `outils linux`, `linux tools`, `check outils shell`, `shell tools`

- **domino_ide_setup**
  - Description: IDE setup check: extensions + Python version
  - Triggers: `configure ide`, `setup vscode`, `prepare l'editeur`, `ide setup`

- **domino_workspace_reset**
  - Description: Reset workspace: clear caches + check git status
  - Triggers: `reset workspace`, `nettoie l'espace de travail`, `workspace propre`, `clean workspace`


### dev_tools (1 dominos)

- **domino_regex_playground**
  - Description: Regex playground: demo pattern matching
  - Triggers: `playground regex`, `teste regex`, `regex sandbox`, `expression reguliere`


### dev_workflow (21 dominos)

- **domino_code_review_complet**
  - Description: Code review: git diff + lint + type check + tests rapides
  - Triggers: `code review complet`, `revue de code`, `review le code`

- **domino_git_log_visual**
  - Description: Historique git visuel: graph + top authors
  - Triggers: `historique git`, `log git`, `montre les commits`

- **domino_deploy_staging**
  - Description: Deploy staging: syntax check + commit + push
  - Triggers: `deploie en staging`, `deploy staging`, `push staging`, `envoie en staging`

- **domino_git_cleanup**
  - Description: Git cleanup: prune remote + list merged + gc
  - Triggers: `nettoie git`, `git cleanup`, `clean les branches`, `menage git`

- **domino_update_deps**
  - Description: Update deps: check outdated + uv sync
  - Triggers: `mets a jour les dependances`, `update deps`, `upgrade packages`, `mise a jour pip`

- **domino_docker_status**
  - Description: Docker status: containers + images
  - Triggers: `statut docker`, `docker status`, `conteneurs actifs`, `docker ps`

- **domino_project_stats**
  - Description: Project stats: line count + file count + git commits
  - Triggers: `stats du projet`, `statistiques projet`, `project stats`, `combien de lignes`

- **domino_dev_setup**
  - Description: Dev setup: git status + uv sync + cluster check
  - Triggers: `prepare le dev`, `setup dev`, `prepare l'environnement`, `init workspace`

- **domino_pip_upgrade_all**
  - Description: Pip upgrade: list outdated packages
  - Triggers: `upgrade tous les packages`, `pip upgrade all`, `mets tout a jour pip`, `upgrade pip`

- **domino_git_stash_pop**
  - Description: Git stash pop: restore stashed work
  - Triggers: `recupere le stash`, `stash pop`, `git stash pop`, `reprends le travail`

- **domino_git_revert**
  - Description: Git revert prep: show last commits before reverting
  - Triggers: `annule le dernier commit`, `git revert`, `reviens en arriere`, `undo commit`

- **domino_git_stats_detailed**
  - Description: Git stats detailed: commits + branches + files
  - Triggers: `statistiques git`, `git stats`, `stats du repo`, `contributions git`

- **domino_dev_reset**
  - Description: Dev reset: clean git + clear caches + sync deps
  - Triggers: `reset dev`, `remet l'environnement`, `clean dev`, `fresh start dev`

- **domino_commit_deploy**
  - Description: Commit and deploy: syntax check + commit + push
  - Triggers: `commit et deploie`, `commit and deploy`, `save and deploy`, `deploy le code`

- **domino_dependency_audit**
  - Description: Dependency audit: outdated + conflicts check
  - Triggers: `audit des dependances`, `dependency audit`, `check les deps`, `verifie les dependances`

- **domino_quick_save**
  - Description: Quick save: instant git add + commit
  - Triggers: `sauvegarde rapide`, `quick save`, `save vite`, `save rapide`

- **domino_release_prep**
  - Description: Release prep: syntax + tests + stats + git status
  - Triggers: `prepare la release`, `release prep`, `prepare le deploiement`, `pre release`

- **domino_git_branch_cleanup**
  - Description: Branch cleanup: list + merged check + prune
  - Triggers: `nettoie les branches`, `branch cleanup`, `supprime les vieilles branches`, `prune branches`

- **domino_quick_fix**
  - Description: Quick fix: syntax check + diff
  - Triggers: `quick fix`, `correction rapide`, `fix rapide`, `repare vite`

- **domino_workspace_stats**
  - Description: Workspace stats: lines + files + git size + data size
  - Triggers: `stats du workspace`, `workspace stats`, `taille du projet`, `project size`

- **domino_container_logs**
  - Description: Container logs: list + recent logs
  - Triggers: `logs docker`, `container logs`, `logs des conteneurs`, `docker logs`


### devops (4 dominos)

- **domino_ci_overview**
  - Description: CI/CD overview with GitHub Actions
  - Triggers: `overview ci`, `ci overview`, `ci cd status`, `pipelines ci`

- **domino_argocd_apps**
  - Description: ArgoCD applications list
  - Triggers: `argocd apps`, `liste argocd`, `applications argocd`, `argo apps`

- **domino_gh_actions_run**
  - Description: GitHub Actions workflow list
  - Triggers: `lance github actions`, `run gh actions`, `trigger workflow`, `github workflow run`

- **domino_jenkins_build**
  - Description: Jenkins build status
  - Triggers: `jenkins build`, `lance jenkins`, `build jenkins`, `jenkins job`


### documentation (7 dominos)

- **domino_doc_stats**
  - Description: Stats projet: fichiers Python, lignes, commits
  - Triggers: `statistiques du projet`, `stats jarvis`, `resume du projet`

- **domino_doc_changelog**
  - Description: Changelog: commits recents + fichiers modifies
  - Triggers: `genere le changelog`, `historique des changements`, `quoi de neuf`

- **domino_weekly_report**
  - Description: Rapport hebdo: commits semaine + diff stats + DB counts
  - Triggers: `rapport hebdomadaire`, `bilan de la semaine`, `weekly report`

- **domino_changelog_gen**
  - Description: Changelog: recent commits + tags
  - Triggers: `genere le changelog`, `changelog`, `quoi de neuf`, `what's new`

- **domino_docs_build**
  - Description: Documentation tools check (Sphinx + MkDocs)
  - Triggers: `build docs`, `genere la doc`, `documentation build`, `compile docs`

- **domino_swagger_api**
  - Description: Swagger/OpenAPI documentation check
  - Triggers: `swagger api`, `ouvre swagger`, `api documentation`, `swagger docs`

- **domino_readme_check**
  - Description: README.md existence and size check
  - Triggers: `check readme`, `readme status`, `verifie le readme`, `readme ok`


### emergency_protocol (3 dominos)

- **domino_emergency_gpu_kill**
  - Description: Urgence GPU: lister processus CUDA
  - Triggers: `urgence gpu`, `kill tous les gpu`, `gpu emergency stop`

- **domino_emergency_backup**
  - Description: Evacuation donnees: verifier statut git
  - Triggers: `evacuation donnees`, `backup urgence`, `sauvegarde d'urgence`

- **domino_emergency_survival**
  - Description: Mode survie: identifier processus lourds
  - Triggers: `mode survie`, `survival mode`, `mode minimal`


### frontend (4 dominos)

- **domino_state_mgmt**
  - Description: State management libraries check
  - Triggers: `check state management`, `state mgmt`, `gestion d'etat`, `state overview`

- **domino_frontend_build**
  - Description: Frontend build environment check
  - Triggers: `build frontend`, `frontend build`, `compile le frontend`, `build le front`

- **domino_storybook_launch**
  - Description: Storybook availability check
  - Triggers: `lance storybook`, `ouvre storybook`, `storybook dev`, `demarre storybook`

- **domino_build_tools_audit**
  - Description: Build tools audit: Node + Vite + esbuild
  - Triggers: `audit build tools`, `check build tools`, `outils de build`, `build audit`


### frontend_dev (4 dominos)

- **domino_typescript_check**
  - Description: TypeScript compilation check
  - Triggers: `check typescript`, `tsc check`, `compile typescript`, `typescript valide`

- **domino_react_setup**
  - Description: React setup check: Node + NPM versions
  - Triggers: `setup react`, `prepare react`, `init react`, `nouveau projet react`

- **domino_frontend_full**
  - Description: Full frontend audit: Node + npm + TypeScript
  - Triggers: `check frontend complet`, `frontend full`, `audit frontend`, `verifie le frontend`

- **domino_tailwind_setup**
  - Description: Tailwind CSS setup check
  - Triggers: `setup tailwind`, `init tailwind`, `configure tailwind`, `tailwind css`


### full_diagnostics (1 dominos)

- **domino_full_diagnostic**
  - Description: Complete diagnostic: syntax + cluster + RAM + disk + DB + project + git
  - Triggers: `diagnostic complet`, `full diagnostic`, `check tout`, `diagnostic total`


### gaming_dev (1 dominos)

- **domino_game_dev_setup**
  - Description: Game dev setup: GPU check
  - Triggers: `setup game dev`, `prepare game dev`, `environnement jeu`, `game development`


### git_advanced (2 dominos)

- **domino_git_deep_status**
  - Description: Deep git status: status + stash + branches + tags + log
  - Triggers: `statut git complet`, `git deep status`, `git avance`, `resume git detaille`

- **domino_git_recovery**
  - Description: Git recovery tools: reflog + stash list
  - Triggers: `recovery git`, `recupere le code`, `git reflog`, `annuler git`


### gpu (1 dominos)

- **domino_vram_cleanup**
  - Description: Nettoyer la VRAM en killant les processus idle
  - Triggers: `libere la vram`, `nettoie la vram`, `optimise la vram`


### gpu_monitoring (1 dominos)

- **domino_gpu_vram**
  - Description: Detailed GPU VRAM usage
  - Triggers: `vram detaillee`, `gpu vram`, `memoire gpu detaillee`, `nvidia vram`


### gpu_thermal (3 dominos)

- **domino_gpu_monitor_full**
  - Description: Monitoring GPU complet: metriques + processus + evaluation IA
  - Triggers: `monitore les gpu`, `status gpu complet`, `thermal gpu`

- **domino_gpu_optimize**
  - Description: Optimisation GPU: check VRAM + kill idle + verification
  - Triggers: `optimise les gpu`, `libere la vram`, `gpu optimization`

- **domino_gpu_emergency**
  - Description: Urgence GPU: lire temps + kill + reduire puissance
  - Triggers: `urgence gpu`, `gpu critical`, `surchauffe critique`


### hardware (5 dominos)

- **domino_hardware_audit**
  - Description: Hardware audit: CPU + GPU + RAM + disk
  - Triggers: `audit hardware`, `hardware check`, `verification materiel`, `check composants`

- **domino_thermal_check**
  - Description: Thermal check: GPU temperatures
  - Triggers: `check thermique`, `temperatures`, `thermal check`, `chauffe`

- **domino_usb_check**
  - Description: Check connected USB devices
  - Triggers: `check usb`, `peripheriques usb`, `usb connectes`, `liste usb`

- **domino_driver_check**
  - Description: Check installed device drivers
  - Triggers: `check drivers`, `verification drivers`, `pilotes installes`, `drivers status`

- **domino_bios_info**
  - Description: BIOS/UEFI information
  - Triggers: `info bios`, `bios check`, `uefi info`, `firmware check`


### incident (1 dominos)

- **domino_incident_mode**
  - Description: Incident response mode with full system diagnostic
  - Triggers: `mode incident`, `incident critique`, `production down`, `urgence prod`


### incident_response (1 dominos)

- **domino_incident_response**
  - Description: Incident response: cluster + RAM + disk + errors
  - Triggers: `incident response`, `reponse incident`, `procedure urgence`, `urgence prod`


### infrastructure (3 dominos)

- **domino_iac_overview**
  - Description: IaC tools overview: Terraform + Ansible + Pulumi
  - Triggers: `overview iac`, `infrastructure as code`, `iac status`, `check iac`

- **domino_terraform_workflow**
  - Description: Terraform workflow guide
  - Triggers: `workflow terraform`, `terraform complet`, `tf workflow`, `pipeline terraform`

- **domino_infra_check**
  - Description: Infrastructure tools check: Ansible + Vagrant + Terraform
  - Triggers: `check infra`, `infrastructure check`, `verification infra`, `infra status`


### integration (3 dominos)

- **domino_ollama_models**
  - Description: Lister les modeles Ollama: tags + running
  - Triggers: `liste les modeles ollama`, `quels modeles ollama`, `ollama models`

- **domino_lmstudio_models**
  - Description: Lister les modeles LM Studio sur M1/M2/M3
  - Triggers: `liste les modeles lm studio`, `quels modeles lm studio`, `lm studio models`

- **domino_n8n_status**
  - Description: Check n8n health
  - Triggers: `statut n8n`, `n8n status`, `les workflows`


### kubernetes (1 dominos)

- **domino_k8s_overview**
  - Description: Kubernetes overview: pods + services
  - Triggers: `statut kubernetes`, `k8s overview`, `resume kubernetes`, `cluster k8s`


### learning_mode (3 dominos)

- **domino_learn_benchmark**
  - Description: Benchmark cluster: compter dataset
  - Triggers: `benchmark les modeles`, `teste les performances ia`, `evalue le cluster`

- **domino_learn_train_status**
  - Description: Statut training: taille dataset
  - Triggers: `statut du training`, `ou en est l'entrainement`, `progression apprentissage`

- **domino_learn_quiz**
  - Description: Quiz: afficher description random, deviner le domino
  - Triggers: `lance un quiz`, `quiz de revision`, `teste mes connaissances`


### logging (1 dominos)

- **domino_log_review**
  - Description: Log review: recent entries + error count
  - Triggers: `review logs`, `revue des logs`, `check logs`, `analyse logs`


### maintenance (3 dominos)

- **domino_maintenance_hebdo**
  - Description: Maintenance hebdo: vacuum DB + git gc + clean temp + clean old logs
  - Triggers: `maintenance hebdo`, `maintenance de la semaine`, `nettoyage hebdomadaire`

- **domino_clean_temp_files**
  - Description: Nettoyer les fichiers temporaires et caches Python
  - Triggers: `nettoie les temporaires`, `supprime les temp`, `clean temp`

- **domino_rotate_logs**
  - Description: Rotation logs: compter + archiver les logs > 7 jours
  - Triggers: `rotation des logs`, `archive les logs`, `nettoie les vieux logs`


### maintenance_predictive (3 dominos)

- **domino_predict_disk_health**
  - Description: Diagnostic predictif disques: SMART + espace + latence IO
  - Triggers: `sante des disques`, `check les disques`, `diagnostic disque dur`

- **domino_predict_model_drift**
  - Description: Detection derive modeles: tester qualite reponses M1/M2/OL1
  - Triggers: `derive des modeles`, `check model drift`, `qualite des modeles`

- **domino_predict_failure**
  - Description: Prediction pannes: GPU usure, uptime, erreurs systeme, cluster health
  - Triggers: `prediction de panne`, `anticipe les pannes`, `maintenance preventive`


### media_control (5 dominos)

- **domino_media_focus_playlist**
  - Description: Playlist focus: ambiance sonore travail
  - Triggers: `musique de concentration`, `playlist focus`, `mets de la musique calme`

- **domino_media_silence**
  - Description: Silence total: couper tous les sons
  - Triggers: `coupe le son`, `silence total`, `mute everything`

- **domino_audio_setup**
  - Description: Audio setup: list devices + check volume
  - Triggers: `configure l'audio`, `audio setup`, `parametres son`, `regle le son`

- **domino_gaming_mode_full**
  - Description: Gaming mode full: list heavy processes + GPU check
  - Triggers: `mode gaming complet`, `full gaming`, `prepare le gaming`, `game mode full`

- **domino_streaming_setup**
  - Description: Streaming setup: GPU + network check
  - Triggers: `prepare le stream`, `setup streaming`, `mode streaming complet`


### meeting_assistant (4 dominos)

- **domino_meeting_prep**
  - Description: Prep meeting: test internet, audio check
  - Triggers: `prepare la reunion`, `meeting prep`, `briefing avant reunion`

- **domino_meeting_notes**
  - Description: Notes meeting: creer fichier markdown
  - Triggers: `prends des notes`, `compte rendu reunion`, `notes de meeting`

- **domino_meeting_timer**
  - Description: Timer reunion: demarrer chrono + log
  - Triggers: `timer de reunion`, `minuteur meeting`, `chrono reunion`

- **domino_presentation_setup**
  - Description: Presentation setup: disable notif + check display
  - Triggers: `prepare la presentation`, `setup presentation`, `mode presentation complet`


### mega_diagnostics (1 dominos)

- **domino_everything_check**
  - Description: EVERYTHING check: all 10 subsystems verified
  - Triggers: `check tout tout tout`, `mega check`, `everything check`, `verifie absolument tout`


### messaging (3 dominos)

- **domino_queue_health**
  - Description: Message queue health check
  - Triggers: `sante queues`, `queue health`, `check message queues`, `brokers status`

- **domino_kafka_topics**
  - Description: List Kafka topics
  - Triggers: `kafka topics`, `liste kafka`, `topics kafka`, `kafka list`

- **domino_celery_monitor**
  - Description: Celery workers monitoring
  - Triggers: `monitore celery`, `celery workers`, `celery monitor`, `check celery workers`


### milestone (2 dominos)

- **domino_3000_celebration**
  - Description: 3000 corrections milestone celebration
  - Triggers: `trois mille corrections`, `milestone trois mille`, `3000 corrections`, `celebration 3000`

- **domino_milestone_100**
  - Description: Batch 100 milestone celebration: full project stats
  - Triggers: `milestone cent`, `batch cent`, `centieme batch`, `celebration`


### mobile_dev (1 dominos)

- **domino_mobile_build**
  - Description: Check mobile build tools (Flutter/Expo)
  - Triggers: `build mobile`, `compile mobile`, `build apk`, `build app`


### monitoring (43 dominos)

- **domino_export_metrics**
  - Description: Exporter les metriques DB (etoile + jarvis)
  - Triggers: `exporte les metriques`, `export metrics`, `sauvegarde les stats`

- **domino_full_system_report**
  - Description: Rapport complet: CPU + RAM + GPU + disques + cluster + git
  - Triggers: `rapport systeme complet`, `etat global`, `tout savoir sur le systeme`

- **domino_check_services**
  - Description: Check services: LM Studio + Ollama + n8n + Dashboard
  - Triggers: `verifie les services`, `check services`, `services en ligne`

- **domino_cluster_warmup**
  - Description: Cluster warmup: ping all nodes to wake them
  - Triggers: `chauffe le cluster`, `warmup cluster`, `prepare le cluster`, `reveille le cluster`

- **domino_performance_report**
  - Description: Performance report: CPU + RAM + GPU + Disk
  - Triggers: `rapport de performance`, `performance report`, `etat des performances`, `combien ca tourne`

- **domino_disk_health**
  - Description: Disk health: space + SMART status
  - Triggers: `sante des disques`, `disk health`, `etat des ssd`, `smart status`

- **domino_gpu_detailed**
  - Description: GPU detailed: nvidia-smi + GPU processes
  - Triggers: `detail gpu`, `gpu detaille`, `info gpu complete`, `nvidia detail`

- **domino_vram_monitor**
  - Description: VRAM monitor: usage per GPU
  - Triggers: `surveille la vram`, `vram monitor`, `watch vram`, `monitore la vram`

- **domino_ollama_restart**
  - Description: Ollama restart: stop + start + verify
  - Triggers: `redemarre ollama`, `restart ollama`, `relance ollama`, `ollama restart`

- **domino_health_full**
  - Description: Full health check: all nodes + GPU
  - Triggers: `health check complet`, `check complet`, `diagnostic complet du cluster`, `full health`

- **domino_screen_setup**
  - Description: Screen setup: display info + resolution
  - Triggers: `configure les ecrans`, `screen setup`, `parametres ecrans`, `display settings`

- **domino_env_report**
  - Description: Environment report: versions + disk + uptime
  - Triggers: `rapport environnement`, `env report`, `check l'environnement`, `verifie l'env`

- **domino_model_reload**
  - Description: Model reload: check + warmup M1
  - Triggers: `recharge les modeles`, `model reload`, `reload models`, `recharge le modele`

- **domino_full_diagnostics**
  - Description: Full diagnostics: GPU + CPU + RAM + Disk + Uptime + Cluster
  - Triggers: `diagnostic complet`, `full diagnostics`, `diagnostique tout`, `check tout`

- **domino_service_restart_all**
  - Description: Service restart: check all services status
  - Triggers: `redemarre tous les services`, `restart all services`, `relance tout`, `restart tout`

- **domino_status_dashboard**
  - Description: Status dashboard: full metrics overview
  - Triggers: `tableau de bord`, `dashboard status`, `status board`, `affiche le tableau de bord`

- **domino_system_info**
  - Description: System info: OS + CPU + RAM + GPU specs
  - Triggers: `info systeme`, `system info`, `a propos du systeme`, `specs du pc`

- **domino_thermal_monitor**
  - Description: Thermal monitor: GPU + CPU temperatures
  - Triggers: `monitore les temperatures`, `thermal monitor`, `check les temperatures`, `watch thermal`

- **domino_metrics_snapshot**
  - Description: Metrics snapshot: all system metrics at a point in time
  - Triggers: `snapshot des metriques`, `metrics snapshot`, `sauvegarde les metriques`, `capture les stats`

- **domino_process_monitor**
  - Description: Process monitor: top 10 by CPU + total count
  - Triggers: `monitore les processus`, `process monitor`, `watch processus`, `surveille les processus`

- **domino_cluster_status_full**
  - Description: Full cluster status: all nodes + GPU + disk + uptime
  - Triggers: `statut complet du cluster`, `full cluster status`, `etat du cluster complet`

- **domino_memory_profile**
  - Description: Memory profile: total + free + top RAM consumers
  - Triggers: `profil memoire`, `memory profile`, `analyse la memoire`, `ram detaille`

- **domino_ml_status**
  - Description: ML status: GPU usage + loaded models
  - Triggers: `statut ml`, `ml status`, `etat du machine learning`, `statut entrainement`

- **domino_env_vars_audit**
  - Description: Env vars audit: check critical environment variables
  - Triggers: `audit variables env`, `env vars audit`, `verifie les variables`, `check env`

- **domino_elk_health**
  - Description: ELK stack health check
  - Triggers: `health elk`, `elk health`, `sante elk`, `elasticsearch health`

- **domino_observability**
  - Description: Observability stack check (OTel + Prometheus)
  - Triggers: `check observabilite`, `observability check`, `monitoring check`, `otel check`

- **domino_log_analysis**
  - Description: Log analysis for recent errors
  - Triggers: `analyse les logs`, `log analysis`, `cherche dans les logs`, `parse logs`

- **domino_api_health**
  - Description: API health check for cluster endpoints
  - Triggers: `sante des api`, `api health`, `check api sante`, `health check api`

- **domino_monitoring_dashboard**
  - Description: Full monitoring dashboard: cluster + disk + project stats
  - Triggers: `ouvre monitoring`, `dashboard monitoring`, `monitoring complet`, `observabilite`

- **domino_alert_review**
  - Description: Review recent alerts: Windows errors + recent fixes
  - Triggers: `review alertes`, `alertes recentes`, `check alertes`, `erreurs recentes`

- **domino_metrics_dashboard**
  - Description: Dashboard en temps reel: cluster, dispatch, GPU, DBs
  - Triggers: `dashboard`, `metriques systeme`, `metrics`, `tableau de bord`, `donne moi les stats`

- **domino_health_score**
  - Description: Recupere le health score global du systeme (A+ a F)
  - Triggers: `score de sante`, `health score`, `note systeme`, `grade systeme`, `quelle note`

- **domino_metrics_dashboard**
  - Description: Dashboard complet: cluster, dispatch, GPU, DB, scheduler
  - Triggers: `dashboard`, `tableau de bord`, `metriques`, `metrics dashboard`, `vue ensemble`

- **domino_monitor_full_dashboard**
  - Description: Dashboard tmux 4 panneaux: GPU, htop, logs, reseau
  - Triggers: `dashboard complet`, `ouvre le dashboard`, `monitoring complet`, `affiche le tableau de bord`, `tmux dashboard`, `lance le dashboard`, ``

- **domino_monitor_gpu_history**
  - Description: Historique et courbe des temperatures GPU sur 24h
  - Triggers: `historique gpu`, `temperatures gpu 24h`, `gpu history`, `courbe temperatures gpu`, `evolution gpu`, `historique temperatures`, ``

- **domino_monitor_network_traffic**
  - Description: Surveillance trafic reseau: connexions, bande passante, ports
  - Triggers: `surveille le reseau`, `trafic reseau`, `network monitor`, `qui utilise le reseau`, `bande passante`, `check le reseau`, ``

- **domino_monitor_disk_io**
  - Description: Analyse IO disque: usage, performances, gros fichiers, SMART
  - Triggers: `analyse les disques`, `io disque`, `disk io`, `performances disque`, `check les disques`, `sante des disques`, ``

- **domino_monitor_memory_leak**
  - Description: Detection fuites memoire: top consumers, swap, OOM, ZRAM
  - Triggers: `detecte les fuites memoire`, `memory leak`, `fuite memoire`, `qui bouffe la ram`, `analyse memoire`, `check la ram`, ``

- **domino_monitor_process_tree**
  - Description: Arbre des processus JARVIS: tree, Python, zombies
  - Triggers: `arbre des processus`, `process tree`, `processus jarvis`, `montre les process`, `ps tree`, `qui tourne`, ``

- **domino_monitor_service_health**
  - Description: Verification sante de tous les services JARVIS
  - Triggers: `sante des services`, `check les services`, `service health`, `etat des services`, `services jarvis`, `status services`, ``

- **domino_monitor_error_digest**
  - Description: Resume des erreurs systeme du jour via journalctl
  - Triggers: `resume des erreurs`, `digest erreurs`, `error digest`, `erreurs systeme`, `quelles erreurs aujourd'hui`, `recap erreurs`, ``

- **domino_monitor_uptime_report**
  - Description: Rapport uptime systeme et services
  - Triggers: `rapport uptime`, `depuis quand ca tourne`, `uptime report`, `disponibilite services`, `uptime des services`, ``

- **domino_monitor_resource_forecast**
  - Description: Prediction d'utilisation des ressources: disque, RAM, GPU, swap
  - Triggers: `prediction ressources`, `forecast utilisation`, `resource forecast`, `prevision ressources`, `tendance utilisation`, ``


### monitoring_alert (3 dominos)

- **domino_monitor_system_full**
  - Description: Monitoring complet: CPU/RAM + disque + GPU + cluster
  - Triggers: `monitoring systeme complet`, `status systeme total`, `check tout le systeme`

- **domino_monitor_alerts_check**
  - Description: Check alertes: logs erreurs + GPU temp + espace disque
  - Triggers: `verifie les alertes`, `check alertes`, `y a des alertes`

- **domino_monitor_performance**
  - Description: Benchmark rapide: CPU + RAM + GPU + IO
  - Triggers: `performance systeme`, `benchmark rapide`, `check performance`


### monitoring_live (3 dominos)

- **domino_watch_gpu_temp**
  - Description: Surveiller les temperatures GPU et alerter si critique
  - Triggers: `surveille les temperatures`, `watch gpu`, `alerte temperature`

- **domino_log_monitor**
  - Description: Log monitor: count errors + show recent
  - Triggers: `surveille les logs`, `monitor les logs`, `log monitor`, `regarde les erreurs`

- **domino_log_analysis**
  - Description: Log analysis: count lines + errors + warnings
  - Triggers: `analyse les logs`, `log analysis`, `examine les logs`, `parse les logs`


### multimedia (1 dominos)

- **domino_multimedia_check**
  - Description: Multimedia tools check: FFmpeg
  - Triggers: `check multimedia`, `outils multimedia`, `ffmpeg check`, `video tools`


### network_diagnostics (11 dominos)

- **domino_network_scan**
  - Description: Scan reseau: ARP table, IP config, ping cluster nodes
  - Triggers: `scan reseau`, `analyse le reseau`, `qui est connecte`

- **domino_network_latency**
  - Description: Test latence: ping M1/M2/M3, mesure RTT
  - Triggers: `test de latence`, `ping le cluster`, `mesure la latence reseau`

- **domino_network_dns**
  - Description: Diagnostic DNS: resolution, serveurs configures
  - Triggers: `diagnostic dns`, `verifie le dns`, `test dns`

- **domino_network_bandwidth**
  - Description: Bandwidth test: download speed + cluster latency
  - Triggers: `test de bande passante`, `speed test`, `test de vitesse reseau`

- **domino_network_scan**
  - Description: Network scan: ping gateway + DNS + connectivity
  - Triggers: `scan reseau`, `diagnostic reseau`, `test le reseau`, `network scan`

- **domino_network_speed**
  - Description: Network speed: ping + DNS test
  - Triggers: `test de vitesse`, `speed test`, `vitesse internet`, `bande passante`

- **domino_dns_diagnostic**
  - Description: DNS diagnostic: nslookup + ping
  - Triggers: `diagnostic dns`, `check dns complet`, `dns full`, `probleme dns`

- **domino_network_full**
  - Description: Full network diagnostic: IP + DNS + ports + latency
  - Triggers: `diagnostic reseau complet`, `full network check`, `network diagnostic`, `reseau complet`

- **domino_speed_test**
  - Description: Internet speed test via Cloudflare
  - Triggers: `test de vitesse`, `speed test`, `debit internet`, `vitesse connexion`

- **domino_latency_full**
  - Description: Full latency test on all 4 cluster nodes
  - Triggers: `test latence complet`, `full latency`, `latence tous les noeuds`, `ping complet`

- **domino_port_scan**
  - Description: Scan local listening ports
  - Triggers: `scan ports`, `ports ouverts`, `quels ports`, `netstat`, `port scan`


### network_info (1 dominos)

- **domino_ip_info**
  - Description: Show local and public IP addresses
  - Triggers: `info ip`, `mon ip`, `adresse ip`, `ip publique et locale`


### networking (7 dominos)

- **domino_gateway_audit**
  - Description: API gateway and reverse proxy audit
  - Triggers: `audit gateway`, `check gateway`, `gateway overview`, `reverse proxy check`

- **domino_nginx_config**
  - Description: Nginx configuration test
  - Triggers: `config nginx`, `nginx config`, `nginx configuration`, `verifie nginx`

- **domino_service_mesh**
  - Description: Service mesh check (Istio/Linkerd)
  - Triggers: `check service mesh`, `service mesh`, `istio check`, `mesh status`

- **domino_proxy_health**
  - Description: Proxy health check
  - Triggers: `sante proxy`, `proxy health`, `check proxy`, `reverse proxy status`

- **domino_websocket_test**
  - Description: WebSocket library check
  - Triggers: `test websocket`, `check websocket`, `teste les websocket`, `ws test`

- **domino_streaming_check**
  - Description: Streaming/SSE capability check
  - Triggers: `check streaming`, `test streaming api`, `streaming status`, `sse check`

- **domino_cdn_check**
  - Description: CDN availability check
  - Triggers: `check cdn`, `cdn status`, `verifie le cdn`, `cache cdn`


### notification_smart (3 dominos)

- **domino_notif_telegram**
  - Description: Alerte Telegram: collecter status + construire message + envoyer
  - Triggers: `envoie une alerte telegram`, `notifie sur telegram`, `telegram urgent`

- **domino_notif_tts_broadcast**
  - Description: Broadcast vocal: verifier cluster + GPU + annonce TTS
  - Triggers: `annonce vocale`, `broadcast vocal`, `annonce a tout le monde`

- **domino_notif_desktop**
  - Description: Toast Windows: construire notification + afficher + confirmer vocal
  - Triggers: `notification bureau`, `alerte desktop`, `toast notification`


### performance (5 dominos)

- **domino_perf_benchmark**
  - Description: Performance benchmark: import speed + RAM + cluster latency
  - Triggers: `benchmark performance`, `perf benchmark`, `test performance`, `bench complet`

- **domino_profiling_python**
  - Description: Python cProfile: top 5 functions by cumulative time
  - Triggers: `profiling python`, `profile le code`, `cprofile`, `performance python`

- **domino_load_test_prep**
  - Description: Load test preparation: check available tools
  - Triggers: `prepare load test`, `test de charge`, `load test`, `stress test prep`

- **domino_import_speed**
  - Description: Import speed benchmark: measure loading time of all modules
  - Triggers: `vitesse import`, `import speed`, `benchmark import`, `temps chargement`

- **domino_cache_management**
  - Description: Cache management: clear all caches
  - Triggers: `gere les caches`, `cache management`, `nettoie les caches`, `purge cache`


### performance_tuning (2 dominos)

- **domino_perf_gpu_optimize**
  - Description: GPU tuning: clocks, processes, power analysis
  - Triggers: `optimise les gpu`, `gpu tuning`, `ajuste les performances gpu`

- **domino_perf_memory_optimize**
  - Description: Memory analysis: RAM usage + top consumers
  - Triggers: `optimise la memoire`, `libere de la ram`, `memory cleanup`


### power_management (4 dominos)

- **domino_power_eco**
  - Description: Mode eco: verifier puissance GPU
  - Triggers: `mode economie`, `economise l'energie`, `power save`

- **domino_power_max**
  - Description: Mode performance: GPU full power
  - Triggers: `puissance maximum`, `full power`, `mode performance`

- **domino_focus_mode**
  - Description: Focus mode: disable notifications for deep work
  - Triggers: `mode focus`, `mode concentration`, `active le focus`, `deep work`

- **domino_study_mode**
  - Description: Study mode: disable notifications for focus
  - Triggers: `mode etude`, `study mode`, `mode revision`, `mode apprentissage`


### production (13 dominos)

- **domino_production_check**
  - Description: Validation des 7 couches de production avec score A-F
  - Triggers: `check production`, `valide la production`, `production status`, `grade jarvis`, `score production`, `audit production`

- **domino_production_report**
  - Description: Validation production + envoi Telegram automatique
  - Triggers: `rapport production`, `envoie le rapport`, `production report telegram`, `rapport complet production`

- **domino_heavy_model_load**
  - Description: Charger gpt-oss-20b sur M1 pour taches complexes
  - Triggers: `prepare grosse demande`, `charge le gros modele`, `mode heavy`, `prepare gpt oss`, `grosse tache`

- **domino_production_bootstrap**
  - Description: Bootstrap complet: GPU + cluster + automation + validation + Telegram
  - Triggers: `bootstrap production`, `amorce production`, `lance tout le systeme`, `demarrage production complet`

- **domino_auto_improve**
  - Description: Lance un cycle auto-improve: validation + correction automatique
  - Triggers: `ameliore le systeme`, `auto improve`, `auto amelioration`, `lance l'amelioration`, `optimise la production`

- **domino_daily_digest**
  - Description: Resume quotidien: automation + scheduler + production grade
  - Triggers: `resume de la journee`, `digest journalier`, `daily digest`, `qu'est ce qui s'est passe aujourd'hui`

- **domino_full_health**
  - Description: Health check complet: auto_scan + self_diagnostic + cache + automation status
  - Triggers: `sante complete`, `full health check`, `check complet`, `verification complete du systeme`, `rapport sante global`

- **domino_log_predictions**
  - Description: Predictions de pannes basees sur l'analyse des patterns de logs
  - Triggers: `predictions erreurs`, `previsions pannes`, `log predictions`, `anticipe les erreurs`, `problemes a venir`

- **domino_decision_stats**
  - Description: Affiche les decisions autonomes prises par JARVIS
  - Triggers: `decisions prises`, `decision engine stats`, `historique des decisions`, `qu'est ce que tu as decide`, `decisions autonomes`

- **domino_full_autonomy_check**
  - Description: Check complet de l'autonomie: automation + decisions + resources + diagnostic
  - Triggers: `check autonomie`, `verification autonomie complete`, `es tu autonome`, `statut autonomie`, `autonomy check`

- **domino_autonomous_cycle**
  - Description: Cycle autonome complet: scan + diagnostic + decisions + fix + predict + report + Telegram notify
  - Triggers: `cycle autonome`, `lance le cycle`, `autonomous cycle`, `scan et repare`, `auto scan fix`, `lance autonomie`

- **domino_endpoint_benchmark**
  - Description: Benchmark de tous les endpoints API avec temps de reponse et grade
  - Triggers: `benchmark`, `benchmark endpoints`, `performance api`, `vitesse api`, `teste les endpoints`

- **domino_watchdog_once**
  - Description: Execute un cycle watchdog: cycle autonome + self-improve si grade < B
  - Triggers: `watchdog`, `lance le watchdog`, `surveillance`, `watchdog une fois`


### productivity (5 dominos)

- **domino_mode_coding_intense**
  - Description: Mode coding intense: VSCode + terminal + disable notifs + focus timer
  - Triggers: `mode coding`, `mode dev intense`, `mode programmation`, `session de code`

- **domino_rapport_du_jour**
  - Description: Rapport quotidien: git log today + cluster + DB + trading PnL
  - Triggers: `rapport du jour`, `bilan de la journee`, `resume du jour`, `qu'est ce qu'on a fait aujourd'hui`

- **domino_satisfaction**
  - Description: Satisfaction report with system summary
  - Triggers: `tout va bien`, `status global`, `ca marche bien`, `everything ok`

- **domino_priority_report**
  - Description: Priority report with recent changes and pending work
  - Triggers: `rapport priorites`, `quoi d'urgent`, `priorite du jour`, `tasks urgentes`

- **domino_timer_pomodoro**
  - Description: Start a 25-minute Pomodoro timer
  - Triggers: `pomodoro`, `lance un pomodoro`, `timer 25 minutes`, `focus pomodoro`


### project_management (3 dominos)

- **domino_project_init**
  - Description: Init projet: verifier outils (uv, git)
  - Triggers: `initialise un projet python`, `nouveau projet`, `cree un projet`

- **domino_env_check**
  - Description: Check environnement: Python, UV, Node, Git, .env
  - Triggers: `verifie l'environnement`, `check env`, `environnement ok`

- **domino_milestone_check**
  - Description: Milestone check: project stats + categories + corrections
  - Triggers: `check milestone`, `milestone`, `objectif atteint`, `etape franchie`


### project_stats (2 dominos)

- **domino_large_files**
  - Description: Large files check + lines of code
  - Triggers: `gros fichiers`, `large files`, `fichiers volumineux`, `plus gros fichiers`

- **domino_lines_of_code**
  - Description: Count lines of code in project
  - Triggers: `lignes de code`, `count lines`, `combien de lignes`, `loc`, `taille du projet`


### python_dev (3 dominos)

- **domino_python_env**
  - Description: Python environment check: version + pip + uv + venv
  - Triggers: `environnement python`, `python env`, `setup python`, `check python`

- **domino_fastapi_launch**
  - Description: FastAPI launch preparation: check installation
  - Triggers: `lance l'api`, `fastapi start`, `demarre fastapi`, `uvicorn start`

- **domino_venv_setup**
  - Description: Create Python virtual environment
  - Triggers: `setup venv`, `cree un venv`, `virtualenv setup`, `init venv`


### release (2 dominos)

- **domino_changelog_gen**
  - Description: Generate changelog: last 30 days commits
  - Triggers: `genere changelog`, `changelog generation`, `release notes`, `notes de version`

- **domino_pre_release**
  - Description: Pre-release checks: syntax + tests + stats + git log
  - Triggers: `pre release`, `prepare la release`, `release prep`, `avant la release`


### reporting (2 dominos)

- **domino_grand_bilan**
  - Description: Grand bilan: full system + models + DB + today's activity
  - Triggers: `grand bilan`, `bilan general`, `recap total`, `tout recapituler`

- **domino_full_report**
  - Description: Full system report: summary + commits + today's activity
  - Triggers: `rapport final`, `full report`, `rapport complet systeme`, `bilan total`


### routine (11 dominos)

- **domino_daily_standup**
  - Description: Daily standup: commits hier + cluster + DB stats
  - Triggers: `standup`, `daily standup`, `standup du jour`, `morning standup`

- **domino_routine_matin_express**
  - Description: Routine matin express en moins de 2 minutes
  - Triggers: `matin express`, `routine express`, `demarrage rapide du matin`, `quick morning`, `vite fait le matin`, `matin deux minutes`, ``

- **domino_routine_pause_cafe**
  - Description: Mode pause cafe: musique lo-fi, ecran dim, volume bas, DND
  - Triggers: `pause cafe`, `mode cafe`, `je prends un cafe`, `break cafe`, `pause detente`, `coffee break`, ``

- **domino_routine_focus_mode**
  - Description: Mode focus: ferme distractions, DND, ouvre editeur
  - Triggers: `mode focus`, `concentration`, `pas de distractions`, `mode travail intense`, `deep work`, `focus total`, ``

- **domino_routine_meeting_prep**
  - Description: Preparation reunion: micro, camera, volume, ferme medias
  - Triggers: `prepare une reunion`, `meeting prep`, `je vais en reunion`, `prepare la visio`, `mode reunion`, `meeting mode`, ``

- **domino_routine_end_of_day**
  - Description: Fin de journee: sauvegarde, resume, restaure les parametres
  - Triggers: `fin de journee`, `end of day`, `termine la journee`, `bonne nuit jarvis`, `arrete la journee`, `on ferme boutique`, ``

- **domino_routine_weekend_mode**
  - Description: Mode weekend: reduit la consommation, backup, services alleges
  - Triggers: `mode weekend`, `passe en weekend`, `weekend mode`, `reduis les services`, `mode econome`, `mode repos`, ``

- **domino_routine_presentation**
  - Description: Mode presentation: pas de veille, DND, luminosite max
  - Triggers: `mode presentation`, `lance la presentation`, `presentation mode`, `prepare la demo`, `mode demo`, `je presente`, ``

- **domino_routine_debug_session**
  - Description: Session debug intensive: tmux logs + htop + GPU + erreurs recentes
  - Triggers: `session debug`, `mode debug`, `debug intensif`, `lance le debug`, `debug session`, `troubleshoot`, ``

- **domino_routine_learning_mode**
  - Description: Mode apprentissage: docs, notes, DND, timer
  - Triggers: `mode apprentissage`, `learning mode`, `mode etude`, `session apprentissage`, `je veux apprendre`, `mode documentation`, ``

- **domino_routine_emergency**
  - Description: Mode urgence: diagnostic complet rapide de tous les composants critiques
  - Triggers: `mode urgence`, `urgence systeme`, `emergency mode`, `alerte critique`, `all hands`, `c'est urgent`, ``


### routine_hebdo (1 dominos)

- **domino_weekend_prep**
  - Description: Weekend prep: save work + weekly summary
  - Triggers: `prepare le weekend`, `weekend prep`, `fin de semaine`, `avant le weekend`


### routine_matin (13 dominos)

- **domino_matin_complet**
  - Description: Briefing matinal complet: GPU, cluster, meteo, agenda, synthese vocale
  - Triggers: `bonjour jarvis`, `routine du matin`, `demarre la journee`, `lance le matin`

- **domino_cafe_code**
  - Description: Setup matinal dev: VSCode + git + musique + cluster
  - Triggers: `mode cafe code`, `session cafe dev`, `code du matin`

- **domino_reveil_rapide**
  - Description: Demarrage ultra-rapide: GPU + heure + confirmation vocale
  - Triggers: `reveil rapide`, `demarrage express`, `vite jarvis`

- **domino_matin_trading**
  - Description: Routine matin trading: marche + portfolio + signaux + alertes
  - Triggers: `matin trading`, `routine trading matin`, `bonjour trading`

- **domino_matin_weekend**
  - Description: Routine weekend allegee: GPU + backup + message
  - Triggers: `bonjour weekend`, `matin tranquille`, `routine weekend`

- **domino_morning_full**
  - Description: Briefing complet: date + GPU + cluster + disques + git
  - Triggers: `briefing complet`, `demarrage complet`, `full morning`

- **domino_lunch_break**
  - Description: Pause dejeuner: save + lock screen
  - Triggers: `pause dejeuner`, `je mange`, `lunch break`, `pause midi`

- **domino_coffee_break**
  - Description: Pause cafe: git stash le travail en cours
  - Triggers: `pause cafe`, `coffee break`, `je prends un cafe`, `petite pause`

- **domino_startup_sequence**
  - Description: Startup sequence: health check + git pull + GPU temp
  - Triggers: `sequence de demarrage`, `startup`, `boot sequence`, `demarre tout`

- **domino_morning_stretch**
  - Description: Morning stretch: TTS reminder to stretch
  - Triggers: `etirement matin`, `morning stretch`, `pause etirement`, `stretch break`

- **domino_git_morning**
  - Description: Morning git: pull + status + today's log
  - Triggers: `git du matin`, `morning git`, `check git matin`, `git matinal`

- **domino_monday_morning**
  - Description: Monday morning: pull + health + disk check
  - Triggers: `lundi matin`, `monday morning`, `debut de semaine`, `nouvelle semaine`

- **domino_morning_dev**
  - Description: Morning dev routine: pull + health + summary + env versions
  - Triggers: `morning dev`, `debut de journee dev`, `demarre la journee dev`, `dev morning routine`


### routine_soir (10 dominos)

- **domino_bonne_nuit**
  - Description: Routine soir: sauvegarder + backup + fermer trading + reduire GPU
  - Triggers: `bonne nuit jarvis`, `fin de journee`, `arrete tout pour ce soir`

- **domino_pause_dejeuner**
  - Description: Pause dejeuner: sauvegarder + reduire charge
  - Triggers: `pause dejeuner`, `je vais manger`, `break midi`

- **domino_weekend_shutdown**
  - Description: Shutdown weekend: backup + metriques + close trading + GPU eco
  - Triggers: `mode weekend`, `eteins le cluster weekend`, `shutdown weekend`

- **domino_end_of_day**
  - Description: Fin de journee: auto commit + push + backup + stats session
  - Triggers: `fin de journee`, `bonne nuit jarvis`, `je pars`, `fin du travail`

- **domino_evening_review**
  - Description: Evening review: today's commits + stats
  - Triggers: `bilan du soir`, `revue du soir`, `evening review`, `resume de la journee`

- **domino_shutdown_sequence**
  - Description: Shutdown sequence: save + push + backup
  - Triggers: `sequence arret`, `shutdown`, `arrete tout proprement`, `extinction`

- **domino_end_session**
  - Description: End session: stats + auto save
  - Triggers: `fin de session`, `end session`, `termine la session`, `session terminee`

- **domino_weekend_prep**
  - Description: Weekend prep: save + push + backup
  - Triggers: `prepare le weekend`, `weekend prep`, `mode weekend`, `vendredi soir`

- **domino_daily_wrapup**
  - Description: Daily wrapup: today's commits + stats + system health
  - Triggers: `bilan journee`, `daily wrapup`, `fin de journee`, `resume du jour`

- **domino_night_shutdown**
  - Description: Night shutdown: save work + show stats
  - Triggers: `bonne nuit`, `extinction nocturne`, `night shutdown`, `mode nuit`


### security (8 dominos)

- **domino_pip_security**
  - Description: pip security audit for vulnerabilities
  - Triggers: `securite pip`, `pip audit`, `vulnerabilites pip`, `pip security`

- **domino_rate_limit**
  - Description: Rate limiting configuration check
  - Triggers: `check rate limiting`, `rate limit`, `limite de requetes`, `throttling check`

- **domino_auth_audit**
  - Description: Authentication libraries audit
  - Triggers: `audit auth`, `audit authentification`, `check securite auth`, `auth security`

- **domino_mfa_check**
  - Description: MFA/2FA library check
  - Triggers: `check mfa`, `mfa status`, `authentification double`, `2fa check`

- **domino_firewall_check**
  - Description: Check Windows firewall status
  - Triggers: `check firewall`, `statut pare feu`, `firewall rules`, `pare feu actif`

- **domino_security_scan**
  - Description: Quick security scan: ports + pip audit + git secrets
  - Triggers: `scan securite`, `security scan`, `audit securite rapide`, `check securite`

- **domino_token_generate**
  - Description: Generate secure random token
  - Triggers: `genere un token`, `nouveau token`, `create token`, `api key`

- **domino_pip_security**
  - Description: Python pip security audit
  - Triggers: `securite pip`, `pip security`, `audit pip`, `vulnerabilites python`


### security_sweep (8 dominos)

- **domino_security_full**
  - Description: Audit securite complet: ports + firewall + .env + processus suspects
  - Triggers: `scan securite complet`, `audit securite`, `security sweep`

- **domino_security_keys**
  - Description: Audit cles API: .env + historique git + DB
  - Triggers: `verifie les cles api`, `check api keys`, `audit cles`

- **domino_security_network**
  - Description: Scan reseau securite: connexions actives + IPs inconnues
  - Triggers: `scan reseau securite`, `check connexions suspectes`, `intrusion check`

- **domino_security_permissions**
  - Description: Audit permissions: ACL + fichiers sensibles
  - Triggers: `check permissions`, `audit droits fichiers`, `permissions securite`

- **domino_security_quick**
  - Description: Securite rapide: ports ouverts + firewall status
  - Triggers: `check securite rapide`, `securite rapide`, `quick security`

- **domino_security_audit**
  - Description: Security audit: ports + firewall + defender + secrets scan
  - Triggers: `audit de securite`, `security audit`, `check securite complet`, `full security`

- **domino_pip_security**
  - Description: Pip security: audit for known vulnerabilities
  - Triggers: `check securite pip`, `pip security`, `audit pip`, `vulnerabilites pip`

- **domino_cert_check**
  - Description: Certificate check: SSL cert dates
  - Triggers: `verifie les certificats`, `cert check`, `ssl check`, `check ssl`


### self_diagnostics (3 dominos)

- **domino_jarvis_health**
  - Description: JARVIS health check: syntax + stats + cluster
  - Triggers: `sante jarvis`, `jarvis health`, `comment va jarvis`, `jarvis ok`

- **domino_jarvis_self_test**
  - Description: JARVIS self-test: syntax + imports + matching + stats
  - Triggers: `test jarvis`, `auto test`, `self test`, `jarvis fonctionne`

- **domino_jarvis_stats**
  - Description: JARVIS stats: commands + corrections + dominos
  - Triggers: `stats jarvis`, `statistiques jarvis`, `combien de commandes`, `resume jarvis`


### sre (1 dominos)

- **domino_sre_dashboard**
  - Description: SRE dashboard: uptime + RAM + disk + ports + activity
  - Triggers: `dashboard sre`, `sre overview`, `fiabilite systeme`, `site reliability`


### streaming (2 dominos)

- **domino_stream_start**
  - Description: Demarrage stream: reseau + OBS + chat monitor
  - Triggers: `lance le stream`, `demarre le streaming`, `on stream maintenant`

- **domino_stream_stop**
  - Description: Arret stream: stop OBS + sauvegarder VOD info
  - Triggers: `arrete le stream`, `stop streaming`, `fin du stream`


### support (1 dominos)

- **domino_frustration_handler**
  - Description: Frustration handler with automatic diagnostic
  - Triggers: `ca marche pas`, `rien ne marche`, `tout est casse`, `j'en ai marre`


### system (10 dominos)

- **domino_check_disk_space**
  - Description: Verifier l'espace disque C: et F:
  - Triggers: `espace disque`, `combien de place`, `disk space`

- **domino_auto_scan**
  - Description: Scan autonome complet: cluster, DB, GPU, services, dispatch
  - Triggers: `scan le systeme`, `auto scan`, `scan complet`, `diagnostic complet`, `scan jarvis`

- **domino_windows_notify**
  - Description: Envoyer une notification toast Windows via le bridge
  - Triggers: `notification windows`, `envoie une notif`, `toast windows`, `alerte windows`, `notifie moi`

- **domino_sql_status**
  - Description: Afficher les stats des 3 bases SQLite (etoile, jarvis, scheduler)
  - Triggers: `status des bases`, `etat des databases`, `sql stats`, `combien de tables`, `bases de donnees`

- **domino_mode_performance**
  - Description: Active le mode performance: ferme apps gourmandes + GPU boost
  - Triggers: `mode performance`, `max performance`, `boost performance`, `mode turbo`

- **domino_self_diagnostic**
  - Description: Lance un auto-diagnostic complet: response times, error rates, circuit breakers, queue
  - Triggers: `diagnostic systeme`, `auto diagnostic`, `self diagnostic`, `analyse toi`, `diagnostique toi`, `check ta sante`

- **domino_dispatch_cache**
  - Description: Affiche les statistiques du cache de dispatch (hits, taille, TTL)
  - Triggers: `stats du cache`, `cache dispatch`, `etat du cache`, `performance cache`

- **domino_system_resources**
  - Description: Affiche les ressources systeme: CPU, RAM, GPU, disques
  - Triggers: `ressources systeme`, `cpu et ram`, `utilisation memoire`, `charge systeme`, `system resources`

- **domino_vram_check**
  - Description: Verifie l'utilisation VRAM de tous les GPU et suggere des optimisations
  - Triggers: `etat de la vram`, `vram status`, `memoire gpu`, `gpu memoire`, `vram libre`, `optimise la vram`

- **domino_rollback_history**
  - Description: Affiche l'historique des auto-fix avec snapshots et rollbacks
  - Triggers: `historique rollback`, `rollback history`, `dernieres corrections`, `historique des fix`


### system_cleanup (11 dominos)

- **domino_cleanup_temp**
  - Description: Analyse temp files: compter taille TEMP + pip cache
  - Triggers: `nettoie les fichiers temporaires`, `vide le temp`, `clean temp files`

- **domino_cleanup_orphans**
  - Description: Detecter processus orphelins et top CPU consumers
  - Triggers: `cherche les processus orphelins`, `kill les zombies`, `processus fantomes`

- **domino_cleanup_git**
  - Description: Git cleanup: gc, prune remote branches, check size
  - Triggers: `nettoie le git`, `git cleanup`, `git prune`

- **domino_cache_cleanup**
  - Description: Cache cleanup: Python + pip + npm caches
  - Triggers: `nettoie les caches`, `vide tous les caches`, `cache cleanup`

- **domino_memory_cleanup**
  - Description: Memory cleanup: GC collect + RAM status
  - Triggers: `libere la memoire`, `nettoie la ram`, `memory cleanup`, `libere la ram`

- **domino_windows_cleanup**
  - Description: Windows cleanup: temp + prefetch + recycle bin
  - Triggers: `nettoie windows`, `windows cleanup`, `vide les temp`, `menage windows`

- **domino_weekly_maintenance**
  - Description: Weekly maintenance: vacuum + analyze + git gc + temp cleanup
  - Triggers: `maintenance hebdo`, `weekly maintenance`, `maintenance de la semaine`, `entretien hebdomadaire`

- **domino_task_kill_heavy**
  - Description: List heavy processes: top 5 by CPU
  - Triggers: `tue les processus lourds`, `kill heavy`, `libere le cpu`, `kill les processus`

- **domino_workspace_organize**
  - Description: Workspace organize: count desktop + downloads files
  - Triggers: `organise le workspace`, `range le bureau`, `workspace organize`, `trie les fichiers`

- **domino_docker_cleanup**
  - Description: Docker cleanup: prune containers + images + volumes
  - Triggers: `nettoie docker`, `docker cleanup`, `docker prune`, `menage docker`

- **domino_clean_everything**
  - Description: Clean everything: all caches + temp + pip + git gc
  - Triggers: `nettoie tout`, `clean everything`, `grand menage`, `purge complete`


### system_control (3 dominos)

- **monte_volume**
  - Description: Augmente le volume de 10%
  - Triggers: `monte le son`, `augmente le volume`

- **baisse_volume**
  - Description: Baisse le volume de 10%
  - Triggers: `baisse le son`, `diminue le volume`

- **coupe_son**
  - Description: Coupe ou réactive le son
  - Triggers: `coupe le son`, `muet`, `active le son`


### system_diagnostics (5 dominos)

- **domino_storage_full**
  - Description: Full storage check: disk usage + partitions
  - Triggers: `stockage complet`, `full storage check`, `verification stockage`, `disk full check`

- **domino_filesystem_audit**
  - Description: Filesystem audit: disk + large files + DB sizes
  - Triggers: `audit filesystem`, `audit fichiers`, `check filesystem`, `integrite fichiers`

- **domino_memory_check**
  - Description: Memory check: RAM + disk usage
  - Triggers: `check memoire`, `memory check`, `utilisation ram`, `combien de ram`

- **domino_process_heavy**
  - Description: Show heavy processes consuming most memory
  - Triggers: `processus lourds`, `gros processus`, `heavy process`, `qui mange la ram`

- **domino_services_check**
  - Description: Check running Windows services
  - Triggers: `services actifs`, `check services`, `services en cours`, `quels services`


### system_info (3 dominos)

- **domino_env_report**
  - Description: Environment report: Python + Node + Git + disk
  - Triggers: `rapport environnement`, `env report`, `variables env`, `environment report`

- **liste_apps**
  - Description: Liste les applications installées
  - Triggers: `liste les applications`, `quelles sont les applications`

- **status_batterie**
  - Description: Affiche l'état de la batterie
  - Triggers: `etat de la batterie`, `niveau de batterie`


### system_maintenance (2 dominos)

- **range_bureau_auto**
  - Description: Rangement complet et dédoublonnage du bureau
  - Triggers: `range le bureau`, `nettoie le bureau`, `ordonne le bureau`

- **nettoyage_systeme**
  - Description: Nettoyage des fichiers temporaires et du cache apt
  - Triggers: `nettoyage systeme`, `nettoie le systeme`, `purge les temporaires`


### system_settings (2 dominos)

- **mode_nuit**
  - Description: Active le mode nuit (filtre bleu)
  - Triggers: `active le mode nuit`, `mode nuit`, `filtre bleu`

- **mode_jour**
  - Description: Désactive le mode nuit
  - Triggers: `active le mode jour`, `mode jour`, `desactive le mode nuit`


### system_tools (4 dominos)

- **domino_tool_system_health**
  - Description: Health check complet via JARVIS tools: cluster + boot + GPU + DB + alertes
  - Triggers: `sante systeme`, `health check complet`, `check sante jarvis`, `system health`, `check systeme complet`, `statut systeme complet`, `rapport sante`

- **domino_tool_autonomous_check**
  - Description: Statut complet de la boucle autonome: taches + evenements recents
  - Triggers: `statut autonome`, `check autonome`, `taches autonomes`, `boucle autonome`, `etat boucle autonome`, `combien de taches`

- **domino_tool_morning_jarvis**
  - Description: Routine matin JARVIS via tools: boot + cluster + autonome + diag + GPU
  - Triggers: `bonjour jarvis tools`, `matin jarvis complet`, `demarrage jarvis`, `bonjour jarvis`, `routine matin`, `rapport du matin`

- **domino_tool_run_maintenance**
  - Description: Pipeline maintenance via tools: zombie GC + VRAM audit + DB maintenance + diagnostic
  - Triggers: `lance maintenance`, `maintenance tools`, `run maintenance`, `lance la maintenance`, `nettoyage systeme`, `nettoie le systeme`


### systems_programming (3 dominos)

- **domino_rust_build**
  - Description: Rust build environment check
  - Triggers: `build rust`, `compile rust`, `cargo build`, `rust project`

- **domino_go_build**
  - Description: Go build environment check
  - Triggers: `build go`, `compile go`, `go build`, `golang project`

- **domino_wasm_check**
  - Description: WebAssembly tools check
  - Triggers: `check wasm`, `webassembly`, `wasm build`, `wasm status`


### task_scheduling (3 dominos)

- **domino_task_plan_day**
  - Description: Planning jour: date, git pending
  - Triggers: `planifie ma journee`, `organise mon planning`, `plan du jour`

- **domino_timer_pomodoro**
  - Description: Pomodoro: TTS start, log focus
  - Triggers: `lance un pomodoro`, `timer 25 minutes`, `pomodoro start`

- **domino_pomodoro_session**
  - Description: Pomodoro session: start 25min focus timer
  - Triggers: `pomodoro`, `lance pomodoro`, `session pomodoro`, `technique pomodoro`


### testing (7 dominos)

- **domino_test_suite_full**
  - Description: Full test suite: pytest + syntax checks
  - Triggers: `suite de tests complete`, `all tests`, `tous les tests`, `test complet`

- **domino_e2e_launch**
  - Description: E2E testing framework check
  - Triggers: `lance les e2e`, `e2e tests`, `end to end`, `teste e2e`

- **domino_cypress_run**
  - Description: Run Cypress E2E tests headless
  - Triggers: `lance cypress`, `cypress run`, `teste avec cypress`, `cypress e2e`

- **domino_test_coverage**
  - Description: Test coverage report
  - Triggers: `coverage`, `code coverage`, `couverture de tests`, `test coverage`

- **domino_vitest_suite**
  - Description: Run Vitest test suite
  - Triggers: `suite vitest`, `lance les tests vitest`, `vitest run all`, `run vitest`

- **domino_test_suite**
  - Description: Full test suite: syntax + 3 voice matches + summary
  - Triggers: `lance tous les tests`, `test suite complete`, `full test`, `run all tests`

- **domino_regression_check**
  - Description: Regression test: imports + counts + match
  - Triggers: `test de regression`, `regression check`, `rien de casse`, `verifie la regression`


### testing_pipeline (15 dominos)

- **domino_test_all_dominos**
  - Description: Pre-test: compter cascades et dataset avant run
  - Triggers: `teste tous les dominos`, `run all tests`, `lance les tests complets`

- **domino_test_cluster_health**
  - Description: Health check: ping M1/M2/OL1 + GPU temps
  - Triggers: `test de sante cluster`, `cluster health check`, `verifie la sante du cluster`

- **domino_quick_test**
  - Description: Test rapide: syntaxe + imports des modules principaux
  - Triggers: `test rapide`, `quick test`, `verifie que ca marche`

- **domino_test_voice_pipeline**
  - Description: Test du pipeline vocal: compter commandes, corrections, implicites, dominos
  - Triggers: `teste le pipeline vocal`, `test voice`, `teste la reconnaissance`

- **domino_voice_pipeline_test**
  - Description: Voice pipeline test: count + match tests
  - Triggers: `teste le pipeline vocal`, `test voix complet`, `voice pipeline test`, `test la reconnaissance`

- **domino_quick_benchmark**
  - Description: Quick benchmark: test M1 + OL1 response time
  - Triggers: `benchmark rapide`, `quick bench`, `teste la vitesse`, `bench rapide`

- **domino_model_benchmark**
  - Description: Model benchmark: test M1 + OL1 models response
  - Triggers: `benchmark modeles`, `model benchmark`, `teste les modeles`, `compare les modeles`

- **domino_voice_calibrate**
  - Description: Voice calibrate: run match tests + count stats
  - Triggers: `calibre la voix`, `voice calibrate`, `ajuste la reconnaissance`, `calibration vocale`

- **domino_api_test**
  - Description: API test: check M1 + OL1 + Dashboard endpoints
  - Triggers: `teste les api`, `api test`, `check les endpoints`, `verifie les api`

- **domino_latency_test**
  - Description: Latency test: measure response time per node
  - Triggers: `test de latence`, `latency test`, `ping tous les noeuds`, `latence du cluster`

- **domino_voice_stats_report**
  - Description: Voice stats: commands + corrections + session info
  - Triggers: `rapport vocal`, `voice stats`, `statistiques vocales`, `stats de la voix`

- **domino_test_suite_full**
  - Description: Full test suite: syntax + match tests + counts
  - Triggers: `lance tous les tests`, `test suite complete`, `full test`, `teste tout`

- **domino_gpu_benchmark**
  - Description: GPU benchmark: nvidia-smi + inference test
  - Triggers: `benchmark gpu`, `gpu benchmark`, `teste le gpu`, `performance gpu`

- **domino_quick_benchmark_full**
  - Description: Full benchmark: M1 + OL1 + M2 response time
  - Triggers: `benchmark complet`, `full benchmark`, `benchmark le cluster`, `bench all`

- **domino_final_check**
  - Description: Final check: syntax + match + stats + git
  - Triggers: `check final`, `final check`, `verification finale`, `derniere verification`


### trading (2 dominos)

- **domino_trading_quick**
  - Description: Quick trading preparation: verify cluster readiness
  - Triggers: `trading rapide`, `quick trade`, `signal trading`, `scan trading rapide`

- **domino_crypto_check**
  - Description: Crypto status check placeholder
  - Triggers: `check crypto`, `statut crypto`, `blockchain status`, `crypto overview`


### trading_cascade (6 dominos)

- **domino_trading_full_scan**
  - Description: Scan trading complet: prix + correlation + signaux + risque
  - Triggers: `scan trading complet`, `analyse complete marche`, `trading full scan`

- **domino_trading_execute**
  - Description: Execution trading: validation + balance + ordre + TP/SL
  - Triggers: `execute signal trading`, `trade maintenant`, `passe l'ordre`

- **domino_trading_close_all**
  - Description: Fermeture urgente: lister + fermer + PnL + rapport
  - Triggers: `ferme tout trading`, `close all positions`, `urgence trading stop`

- **domino_trading_backtest**
  - Description: Backtest complet: historique + simulation + analyse
  - Triggers: `lance un backtest`, `backtest strategie`, `simule le trading`

- **domino_trading_drawdown_alert**
  - Description: Analyse drawdown: PnL + calcul + evaluation risque
  - Triggers: `check drawdown`, `alerte pertes`, `risque portfolio`

- **domino_analyse_trading_ia**
  - Description: Analyse trading IA: prix + M1 analyse + OL1 analyse + consensus vote
  - Triggers: `analyse trading ia`, `ia analyse le marche`, `consensus trading`


### ux_design (1 dominos)

- **domino_ux_audit**
  - Description: UX audit: accessibility + design check
  - Triggers: `audit ux`, `ux review`, `accessibilite check`, `check ux`


### voice (1 dominos)

- **domino_update_corrections**
  - Description: Recharger les corrections vocales depuis la DB
  - Triggers: `recharge les corrections`, `met a jour les corrections`, `sync corrections`


### voice_audit (1 dominos)

- **domino_voice_system_audit**
  - Description: Full voice system audit: all vocal subsystems
  - Triggers: `audit vocal`, `voice system audit`, `audit systeme vocal`, `check vocal complet`


### voice_profiles (2 dominos)

- **domino_profile_work**
  - Description: Profil travail: GPU check
  - Triggers: `profil travail`, `mode productif`, `active le profil boulot`

- **domino_profile_relax**
  - Description: Profil detente: check temperature
  - Triggers: `profil detente`, `mode relax`, `active le profil chill`


### voice_system (1 dominos)

- **domino_whisper_check**
  - Description: Whisper STT check
  - Triggers: `check whisper`, `whisper status`, `stt check`, `reconnaissance vocale`


### voice_testing (2 dominos)

- **domino_notification_test**
  - Description: Notification test: TTS output test
  - Triggers: `test notification`, `teste les notifications`, `notification check`, `alertes test`

- **domino_voice_pipeline_test**
  - Description: Full voice pipeline test: 3 match tests + corrections count
  - Triggers: `teste le pipeline vocal`, `voice test`, `test vocal complet`, `pipeline vocal`


### web_dev (1 dominos)

- **domino_web_stack**
  - Description: Web stack check: Node + npm + Python + TSC
  - Triggers: `stack web`, `web stack check`, `frontend backend`, `full stack check`


### wellness_productivity (3 dominos)

- **domino_pomodoro**
  - Description: Timer Pomodoro 25min focus + desactive notifs + rappel pause
  - Triggers: `lance un pomodoro`, `mode focus 25 minutes`, `pomodoro timer`

- **domino_focus_mode**
  - Description: Focus mode: fermer distractions, desactiver notifs, optimiser GPU
  - Triggers: `mode concentration`, `active le focus`, `zero distraction`

- **domino_session_review**
  - Description: Revue de session: commits, GPU usage, stats DB, bilan vocal
  - Triggers: `bilan de la journee`, `resume ma session`, `revue de session`


### windows_system (3 dominos)

- **domino_wsl_status**
  - Description: Check WSL distributions status
  - Triggers: `statut wsl`, `wsl status`, `check wsl`, `etat wsl`

- **domino_event_viewer**
  - Description: Show recent Windows system errors from Event Viewer
  - Triggers: `event logs`, `evenements systeme`, `erreurs windows`, `journal evenements`

- **domino_startup_apps**
  - Description: List Windows startup applications
  - Triggers: `apps demarrage`, `startup apps`, `programmes demarrage`, `autostart`


---

## Macros Vocales

- **archive_le_projet** — Git bundle, archive tar et checksum
  - Commandes:
    1. `git bundle`
    1. `archive tar`
    1. `vérifie checksum`
  - Utilisations: 0

- **capture_et_partage** — Capture ecran et copie dans le presse-papier
  - Commandes:
    1. `capture écran`
    1. `copie dans le presse-papier`
  - Utilisations: 0

- **check_sécurité** — Verifie UFW, fail2ban, ports et permissions
  - Commandes:
    1. `vérifie ufw`
    1. `vérifie fail2ban`
    1. `vérifie les ports`
    1. `vérifie les permissions`
  - Utilisations: 0

- **compile_et_teste** — Build, pytest et coverage
  - Commandes:
    1. `lance le build`
    1. `lance pytest`
    1. `lance coverage`
  - Utilisations: 0

- **debug_réseau** — Ping, traceroute, DNS, ports et connexions
  - Commandes:
    1. `ping google`
    1. `traceroute google`
    1. `vérifie dns`
    1. `vérifie les ports`
    1. `liste les connexions`
  - Utilisations: 0

- **diagnostic_complet** — Diagnostic CPU, RAM, GPU, disque, reseau et services
  - Commandes:
    1. `vérifie cpu`
    1. `vérifie ram`
    1. `vérifie gpu`
    1. `vérifie disque`
    1. `vérifie réseau`
    1. `vérifie les services`
  - Utilisations: 0

- **emergency_stop** — Kill GPU processes, arrete le trading et envoie une alerte
  - Commandes:
    1. `kill gpu processes`
    1. `arrête le trading`
    1. `envoie une alerte`
  - Utilisations: 0

- **ferme_tout** — Ferme toutes les fenetres ouvertes
  - Commandes:
    1. `ferme toutes les fenêtres`
  - Utilisations: 0

- **fin_de_journée** — Sauvegarde, backup, rapport, mode economie et verrouillage
  - Commandes:
    1. `sauvegarde tout`
    1. `lance le backup`
    1. `génère le rapport`
    1. `mode économie énergie`
    1. `verrouille l'écran`
  - Utilisations: 0

- **mise_à_jour_complète** — apt update, upgrade, snap refresh et verification reboot
  - Commandes:
    1. `apt update`
    1. `apt upgrade`
    1. `snap refresh`
    1. `vérifie reboot`
  - Utilisations: 0

- **mode_gaming** — Ferme apps inutiles, mode performance, lance Steam
  - Commandes:
    1. `ferme les apps inutiles`
    1. `mode performance`
    1. `ouvre steam`
  - Utilisations: 0

- **mode_lecture** — Ouvre Firefox plein ecran avec luminosite basse
  - Commandes:
    1. `ouvre firefox`
    1. `plein écran`
    1. `luminosité 30`
  - Utilisations: 0

- **mode_musique** — Ouvre Spotify et regle le volume a 60%
  - Commandes:
    1. `ouvre spotify`
    1. `volume 60`
  - Utilisations: 0

- **mode_silence** — Mute, mode ne pas deranger, baisse luminosite ecran
  - Commandes:
    1. `mute`
    1. `active ne pas déranger`
    1. `luminosité 20`
  - Utilisations: 0

- **mode_streaming** — Lance OBS, Discord, verifie micro et camera
  - Commandes:
    1. `ouvre obs`
    1. `ouvre discord`
    1. `vérifie le micro`
    1. `vérifie la caméra`
  - Utilisations: 0

- **mode_voyage** — Economie energie, sync cloud et verrouillage
  - Commandes:
    1. `mode économie énergie`
    1. `synchronise le cloud`
    1. `verrouille l'écran`
  - Utilisations: 0

- **mode_zen** — Fond nature, musique lo-fi, DND et timer pomodoro 25min
  - Commandes:
    1. `fond d'écran nature`
    1. `lance musique lo-fi`
    1. `active ne pas déranger`
    1. `timer 25 minutes`
  - Utilisations: 0

- **moniteur_temps_réel** — Lance htop, nvidia-smi en boucle et iotop
  - Commandes:
    1. `lance htop`
    1. `lance nvidia-smi`
    1. `lance iotop`
  - Utilisations: 0

- **nettoie_l_écran** — Ferme notifications, minimise tout, reset wallpaper
  - Commandes:
    1. `ferme les notifications`
    1. `minimise tout`
    1. `reset wallpaper`
  - Utilisations: 0

- **ouvre_la_doc** — Ouvre docs JARVIS dans Firefox et man pages dans terminal
  - Commandes:
    1. `ouvre firefox docs jarvis`
    1. `ouvre terminal man pages`
  - Utilisations: 0

- **ouvre_mon_espace_de_travail** — Ouvre terminal + vscode + firefox
  - Commandes:
    1. `ouvre terminal`
    1. `ouvre vscode`
    1. `ouvre firefox`
  - Utilisations: 0

- **prépare_une_présentation** — Ouvre LibreOffice Impress, plein ecran et mode ne pas deranger
  - Commandes:
    1. `ouvre libreoffice impress`
    1. `plein écran`
    1. `active ne pas déranger`
  - Utilisations: 0

- **range_les_fichiers** — Organise les telechargements par type de fichier
  - Commandes:
    1. `organise les téléchargements`
  - Utilisations: 0

- **rapport_du_matin** — Meteo, emails, git status et etat des services
  - Commandes:
    1. `donne la météo`
    1. `vérifie les emails`
    1. `git status`
    1. `vérifie les services`
  - Utilisations: 0

- **restaure_l_audio** — Redemarre PipeWire, volume 70% et unmute
  - Commandes:
    1. `redémarre pipewire`
    1. `volume 70`
    1. `unmute`
  - Utilisations: 0

- **sauvegarde_bases** — Vacuum, backup SQLite et verification
  - Commandes:
    1. `vacuum base de données`
    1. `backup sqlite`
    1. `vérifie backup`
  - Utilisations: 0

- **sauvegarde_et_push** — Git add, commit et push
  - Commandes:
    1. `git add tout`
    1. `git commit`
    1. `git push`
  - Utilisations: 0

- **session_code_python** — Ouvre terminal, VSCode et IPython
  - Commandes:
    1. `ouvre terminal`
    1. `ouvre vscode`
    1. `lance ipython`
  - Utilisations: 0

- **session_trading** — Ouvre TradingView, terminal pipeline et check GPU
  - Commandes:
    1. `ouvre tradingview`
    1. `lance le pipeline trading`
    1. `vérifie gpu`
  - Utilisations: 0

- **vérifie_tout** — Git status, tests, services et GPU
  - Commandes:
    1. `git status`
    1. `lance les tests`
    1. `vérifie les services`
    1. `vérifie gpu`
  - Utilisations: 0

---

## Corrections Phonetiques

| Erreur | Correction | Categorie | Occurrences |
|--------|-----------|-----------|-------------|
| aile aime studio | lm studio | ai_cluster | 0 |
| aile ème studio | lm studio | ai_cluster | 0 |
| aime dé | amd | ai_cluster | 0 |
| au lama | ollama | ai_cluster | 0 |
| clostaire | cluster | ai_cluster | 0 |
| clouster | cluster | ai_cluster | 0 |
| cuda | cuda | ai_cluster | 0 |
| elle aime studio | lm studio | ai_cluster | 0 |
| enne vidéa | nvidia | ai_cluster | 0 |
| haut lama | ollama | ai_cluster | 0 |
| huguine face | huggingface | ai_cluster | 0 |
| ji pi you | gpu | ai_cluster | 0 |
| jé pé u | gpu | ai_cluster | 0 |
| langle chaîne | langchain | ai_cluster | 0 |
| langue chaîne | langchain | ai_cluster | 0 |
| o lama | ollama | ai_cluster | 0 |
| ouisper | whisper | ai_cluster | 0 |
| ouispère | whisper | ai_cluster | 0 |
| paille tork | pytorch | ai_cluster | 0 |
| paye torch | pytorch | ai_cluster | 0 |
| pine cône | pinecone | ai_cluster | 0 |
| qlosstère | cluster | ai_cluster | 0 |
| tence heure flo | tensorflow | ai_cluster | 0 |
| tenser flot | tensorflow | ai_cluster | 0 |
| transe formeur | transformer | ai_cluster | 0 |
| ugine face | huggingface | ai_cluster | 0 |
| vie rame | vram | ai_cluster | 0 |
| whisper | whisper | ai_cluster | 0 |
| zi rame | zram | ai_cluster | 0 |
| zia ram | zram | ai_cluster | 0 |
| au da city | audacity | application | 0 |
| aude a city | audacity | application | 0 |
| blaindeur | blender | application | 0 |
| blendeur | blender | application | 0 |
| coddy | kodi | application | 0 |
| dis cord | discord | application | 0 |
| disse corde | discord | application | 0 |
| file zilla | filezilla | application | 0 |
| filzilla | filezilla | application | 0 |
| gimp | gimp | application | 0 |
| jaimpe | gimp | application | 0 |
| kodi | kodi | application | 0 |
| libre office | libreoffice | application | 0 |
| libre ofice | libreoffice | application | 0 |
| nau ti luce | nautilus | application | 0 |
| nautiluce | nautilus | application | 0 |
| obesse studio | obs | application | 0 |
| obs studio | obs | application | 0 |
| spot y faille | spotify | application | 0 |
| spoty faille | spotify | application | 0 |
| steam | steam | application | 0 |
| stim | steam | application | 0 |
| thunder bird | thunderbird | application | 0 |
| tondeur birde | thunderbird | application | 0 |
| trans mission | transmission | application | 0 |
| v l c | vlc | application | 0 |
| v s code | vscode | application | 0 |
| vie esse code | vscode | application | 0 |
| vé elle cé | vlc | application | 0 |
| vé esse code | vscode | application | 0 |
| mosaique 4 | mosaique 4 | auto_learned | 0 |
| active le mode sombr | active le mode sombre | full_phrase | 0 |
| affiche les procéssuce | affiche les processus | full_phrase | 0 |
| affiche les service actif | affiche les services actifs | full_phrase | 0 |
| allume la camérat | allume la caméra | full_phrase | 0 |
| arrête le serveure | arrête le serveur | full_phrase | 0 |
| combien de mémoir | combien de mémoire | full_phrase | 0 |
| combien de mémouar | combien de mémoire | full_phrase | 0 |
| coupe le micro | coupe le micro | full_phrase | 0 |
| désactive le mode sombr | désactive le mode sombre | full_phrase | 0 |
| fais un bac up | fais un backup | full_phrase | 0 |
| fait un bac cup | fais un backup | full_phrase | 0 |
| ferme toute les fenêtres | ferme toutes les fenêtres | full_phrase | 0 |
| lance le serveure | lance le serveur | full_phrase | 0 |
| lance une analyse de sécurité | lance une analyse de sécurité | full_phrase | 0 |
| les mets à jour | mets à jour | full_phrase | 0 |
| mets le son a fond | mets le son à fond | full_phrase | 0 |
| montre l'espace disque | montre l'espace disque | full_phrase | 0 |
| montre la températur | montre la température | full_phrase | 0 |
| montre le tableau de bor | montre le tableau de bord | full_phrase | 0 |
| montre les loges | montre les logs | full_phrase | 0 |
| montre les logue | montre les logs | full_phrase | 0 |
| ouvre le terminale | ouvre le terminal | full_phrase | 0 |
| ouvre un navigateure | ouvre un navigateur | full_phrase | 0 |
| quel processeur | quel cpu | full_phrase | 0 |
| quelle heure ait il | quelle heure est-il | full_phrase | 0 |
| quelle heure et il | quelle heure est-il | full_phrase | 0 |
| redémarre le réseaux | redémarre le réseau | full_phrase | 0 |
| redémarre le réso | redémarre le réseau | full_phrase | 0 |
| vérifie le clustère | vérifie le cluster | full_phrase | 0 |
| vérifie leclustère | vérifie le cluster | full_phrase | 0 |
| a fiche | affiche | homophone | 0 |
| a lume | allume | homophone | 0 |
| a rrête | arrête | homophone | 0 |
| affiche | affiche | homophone | 0 |
| allume | allume | homophone | 0 |
| aret | arrête | homophone | 0 |
| arrêt | arrête | homophone | 0 |
| cher che | cherche | homophone | 0 |
| con figure | configure | homophone | 0 |
| con figurer | configure | homophone | 0 |
| de connecte | déconnecte | homophone | 0 |
| des installe | désinstalle | homophone | 0 |
| dé connecte | déconnecte | homophone | 0 |
| dés installe | désinstalle | homophone | 0 |
| et tein | éteint | homophone | 0 |
| et teins | éteins | homophone | 0 |
| et teint | éteint | homophone | 0 |
| ex écute | exécute | homophone | 0 |
| fair me | ferme | homophone | 0 |
| fer me | ferme | homophone | 0 |
| fer mé | ferme | homophone | 0 |
| in stal | installe | homophone | 0 |
| in stalle | installe | homophone | 0 |
| mais a jour | mets à jour | homophone | 0 |
| mais à jour | mets à jour | homophone | 0 |
| met a jour | mets à jour | homophone | 0 |
| net oie | nettoie | homophone | 0 |
| net toi | nettoie | homophone | 0 |
| net toie | nettoie | homophone | 0 |
| ou vr | ouvre | homophone | 0 |
| ou vre | ouvre | homophone | 0 |
| re cherche | recherche | homophone | 0 |
| re connecte | reconnecte | homophone | 0 |
| re de marre | redémarre | homophone | 0 |
| re démare | redémarre | homophone | 0 |
| re lance | relance | homophone | 0 |
| redémar | redémarre | homophone | 0 |
| ré connecte | reconnecte | homophone | 0 |
| ré démare | redémarre | homophone | 0 |
| ré initialise | réinitialise | homophone | 0 |
| su prim | supprime | homophone | 0 |
| su prime | supprime | homophone | 0 |
| supprime | supprime | homophone | 0 |
| tele charge | télécharge | homophone | 0 |
| télé charge | télécharge | homophone | 0 |
| télé charger | télécharge | homophone | 0 |
| veri fit | vérifie | homophone | 0 |
| véri fie | vérifie | homophone | 0 |
| vérifi | vérifie | homophone | 0 |
| éxécute | exécute | homophone | 0 |
| aime deux | m2 | jarvis_name | 0 |
| aime trois | m3 | jarvis_name | 0 |
| aime un | m1 | jarvis_name | 0 |
| eau aile deux | ol2 | jarvis_name | 0 |
| eau aile trois | ol3 | jarvis_name | 0 |
| eau aile un | ol1 | jarvis_name | 0 |
| eau elle deux | ol2 | jarvis_name | 0 |
| eau elle trois | ol3 | jarvis_name | 0 |
| eau elle un | ol1 | jarvis_name | 0 |
| jar vis | jarvis | jarvis_name | 0 |
| jar visse | jarvis | jarvis_name | 0 |
| jarre vice | jarvis | jarvis_name | 0 |
| la créa trice | la créatrice | jarvis_name | 0 |
| le contrôle heure | le contrôleur | jarvis_name | 0 |
| le pont | le pont | jarvis_name | 0 |
| cent pour cent | 100% | number_unit | 0 |
| cinq pour cent | 5% | number_unit | 0 |
| cinquante pour cent | 50% | number_unit | 0 |
| deux gigas | 2 Go | number_unit | 0 |
| dix pour cent | 10% | number_unit | 0 |
| huit gigas | 8 Go | number_unit | 0 |
| quarante pour cent | 40% | number_unit | 0 |
| quatre-vingt pour cent | 80% | number_unit | 0 |
| quatre-vingt-dix pour cent | 90% | number_unit | 0 |
| soixante pour cent | 60% | number_unit | 0 |
| soixante-dix pour cent | 70% | number_unit | 0 |
| trente pour cent | 30% | number_unit | 0 |
| un giga | 1 Go | number_unit | 0 |
| vingt pour cent | 20% | number_unit | 0 |
| zéro pour cent | 0% | number_unit | 0 |
| amazone | amazon | phonetic | 0 |
| annullé | annuler | phonetic | 0 |
| augmenter | monte | phonetic | 0 |
| baisser | baisse | phonetic | 0 |
| bleutousse | bluetooth | phonetic | 0 |
| blue tooth | bluetooth | phonetic | 0 |
| blutooth | bluetooth | phonetic | 0 |
| burkspace | workspace | phonetic | 0 |
| c p u | cpu | phonetic | 0 |
| c p u | cpu | phonetic | 0 |
| calculer | calculatrice | phonetic | 0 |
| calculette | calculatrice | phonetic | 0 |
| charvise | jarvis | phonetic | 0 |
| chrome | chrome | phonetic | 0 |
| clusteur | cluster | phonetic | 0 |
| clustère | cluster | phonetic | 0 |
| cluter | cluster | phonetic | 0 |
| coler | colle | phonetic | 0 |
| colé | colle | phonetic | 0 |
| copi | copie | phonetic | 0 |
| coppier | copie | phonetic | 0 |
| couper le son | mute | phonetic | 0 |
| couper son | mute | phonetic | 0 |
| crôme | chrome | phonetic | 0 |
| cépeyu | cpu | phonetic | 0 |
| desends | descends | phonetic | 0 |
| dis corde | discord | phonetic | 0 |
| discorde | discord | phonetic | 0 |
| djarvis | jarvis | phonetic | 0 |
| en arrière | en arriere | phonetic | 0 |
| faillefox | firefox | phonetic | 0 |
| fenaître | fenetre | phonetic | 0 |
| fenêtre | fenetre | phonetic | 0 |
| fermer | ferme | phonetic | 0 |
| fermez | ferme | phonetic | 0 |
| fermé | ferme | phonetic | 0 |
| file fox | firefox | phonetic | 0 |
| fire fox | firefox | phonetic | 0 |
| fénêtre | fenetre | phonetic | 0 |
| g p u | gpu | phonetic | 0 |
| g p u | gpu | phonetic | 0 |
| git hub | github | phonetic | 0 |
| gogle | google | phonetic | 0 |
| gogol | google | phonetic | 0 |
| googl | google | phonetic | 0 |
| gougle | google | phonetic | 0 |
| guithab | github | phonetic | 0 |
| guithub | github | phonetic | 0 |
| gé pé u | gpu | phonetic | 0 |
| gé pé u | gpu | phonetic | 0 |
| haut parleur | volume | phonetic | 0 |
| haut parleur | volume | phonetic | 0 |
| instagramme | instagram | phonetic | 0 |
| jarvi | jarvis | phonetic | 0 |
| jarvice | jarvis | phonetic | 0 |
| jarvy | jarvis | phonetic | 0 |
| linkedine | linkedin | phonetic | 0 |
| linquedine | linkedin | phonetic | 0 |
| mode claire | mode clair | phonetic | 0 |
| mode claire | mode clair | phonetic | 0 |
| mode somber | mode sombre | phonetic | 0 |
| mode sombr | mode sombre | phonetic | 0 |
| moteur de recherche | google | phonetic | 0 |
| netflix | netflix | phonetic | 0 |
| ouaifi | wifi | phonetic | 0 |
| ouatssap | whatsapp | phonetic | 0 |
| ouifi | wifi | phonetic | 0 |
| ouvert | ouvre | phonetic | 0 |
| ouvrer | ouvre | phonetic | 0 |
| ouvres | ouvre | phonetic | 1 |
| ouvrez | ouvre | phonetic | 0 |
| ouvrir | ouvre | phonetic | 0 |
| page internet | navigateur | phonetic | 0 |
| page precedente | page precedente | phonetic | 0 |
| plein ecran | plein ecran | phonetic | 0 |
| plein écran | plein ecran | phonetic | 0 |
| presse papier | presse-papiers | phonetic | 0 |
| presse papier | presse-papiers | phonetic | 0 |
| presse-papier | presse-papiers | phonetic | 0 |
| processusse | processus | phonetic | 0 |
| procéssus | processus | phonetic | 0 |
| prècédente | precedente | phonetic | 0 |
| précédente | precedente | phonetic | 0 |
| r a m | ram | phonetic | 0 |
| ramme | ram | phonetic | 0 |
| remonter | remonte | phonetic | 0 |
| résau | reseau | phonetic | 0 |
| résaux | reseaux | phonetic | 0 |
| réseau | reseau | phonetic | 0 |
| sarvice | service | phonetic | 0 |
| sauvegardé | sauvegarde | phonetic | 0 |
| spotifaille | spotify | phonetic | 0 |
| spotifi | spotify | phonetic | 0 |
| statu | statut | phonetic | 1 |
| status | statut | phonetic | 2 |
| statut | statut | phonetic | 0 |
| suivente | suivante | phonetic | 0 |
| sèrvice | service | phonetic | 0 |
| sélectionné | selectionne | phonetic | 0 |
| sérvice | service | phonetic | 0 |
| tele gramme | telegram | phonetic | 0 |
| température | temperature | phonetic | 0 |
| températures | temperatures | phonetic | 0 |
| terminale | terminal | phonetic | 0 |
| terminaux | terminal | phonetic | 0 |
| tiktoque | tiktok | phonetic | 0 |
| tou tube | youtube | phonetic | 0 |
| tout en haut | tout en haut | phonetic | 0 |
| twitche | twitch | phonetic | 0 |
| télégrame | telegram | phonetic | 0 |
| v r a m | vram | phonetic | 0 |
| v ram | vram | phonetic | 0 |
| vis-code | vscode | phonetic | 0 |
| visual studio | vscode | phonetic | 0 |
| vollume | volume | phonetic | 0 |
| volum | volume | phonetic | 0 |
| volumme | volume | phonetic | 0 |
| vs code | vscode | phonetic | 0 |
| vérame | vram | phonetic | 0 |
| what's app | whatsapp | phonetic | 0 |
| wi fi | wifi | phonetic | 0 |
| work space | workspace | phonetic | 0 |
| you tube | youtube | phonetic | 0 |
| yutube | youtube | phonetic | 1 |
| aiche top | htop | system_command | 0 |
| aime vé cé | nmcli | system_command | 0 |
| aine aime cé elle aille | nmcli | system_command | 0 |
| aine top | ntop | system_command | 0 |
| apte guette | apt-get | system_command | 0 |
| apte gète | apt-get | system_command | 0 |
| aïe pé | ip | system_command | 0 |
| crone tab | crontab | system_command | 0 |
| crontabe | crontab | system_command | 0 |
| do quaire | docker | system_command | 0 |
| doker | docker | system_command | 0 |
| doqueur | docker | system_command | 0 |
| dé paquet age | dpkg | system_command | 0 |
| dé pé ka gé | dpkg | system_command | 0 |
| essai essai aiche | ssh | system_command | 0 |
| esse esse hache | ssh | system_command | 0 |
| eu effe double | ufw | system_command | 0 |
| fla pack | flatpak | system_command | 0 |
| flat pack | flatpak | system_command | 0 |
| h top | htop | system_command | 0 |
| journal contrôle | journalctl | system_command | 0 |
| journal cé té elle | journalctl | system_command | 0 |
| paille thon | python | system_command | 0 |
| paille tonne | python | system_command | 0 |
| pi thon | python | system_command | 0 |
| snape | snap | system_command | 0 |
| system cé té elle | systemctl | system_command | 0 |
| système contrôle | systemctl | system_command | 0 |
| système cé té elle | systemctl | system_command | 0 |
| u f w | ufw | system_command | 0 |
