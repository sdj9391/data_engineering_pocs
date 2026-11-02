class LocalWhisperBackend:
    """Run speech-to-text locally with the faster-whisper package."""

    def __init__(self, model_name, language_code):
        from faster_whisper import WhisperModel

        # device="auto" lets Whisper choose CPU/GPU; int8 reduces memory usage.
        self.model = WhisperModel(model_name, device="auto", compute_type="int8")
        # Whisper expects the base language ("en"), while config uses "en-US".
        self.language = language_code.split("-")[0]

    def transcribe(self, chunk_path):
        """Transcribe one WAV chunk and return timestamped text segments."""
        segments, _ = self.model.transcribe(
            str(chunk_path), language=self.language, vad_filter=True,
        )
        # Convert library-specific segment objects into plain dictionaries.
        return [
            {"start_seconds": segment.start, "end_seconds": segment.end,
             "text": segment.text}
            for segment in segments
        ]
