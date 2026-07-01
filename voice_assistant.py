import requests
import pyttsx3
import pyaudio
import json
import os
import sys
import datetime
from vosk import Model, KaldiRecognizer


class VoiceAssistant:
    def __init__(self):
        # Получаем путь к директории скрипта
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"Директория скрипта: {self.script_dir}")

        # Инициализация синтезатора речи
        self.tts_engine = pyttsx3.init()
        self.tts_engine.setProperty("rate", 150)
        self.tts_engine.setProperty("volume", 0.9)

        # Настройки голоса для русского
        voices = self.tts_engine.getProperty("voices")
        for voice in voices:
            if "russian" in voice.name.lower():
                self.tts_engine.setProperty("voice", voice.id)
                break

        # Пути к модели Vosk (пробуем несколько вариантов)
        model_paths = [
            "vosk-model-small-ru-0.22",  # относительный путь
            os.path.join(
                self.script_dir, "vosk-model-small-ru-0.22"
            ),  # абсолютный путь
            os.path.join(
                os.getcwd(), "vosk-model-small-ru-0.22"
            ),  # текущая рабочая директория
        ]

        model_path = None
        for path in model_paths:
            if os.path.exists(path):
                model_path = path
                print(f"Модель найдена по пути: {model_path}")
                break

        if not model_path:
            print(f"Модель Vosk не найдена!")
            print(f"Искал в следующих местах:")
            for path in model_paths:
                print(f"  - {path}")
            print("\nУбедитесь, что:")
            print("1. Вы скачали модель с https://alphacephei.com/vosk/models")
            print("2. Распаковали архив")
            print(
                "3. Папка 'vosk-model-small-ru-0.22' находится в той же папке, что и voice_assistant.py"
            )
            exit(1)

        try:
            print(f"Загружаю модель Vosk из: {model_path}")
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            print("Модель Vosk успешно загружена")
        except Exception as e:
            print(f"Ошибка при загрузке модели Vosk: {e}")
            exit(1)

        # Настройка аудиопотока
        try:
            self.audio = pyaudio.PyAudio()
            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4000,
            )
            print("Аудиопоток настроен успешно")
        except Exception as e:
            print(f"Ошибка при настройке аудио: {e}")
            print("Убедитесь, что микрофон подключен и доступен")
            exit(1)

        # Город для погоды
        self.city = "Saint-Petersburg"

        # Файл для заметок (в той же директории, что и скрипт)
        self.notes_file = os.path.join(self.script_dir, "notes.txt")

        # Флаги для отслеживания состояния
        self.listening = True

        print("Голосовой ассистент инициализирован")

    def speaking(self, text):
        """Произнесение текста"""
        print(f"Ассистент: {text}")
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            print(f"Ошибка синтеза речи: {e}")

    def get_weather_data(self):
        """Получение данных о погоде с wttr.in"""
        try:
            # Получаем данные в JSON формате
            response = requests.get(f"https://wttr.in/{self.city}?format=j1")
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Ошибка получения погоды: {e}")
            return None

    def parse_weather_command(self, command_text):
        """Обработка команд, связанных с погодой"""
        weather_data = self.get_weather_data()
        if not weather_data:
            self.speaking("Не удалось получить данные о погоде")
            return

        try:
            current_condition = weather_data["current_condition"][0]

            if "погода" in command_text:
                temp_c = current_condition["temp_C"]
                weather_desc = current_condition["weatherDesc"][0]["value"]
                self.speaking(
                    f"Сейчас в Санкт-Петербурге {temp_c} градусов, {weather_desc}"
                )

            elif "ветер" in command_text:
                wind_speed = current_condition["windspeedKmph"]
                self.speaking(f"Скорость ветра {wind_speed} километров в час")

            elif "направление" in command_text or "направление ветра" in command_text:
                wind_dir = current_condition.get("winddir16Point", "неизвестно")
                self.speaking(f"Направление ветра {wind_dir}")

            elif "прогулка" in command_text or "прогуляться" in command_text:
                temp_c = int(current_condition["temp_C"])
                wind_speed = int(current_condition["windspeedKmph"])

                if temp_c < 5 or wind_speed > 15:
                    self.speaking(
                        "Прогулка не рекомендуется. Слишком холодно или ветрено."
                    )
                else:
                    self.speaking("Прогулка рекомендуется. Погода хорошая.")

        except KeyError as e:
            print(f"Ошибка парсинга данных погоды: {e}")
            self.speaking("Не удалось обработать данные о погоде")

    def add_note(self, note_text):
        """Добавление заметки в файл"""
        try:
            with open(self.notes_file, "a", encoding="utf-8") as f:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"{timestamp}: {note_text}\n")
            self.speaking("Заметка сохранена")
            print(f"Заметка сохранена: {note_text}")
        except Exception as e:
            print(f"Ошибка записи заметки: {e}")
            self.speaking("Не удалось сохранить заметку")

    def listen_for_speech(self, timeout=7):
        """Прослушивание речи с таймаутом"""
        print("Слушаю...")

        # Собираем аудиоданные
        audio_data = b""
        start_time = datetime.datetime.now()

        while (datetime.datetime.now() - start_time).seconds < timeout:
            try:
                data = self.stream.read(4000, exception_on_overflow=False)
                audio_data += data

                # Пробуем распознать речь
                if self.recognizer.AcceptWaveform(data):
                    result = json.loads(self.recognizer.Result())
                    text = result.get("text", "").strip()
                    if text:
                        return text
            except Exception as e:
                print(f"Ошибка чтения аудио: {e}")
                continue

        # Пробуем распознать то, что накопили
        if audio_data and len(audio_data) > 0:
            if self.recognizer.AcceptWaveform(audio_data):
                result = json.loads(self.recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    return text

        return ""

    def process_command(self, command):
        """Обработка распознанной команды"""
        if not command or command.strip() == "":
            return

        command_lower = command.lower()
        print(f"Распознанная команда: {command_lower}")

        # Команды с погодой
        if any(
            word in command_lower
            for word in ["погода", "ветер", "прогулка", "прогуляться", "направление"]
        ):
            self.parse_weather_command(command_lower)

        # Команда записи заметки
        elif (
            "записать" in command_lower
            or "заметка" in command_lower
            or "запиши" in command_lower
        ):
            self.speaking("Что записать? Говорите после сигнала.")

            # Даем время на подготовку
            import time

            time.sleep(1)

            # Запись заметки
            note = self.listen_for_speech(timeout=10)
            if note and note.strip():
                self.add_note(note.strip())
            else:
                self.speaking("Не удалось распознать заметку")

        # Команда выхода
        elif any(
            word in command_lower
            for word in ["стоп", "выход", "завершить", "хватит", "пока"]
        ):
            self.speaking("Завершение работы. До свидания!")
            self.listening = False

        # Неизвестная команда
        else:
            self.speaking("Не понял команду. Попробуйте еще раз.")
            print(f"Неизвестная команда: {command_lower}")

    def run(self):
        """Основной цикл работы ассистента"""
        print("\n" + "=" * 50)
        print("Голосовой ассистент запущен!")
        print("Доступные команды:")
        print("1. 'Погода' - узнать текущую погоду")
        print("2. 'Ветер' - узнать скорость ветра")
        print("3. 'Направление' - узнать направление ветра")
        print("4. 'Прогулка' - получить рекомендацию по прогулке")
        print("5. 'Записать' - добавить голосовую заметку")
        print("6. 'Стоп' - завершить работу")
        print("=" * 50 + "\n")

        self.speaking("Голосовой ассистент готов к работе. Говорите команды.")

        while self.listening:
            try:
                # Слушаем команду
                command = self.listen_for_speech()

                if command and command.strip():
                    self.process_command(command)

            except KeyboardInterrupt:
                print("\n\nЗавершение работы по запросу пользователя")
                self.speaking("До свидания!")
                self.listening = False
                break

            except Exception as e:
                print(f"Критическая ошибка: {e}")
                self.speaking("Произошла ошибка. Продолжаю работу.")

        # Очистка ресурсов
        try:
            self.stream.stop_stream()
            self.stream.close()
            self.audio.terminate()
        except:
            pass


def main():
    """Основная функция"""
    print("Запуск голосового ассистента...")
    print(f"Текущая рабочая директория: {os.getcwd()}")
    print(f"Путь к скрипту: {os.path.abspath(__file__)}")

    # Проверяем, установлены ли необходимые библиотеки
    try:
        import pyttsx3
        import pyaudio
        import vosk
    except ImportError as e:
        print(f"Ошибка: Не удалось импортировать библиотеку {e}")
        print("Установите необходимые библиотеки командой:")
        print("pip install requests pyttsx3 pyaudio vosk")
        return

    assistant = VoiceAssistant()
    assistant.run()


if __name__ == "__main__":
    main()
