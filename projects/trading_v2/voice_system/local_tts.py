"""
LOCAL TTS v1.0 - Fallback TTS rapide via pyttsx3 (Microsoft SAPI5)
Fonctionne 100% local, zero latence reseau, voix FR si disponible.

Usage:
    from local_tts import LocalTTS
    tts = LocalTTS()
    tts.speak("Bonjour")
"""
import pyttsx3


class LocalTTS:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.engine.setProperty('rate', 190)
        self.engine.setProperty('volume', 1.0)

        # Chercher une voix francaise
        voices = self.engine.getProperty('voices')
        for v in voices:
            if "french" in v.name.lower() or "fr" in v.id.lower():
                self.engine.setProperty('voice', v.id)
                print(f"  [LOCAL-TTS] Voix FR: {v.name}")
                break
        else:
            print("  [LOCAL-TTS] Pas de voix FR, voix par defaut.")

    def speak(self, text):
        """Parle le texte localement via SAPI5."""
        print(f"  [LOCAL-TTS] {text}")
        try:
            self.engine.say(text)
            self.engine.runAndWait()
            return True
        except Exception as e:
            print(f"  [LOCAL-TTS] Erreur: {e}")
            return False
