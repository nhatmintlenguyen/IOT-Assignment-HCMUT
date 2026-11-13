# Spécifications Matérielles : Kit OhStem AIoT & YoloUNO

Ce document détaille l'ensemble des composants physiques du **Kit AIoT OhStem** (référence : [OhStem AIoT Kit](https://ohstem.vn/san-pham/aiot-kit-hoc-lap-trinh-iot-va-ai/)), leur affectation au projet **Smart Safe Guardian**, et l'analyse électrique (tensions, courants, prévention des coupures/brownouts).

---

## 1. Inventaire Exhaustif du Matériel Disponible

### 1.1 Unités de Traitement (Microcontrôleurs)

| Dispositif | Puce & Caractéristiques | Rôle dans le Projet |
| :--- | :--- | :--- |
| **YoloUNO** | **ESP32-S3 Dual-Core Xtensa LX7 @ 240 MHz**<br>• 512 Ko SRAM, 8 Mo Flash<br>• Wi-Fi 2.4 GHz (802.11 b/g/n) + BLE 5.0<br>• Facteur de forme Arduino Uno R3 avec **12 connecteurs Grove intégrés**<br>• 4 ports servo GVS dédiés, port USB Type-C natif, jack DC 7-12V | **Unité centrale du Coffre (Vault Unit)** : Gestion des capteurs, authentification, contrôle du pêne (servo), liaison série Gateway et serveur Web de secours. |
| **Yolo:Bit** | **ESP32 Dual-Core**<br>• Matrice de 25 LED RGB (5×5)<br>• 2 boutons-poussoirs A et B<br>• Buzzer piézoélectrique intégré<br>• Accéléromètre / Gyroscope intégrés<br>• Alimentation par boîtier 2× piles AAA (3V) ou USB-C | **Badge Portatif de Sécurité (Wearable Badge)** : Demande d'accès sans fil via ESP-NOW (Bouton A) ou alerte de détresse (Bouton B), feedback visuel et sonore. |

---

### 1.2 Capteurs Disponibles (Sensors)

| Capteur | Interface & Port Grove | Usage dans le Coffre | État |
| :--- | :--- | :--- | :---: |
| **DHT20** | **I2C** (Adresse `0x38`) — Port Grove I2C | Télémétrie continue température & humidité (climatisation et détection départ de feu). | **Retenu** |
| **Capteur de Lumière (LDR)** | **Analogique** — Port Grove A0 | Placé à l'intérieur du coffre. Détecte toute ouverture physique illicite en mode verrouillé. | **Retenu** |
| **Capteur Ultrason (Grove)** | **Numérique** — Port Grove D2/D3 | Détecte l'approche d'un technicien (< 30 cm) pour réveiller l'écran LCD de veille. | **Retenu** |
| **Récepteur IR (1838)** | **Numérique** — Port Grove D4 | Capture des trames NEC émises par la télécommande pour le PIN de secours. | **Retenu** |
| **Capteur de Mouvement PIR** | Numérique — Port Grove | Détection volumétrique infrarouge de présence humaine. | *Optionnel* |
| **Capteur d'Humidité du Sol** | Analogique — Port Grove | Destiné à l'agriculture connectée. | *Non utilisé* |

---

### 1.3 Actionneurs, Affichage & Contrôle (Actuators & Output)

| Module | Interface | Usage dans le Coffre | État |
| :--- | :--- | :--- | :---: |
| **Moteur Servo (MG90 / SG90)** | **PWM (50 Hz)** — Port GVS Servo | Pêne mécanique de verrouillage de la porte (0° = Déverrouillé, 90° = Verrouillé). | **Retenu** |
| **Écran LCD 1602 I2C** | **I2C** (Adresse `0x27` ou `0x3F`) — Port Grove I2C | Interface utilisateur locale (messages de bienvenue, saisie du PIN masqué `* * * *`, statut). | **Retenu** |
| **LED NeoPixel intégrée** | **GPIO 45** (1-Wire interne YoloUNO) | Balise d'état lumineuse : **Vert** (Ouvert), **Bleu** (Saisie PIN), **Rouge** (Verrouillé/Alarme). | **Retenu** |
| **LED Heartbeat D13** | **GPIO 48** (Interne YoloUNO) | Clignotement à 1 Hz attestant du bon fonctionnement de l'ordonnanceur FreeRTOS. | **Retenu** |
| **Télécommande IR** | Protocole NEC sans fil (38 kHz) | Clavier numérique déporté pour la saisie du code PIN de secours. | **Retenu** |
| **Module Relais 2 Canaux** | Numérique / USB (Isolation optocouplée) | Disponible pour commuter un verrou électromagnétique externe (maglock 12V) ou sirène. | *En réserve* |
| **Module 4 LED RGB Grove** | 1-Wire numérique | Barre de LED additionnelle si besoin d'effets lumineux déportés. | *En réserve* |
| **Mini Ventilateur & Pompe** | PWM / Numérique | Refroidissement d'urgence si surchauffe interne. | *En réserve* |

---

## 2. Analyse Électrique & Réponses aux Risques Matériels

