import sys

with open("app/sim/manager.py", "r") as f:
    content = f.read()

init_end = """        self.model_10m.load_model(str(self.project_dir / "models" / "queue_10m.json"))"""
init_added = """        self.model_10m.load_model(str(self.project_dir / "models" / "queue_10m.json"))
        
        with open(self.junction_cfg_path, 'r') as f:
            self.config = json.load(f)"""
content = content.replace(init_end, init_added)

with open("app/sim/manager.py", "w") as f:
    f.write(content)
