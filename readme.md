# 🎉 ClapTrap Add-on pour Home Assistant 🎉

**ClapTrap** est un add-on puissant pour Home Assistant qui permet la détection d'applaudissements en temps réel 👏 à partir de diverses sources audio 🎤. Il s'appuie sur l'IA 🤖 et le modèle YAMNet pour offrir une reconnaissance audio précise et rapide, et envoie ses détections à Home Assistant via MQTT 🌐.

Cet addon est un fork de l'addon développé sur https://github.com/lfpoulain/ClapTrap-HA-Addon et a pour but de mieux s'intégrer dans home assistant

## ✨ Fonctionnalités principales

- 🔊 **Détection des sons** : Reconnaît les applaudissements à partir de microphones locaux, flux RTSP 📹 ou sources VBAN 🌐.
- 🔗 **MQTT** : Notifie via MQTT lorsqu'un événement est détecté.
- ⚡ **Support multi-sources** : Gère plusieurs flux simultanément avec des réglages indépendants.

## 📋 Prérequis

- 🏠 **Home Assistant x86 installé**
- 🔗 **Mosquitto Broker** (ou tout autre broker MQTT compatible)

## 🚀 Installation

### Étape 1 : Ajout du dépôt
1. Ouvrez Home Assistant et allez dans **Paramètres** > **Add-ons, Backups & Supervisor** > **Add-on Store**.
2. Cliquez sur **Menu (⋮)** > **Dépôt** et ajoutez l'URL de votre dépôt GitHub contenant cet add-on.

### Étape 2 : Installation de l'add-on
1. Recherchez **ClapTrap** dans l'Add-on Store.
2. Cliquez sur **Installer** 🛠️, (ATTENTION la compilation peut prendre plusieurs minutes), puis sur **Configurer** ⚙️
3. Cliquez sur **Démarrer** ▶️ une fois la configuration terminée.

## 🛠️ Utilisation

1. Configurez les paramètres audio :
   - **Sources** : Sélectionnez vos microphones 🎤, flux RTSP 📹 ou sources VBAN 🌐.
   - **Paramètres de détection** : Ajustez le seuil de sensibilité 📈 et les délais entre détections ⏱️.
2. Une fois démarrée, l'addon démarre automatiquement la détection audio 🎧.
3. Visualisez les détections en temps réel 👀 et recevez les événements via MQTT 🌐.

## ⚙️ Paramètres

- 🎙️ **Sources audio** :  
  - Microphone local 🎤  
  - Flux RTSP 📹  
  - Sources VBAN 🌐  
- 🔧 **MQTT Configuration** :  
  - Hôte, port, utilisateur, mot de passe, topic de votre broker MQTT.
- 📈 **Seuil de détection** : Valeur entre 0 et 1 (par défaut : 0.5).
- ⏱️ **Délai entre détections** : Temps minimum en secondes (par défaut : 2).

## 🤝 Contribution

Vous souhaitez contribuer ? 🛠️ Consultez le fichier `DEV_BOOK.md` 📘 pour en savoir plus sur la structure du projet et les étapes de développement.
Big thanks to @korben qui a entierement developpé le systeme de reconnaisance en Python.

## 🆘 Support

Si vous rencontrez des problèmes, consultez la documentation complète dans `DOCUMENTATION.md` 📖 ou ouvrez une issue sur le dépôt GitHub 🐙.
