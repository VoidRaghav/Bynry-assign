class ResourceLedger:
    def __init__(self):
        self.entries = []

    def track(self, label, cleanup):
        self.entries.append((label, cleanup))

    # newest first, so a child record never outlives its parent
    def release(self):
        failures = []
        for label, cleanup in reversed(self.entries):
            try:
                cleanup()
            except Exception as error:
                failures.append(f"{label}: {error}")
        self.entries.clear()
        return failures
