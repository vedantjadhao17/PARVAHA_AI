import sys

with open("app/sim/manager.py", "r") as f:
    content = f.read()

# Replace the manual contract_path loading with model_5m.feature_names
init_features_old = """        # Feature names
        contract_path = self.project_dir / "data" / "processed" / "forecast_feature_contract.json"
        self.feature_names = []
        if contract_path.exists():
            import json
            with open(contract_path, "r") as f:
                contract = json.load(f)
                self.feature_names = contract.get("features", [])
        if not self.feature_names or len(self.feature_names) != 42:
            self.feature_names = [f"f{i}" for i in range(42)]"""

init_features_new = """        # Feature names - get exactly what XGBoost expects from the loaded model
        self.feature_names = self.model_5m.feature_names
        if not self.feature_names:
            self.feature_names = [f"f{i}" for i in range(42)]"""

content = content.replace(init_features_old, init_features_new)

with open("app/sim/manager.py", "w") as f:
    f.write(content)