### 2.1 Risque de Tension & Adaptation de Niveaux (3.3V vs 5V)
* **La problématique classique :** Sur une platine d'essai (*breadboard*) avec des composants génériques (ex: HC-SR04 classique), le capteur est alimenté en 5V et sa broche `Echo` renvoie 5V directement sur le GPIO de l'ESP32, risquant de griller l'entrée (limitée à 3.6V).
* **La réalité avec le kit OhStem YoloUNO :** 
  * Tous les modules du kit sont au format **Grove 4 broches**.
  * Les ports Grove I2C et Analogiques de la YoloUNO sont déjà adaptés aux niveaux logiques de l'ESP32-S3 (3.3V).
  * Le capteur ultrason OhStem intègre sur sa carte le circuit de conditionnement pour être branché sans danger directement sur les ports Grove numériques.
  * **Conclusion : Aucun composant externe (résistance, convertisseur de niveau) n'est nécessaire.** Tout est plug-and-play et sécurisé.

---

### 2.2 Risque d'Appel de Courant du Servomoteur (Brownout Reset)
* **Le phénomène :** Un servomoteur micro (SG90 ou MG90) consomme environ 100 à 250 mA en rotation à vide, mais peut appeler **600 à 800 mA en crête** s'il force contre une butée mécanique (pêne coincé).
* **Le risque :** Si la carte YoloUNO est alimentée uniquement par un port USB 2.0 d'ordinateur portable (limité à 500 mA), cette pointe de courant fait chuter la tension d'alimentation en dessous de 4.5V, déclenchant le détecteur de sous-tension de l'ESP32-S3 (**Brownout Detector: Reset**).
* **Solutions et Recommandations :**
  1. **Alimentation recommandée pour les démos :** Brancher la carte YoloUNO sur un port USB 3.0 / USB-C d'ordinateur (pouvant délivrer 900 mA à 1.5 A), ou utiliser un bloc chargeur USB 5V 2A / une batterie externe (power bank).
  2. **Alimentation externe via Jack DC :** La YoloUNO dispose d'un connecteur d'alimentation DC 5521 acceptant du 7V à 12V. Son régulateur de tension interne alimente alors confortablement les ports GVS pour servomoteur.
  3. **Course mécanique libre :** Calibrer l'angle PWM du servo (ex: entre 10° et 80° au lieu de forcer aux extrêmes 0° et 90°) pour s'assurer que le palonnier ne force jamais contre une paroi.

---

### 2.3 Utilisation du Module Relais (En option)
* Le kit comporte un module **Relais 2 canaux**.
* **Avantage :** Il possède une isolation optocouplée complète.
* **Scénario alternatif possible :** Si l'on souhaite simuler un coffre-fort industriel lourd équipé d'une ventouse magnétique (*maglock*) ou d'un verrou solénoïde 12V, le relais peut commuter cette alimentation sans aucun risque de parasitage pour le microcontrôleur. 
* Dans le cadre du projet, le **servo moteur MG90** reste le choix prioritaire car son mouvement rotatif est immédiatement visible lors de la vidéo démo.

---

### 2.4 Le nombre de périphériques est-il trop élevé ?
* **Sur breadboard avec des fils volants (DuPont) :** 8 modules représenteraient plus de 30 fils, ce qui serait suicidaire pour un projet étudiant (faux contacts garantis lors du déplacement de la maquette).
* **Sur la YoloUNO :** 
  * La carte intègre **12 connecteurs Grove détrompés** et **4 connecteurs GVS dédiés**.
  * Chaque périphérique possède son câble dédié rigide à clipser.
  * Il n'y a **aucun chevauchement de broches** (I2C partage le même bus avec des adresses distinctes `0x38` et `0x27`, l'ADC utilise A0, l'IR utilise D4, le servo utilise le port GVS).
* **Verdict :** Le nombre de périphériques est **parfaitement sain et gérable**. C'est propre, fiable pour la soutenance, et très impressionnant visuellement.

---

## 3. Tableau de Câblage Recommandé sur YoloUNO

| Périphérique | Type de Port sur YoloUNO | Connecteur Physique | Adresse / Broche |
| :--- | :--- | :--- | :--- |
| **Capteur DHT20** | Grove I2C | Port I2C #1 | Bus I2C (`0x38`) |
| **Afficheur LCD 1602** | Grove I2C | Port I2C #2 (ou chaîné) | Bus I2C (`0x27` ou `0x3F`) |
| **Capteur LDR (Lumière)** | Grove Analogique | Port Analogique A0 | Canaux ADC1 |
| **Capteur Ultrason** | Grove Numérique | Port Numérique D2 | GPIO Dédié Trig/Echo |
| **Récepteur IR (1838)** | Grove Numérique | Port Numérique D4 | GPIO Dédié Capture IR |
| **Servo MG90** | Connecteur GVS (3 broches) | Port Servo #1 | PWM LEDC (50 Hz) |
| **LED NeoPixel** | Intégrée sur board | Circuit interne | GPIO 45 |
| **LED D13 (Statut)** | Intégrée sur board | Circuit interne | GPIO 48 |
| **Liaison PC Gateway** | Câble USB-C | Port USB-C YoloUNO | UART CDC @ 115200 baud |
