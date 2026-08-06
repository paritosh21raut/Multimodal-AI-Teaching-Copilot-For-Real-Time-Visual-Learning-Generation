from app.speech.transcript_manager import TranscriptManager

manager = TranscriptManager()

manager.add("Hello everyone.")
manager.add("Today we study Computer Networks.")
manager.add("The OSI model has seven layers.")

print("=" * 50)
print(manager.get_all())
print("=" * 50)