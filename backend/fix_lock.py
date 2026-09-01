with open("app/sim/manager.py", "r") as f:
    content = f.read()

# Restore the inner loop one
content = content.replace("""                    if self.pending_plan:
                        self._execute_plan(self.pending_plan)
                        self.pending_plan = None
        self.lock = threading.Lock()""", """                    if self.pending_plan:
                        self._execute_plan(self.pending_plan)
                        self.pending_plan = None""")

# Add the proper lock to __init__
content = content.replace("""        self.feature_extractor = LiveFeatureExtractor(self.feature_names)
        self.pending_plan = None""", """        self.feature_extractor = LiveFeatureExtractor(self.feature_names)
        self.pending_plan = None
        self.lock = threading.Lock()""")

with open("app/sim/manager.py", "w") as f:
    f.write(content)
